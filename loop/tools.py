"""Tool schemas + dispatcher exposing data/ fetchers to the hosted model.

OpenAI-style function-calling definitions for the functions in
`data.feeds`, `data.nexla_client`, and `data.injector`, plus a dispatcher
that executes a tool call by name. `loop.model` passes `TOOLS` to the Akash
chat-completions endpoint and routes any `tool_calls` it gets back through
`call_tool`, so the model can pull fresh trial/FDA/news/price data (or fire
a scripted demo catalyst) instead of only ever seeing the catalyst it was
handed.
"""

from data import feeds, injector, nexla_client

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_trials",
            "description": "ClinicalTrials.gov phase-readout catalysts for GLP-1/obesity tickers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_fda",
            "description": "openFDA approval / new-indication catalysts for GLP-1/obesity tickers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_news",
            "description": "Pharma news-headline catalysts for GLP-1/obesity tickers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_prices",
            "description": "Latest close price per ticker, via yfinance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tickers to price; defaults to the full portfolio universe.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexla_pull",
            "description": "One merged Nexla read: {catalysts, prices} across trials/FDA/news/prices in a single call.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inject_demo_catalyst",
            "description": "Fire one of the two scripted demo catalysts at the running loop's /inject endpoint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "0 or 1 — which DEMO_CATALYSTS entry to fire."},
                    "url": {"type": "string", "description": "Loop base URL; defaults to http://localhost:8000."},
                },
                "required": ["index"],
            },
        },
    },
]

_NEXLA = nexla_client.NexlaSource()


def call_tool(name, arguments):
    """Execute a tool call by name and return a JSON-serializable result."""
    if name == "fetch_trials":
        return feeds.fetch_trials()
    if name == "fetch_fda":
        return feeds.fetch_fda()
    if name == "fetch_news":
        return feeds.fetch_news()
    if name == "fetch_prices":
        return feeds.fetch_prices(arguments.get("tickers"))
    if name == "nexla_pull":
        return _NEXLA.pull()
    if name == "inject_demo_catalyst":
        url = arguments.get("url", "http://localhost:8000")
        catalyst = injector.DEMO_CATALYSTS[arguments["index"]]
        injector.fire(url, catalyst)
        return {"fired": catalyst["headline"]}
    raise ValueError(f"unknown tool: {name}")

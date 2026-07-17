"""Source-feed adapters (P2).

Each returns contract-shaped *catalyst candidates* — dicts the loop can inject:
    {"headline": str, "source": str, "type": <catalyst type>,
     "ticker_primary": str, "phase": "Phase 3", "resolved": bool}

Trials/FDA/news are backed by Nexla via `backend.feed_search.search_feeds`
(see `backend/datasources.md`); `fetch_prices()` is wired directly with
yfinance. `data.nexla_client.NexlaSource.pull()` is the preferred entry point
for the loop — it issues a single shared `search_feeds` call and reuses the
mapping below rather than calling `fetch_trials`/`fetch_fda`/`fetch_news`
independently. These functions remain here as thin, single-source wrappers
for standalone/manual use.
"""

import re

from backend import feed_search

TICKERS = ["LLY", "NVO", "VKTX", "GPCR", "HSY", "MDLZ",
           "STZ", "DEO", "RMD", "INSP", "DVA"]

_CATALYST_TYPE_BY_SOURCE = {
    "clinicaltrials": "trial_update",
    "openfda": "regulatory_update",
    "news": "news_mention",
}

_PHASE_RE = re.compile(r"Phase\s+\d+[A-Za-z]?", re.IGNORECASE)


def _infer_ticker(text):
    text_lower = text.lower()
    for ticker in TICKERS:
        if ticker.lower() in text_lower:
            return ticker
    return ""


def _infer_phase(text):
    match = _PHASE_RE.search(text)
    return match.group(0) if match else None


def to_catalyst(result):
    """Map a `search_feeds` result dict into the catalyst-candidate shape."""
    text = f"{result.get('title') or ''} {result.get('summary') or ''}"
    return {
        "headline": result.get("title"),
        "source": result.get("source"),
        "type": _CATALYST_TYPE_BY_SOURCE.get(result.get("source"), "unknown"),
        "ticker_primary": _infer_ticker(text),
        "phase": _infer_phase(text),
        "resolved": False,
    }


def search_catalyst_sources():
    """Call `search_feeds` once and return its raw `{results, errors}`."""
    return feed_search.search_feeds("")


def fetch_trials():
    """ClinicalTrials.gov v2 — obesity / GLP-1 phase readouts, via Nexla."""
    outcome = search_catalyst_sources()
    return [
        to_catalyst(result)
        for result in outcome["results"]
        if result.get("source") == "clinicaltrials"
    ]


def fetch_fda():
    """openFDA — approvals / new indications, via Nexla."""
    outcome = search_catalyst_sources()
    return [
        to_catalyst(result)
        for result in outcome["results"]
        if result.get("source") == "openfda"
    ]


def fetch_prices(tickers=None):
    """Market prices via yfinance — this one can be real.

    Returns {ticker: last_price}. Keeps a stub fallback so the loop never
    hard-fails if the network is down during the demo.
    """
    tickers = tickers or TICKERS
    try:
        import yfinance as yf
        data = yf.download(tickers, period="1d", progress=False)
        closes = data["Close"].iloc[-1]
        return {t: round(float(closes[t]), 2) for t in tickers if t in closes}
    except Exception:
        return {}


def fetch_news():
    """Pharma news RSS headline stream for catalyst detection, via Nexla."""
    outcome = search_catalyst_sources()
    return [
        to_catalyst(result)
        for result in outcome["results"]
        if result.get("source") == "news"
    ]

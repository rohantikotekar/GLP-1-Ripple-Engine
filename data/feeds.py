"""Source-feed adapters (P2).

Each returns contract-shaped *catalyst candidates* — dicts the loop can inject,
matching `backend/model_output.json`:
    {"id": str | None, "type": "phase3_readout"|"approval"|"new_indication"|"rx_volume",
     "ticker_primary": str, "detail": str, "resolved": bool, "ts": str | None}
Plus a "phase" field (e.g. "Phase 3") kept alongside for `loop.gate`'s
self-correct check, which isn't part of the P1 payload contract but is
harmless extra data.

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

# Broader GLP-1 ripple watchlist for on-demand price pulls (fetch_watchlist_prices),
# independent of the loop's own DEFAULT_BOOK tickers (loop/state.py).
WATCHLIST_TICKERS = [
    "LLY", "NVO", "ABT", "JNJ", "RHHBY", "MDT", "NSRGY", "AMGN",
    "VKTX", "DXCM", "HIMS", "PFE", "UNH", "CVS", "PEP",
]

_PHASE_RE = re.compile(r"Phase\s+\d+[A-Za-z]?", re.IGNORECASE)
_PHASE3_RE = re.compile(r"phase\s*3", re.IGNORECASE)
_NCT_RE = re.compile(r"(NCT\d+)", re.IGNORECASE)
_APPLICATION_NUMBER_RE = re.compile(r"\b((?:NDA|ANDA|BLA)\d+)\b", re.IGNORECASE)

_NEW_INDICATION_KEYWORDS = (
    "new indication", "expanded to", "expanded indication", "additional indication",
)


def _infer_ticker(text):
    text_lower = text.lower()
    for ticker in TICKERS:
        if ticker.lower() in text_lower:
            return ticker
    return ""


def _infer_phase(text):
    match = _PHASE_RE.search(text)
    return match.group(0) if match else None


def _infer_id(result):
    """Best-effort natural key: NCT id (clinicaltrials), application number
    (openfda), or the record's own url (news/yahoo) — else None."""
    source = result.get("source")
    if source == "clinicaltrials":
        match = _NCT_RE.search(result.get("url") or "") or _NCT_RE.search(result.get("title") or "")
        return match.group(1).upper() if match else None
    if source == "openfda":
        match = _APPLICATION_NUMBER_RE.search(result.get("summary") or "")
        return match.group(1).upper() if match else None
    return result.get("url")


def _infer_type(result, text):
    """Classify into the closed enum the loop's impact graph understands:
    phase3_readout | approval | new_indication | rx_volume."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in _NEW_INDICATION_KEYWORDS):
        return "new_indication"
    source = result.get("source")
    if source == "clinicaltrials":
        return "phase3_readout"
    if source == "openfda" or "approv" in text_lower:
        return "approval"
    if _PHASE3_RE.search(text_lower):
        return "phase3_readout"
    return "rx_volume"


def to_catalyst(result):
    """Map a `search_feeds` result dict into the catalyst-candidate shape."""
    text = f"{result.get('title') or ''} {result.get('summary') or ''}"
    return {
        "id": _infer_id(result),
        "type": _infer_type(result, text),
        "ticker_primary": _infer_ticker(text),
        "detail": result.get("title"),
        "resolved": False,
        "ts": result.get("ts"),
        "phase": _infer_phase(text),
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


def fetch_watchlist_prices(tickers=None):
    """On-demand price pull for the GLP-1 ripple watchlist, via yfinance.

    Defaults to WATCHLIST_TICKERS. Pulls a 5-trading-day window and
    forward-fills so a call made while the market is closed (nights,
    weekends, holidays) still returns each ticker's last available close
    instead of an empty/stale read for "today". Returns {} on any failure
    (network down, yfinance missing) - same fallback contract as
    fetch_prices(), so the loop never hard-fails on this.
    """
    tickers = tickers or WATCHLIST_TICKERS
    try:
        import yfinance as yf
        data = yf.download(tickers, period="5d", progress=False)
        closes = data["Close"].ffill().iloc[-1]
        prices = {}
        for t in tickers:
            if t not in closes:
                continue
            value = closes[t]
            if value != value:  # NaN check without a pandas/numpy import
                continue
            prices[t] = round(float(value), 2)
        return prices
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

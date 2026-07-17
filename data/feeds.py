"""Source-feed adapters (P2).

Each returns contract-shaped *catalyst candidates* — dicts the loop can inject:
    {"headline": str, "source": str, "type": <catalyst type>,
     "ticker_primary": str, "phase": "Phase 3", "resolved": bool}

fetch_prices() can be wired for real with yfinance today; the rest are stubs.
"""

TICKERS = ["LLY", "NVO", "VKTX", "GPCR", "HSY", "MDLZ",
           "STZ", "DEO", "RMD", "INSP", "DVA"]


def fetch_trials():
    """ClinicalTrials.gov v2 — obesity / GLP-1 phase readouts.

    Endpoint: https://clinicaltrials.gov/api/v2/studies  (free, no key)
    Fields to extract: phase, overallStatus, primaryCompletionDate, condition.
    """
    # TODO(P2/Nexla): route through Nexla pipeline
    return []


def fetch_fda():
    """openFDA — approvals / new indications (e.g. Zepbound sleep apnea label).

    Endpoint: https://api.fda.gov/drug/...  (free; higher limit with a key)
    """
    # TODO(P2/Nexla): route through Nexla pipeline
    return []


def fetch_prices(tickers=None):
    """Market prices via yfinance — this one can be real.

    Returns {ticker: last_price}. Wire yfinance below; keeps a stub fallback so
    the loop never hard-fails if the network is down during the demo.
    """
    tickers = tickers or TICKERS
    # TODO(P2/Nexla): route through Nexla pipeline
    try:
        import yfinance as yf
        data = yf.download(tickers, period="1d", progress=False)
        closes = data["Close"].iloc[-1]
        return {t: round(float(closes[t]), 2) for t in tickers if t in closes}
    except Exception:
        return {}


def fetch_news():
    """News / RSS headline stream for catalyst detection.

    RSS (FiercePharma, Endpoints, company IR) is the keyless, unlimited option.
    """
    # TODO(P2/Nexla): route through Nexla pipeline
    return []

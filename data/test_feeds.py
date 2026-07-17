"""Usage examples for data/feeds.py and data/nexla_client.py.

Mirrors backend/test.py's convention: load backend/.env for Nexla
credentials, then call each function and print its output. Run directly:

    python -m data.test_feeds
"""

import json
import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"
for line in _ENV_PATH.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip("'\""))

from data import feeds
from data.nexla_client import NexlaSource


def show(label, value):
    print(f"\n--- {label} ---")
    print(json.dumps(value, indent=2))


def main():
    # feeds.to_catalyst: map one raw search_feeds result into catalyst shape.
    raw_result = {
        "source": "openfda",
        "title": "WEGOVY (NOVO)",
        "summary": "approval — NDA218316, Phase 3",
        "url": None,
        "ts": "2026-06-18T00:00:00+00:00",
    }
    show("feeds.to_catalyst(raw_result)", feeds.to_catalyst(raw_result))

    # feeds.search_catalyst_sources: single shared search_feeds("") call,
    # returns the raw {"results": [...], "errors": [...]} before mapping.
    outcome = feeds.search_catalyst_sources()
    show(
        "feeds.search_catalyst_sources() [summary]",
        {"result_count": len(outcome["results"]), "errors": outcome["errors"]},
    )

    # feeds.fetch_trials / fetch_fda / fetch_news: single-source catalyst
    # lists, each filtering its own search_feeds("") call.
    show("feeds.fetch_trials()[:2]", feeds.fetch_trials()[:2])
    show("feeds.fetch_fda()[:2]", feeds.fetch_fda()[:2])
    show("feeds.fetch_news()[:2]", feeds.fetch_news()[:2])

    # feeds.fetch_prices: real yfinance lookup, falls back to {} on failure
    # (e.g. yfinance not installed, or network/rate-limit issues).
    show("feeds.fetch_prices(['LLY', 'NVO'])", feeds.fetch_prices(["LLY", "NVO"]))

    # NexlaSource.pull: the loop's entry point — one shared search_feeds
    # call reused across all 3 catalyst sources, plus prices.
    pulled = NexlaSource().pull()
    show(
        "NexlaSource().pull() [summary]",
        {
            "catalyst_count": len(pulled["catalysts"]),
            "catalysts_sample": pulled["catalysts"][:2],
            "prices": pulled["prices"],
        },
    )


if __name__ == "__main__":
    main()

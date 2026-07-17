"""Demo catalyst injector (P2).

Fires the scripted catalysts at the running loop on command so the demo never
depends on a real trial updating during judging. POSTs to /inject.

Usage:
    python -m data.injector                 # fire the full demo sequence
    python -m data.injector --url http://localhost:8000
"""

import argparse
import time

import httpx

# The scripted demo sequence — mirrors contracts/mock-events.json.
DEMO_CATALYSTS = [
    {
        "id": "NCT-DEMO-ALENIGLIPRON",
        "type": "phase3_readout",
        "ticker_primary": "GPCR",
        "detail": "Structure aleniglipron Phase 3 positive",
        "resolved": False,
        "ts": None,
        "phase": "Phase 2b",  # invalid phase → triggers the self-correct gate
    },
    {
        "id": "NDA-DEMO-ZEPBOUND-SLEEPAPNEA",
        "type": "new_indication",
        "ticker_primary": "LLY",
        "detail": "Zepbound expanded to sleep apnea",
        "resolved": False,
        "ts": None,
        "phase": "Phase 3",
    },
]


def fire(url, catalyst):
    r = httpx.post(f"{url}/inject", json=catalyst, timeout=10)
    r.raise_for_status()
    print(f"injected: {catalyst['detail']} -> {r.json()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--delay", type=float, default=6.0,
                    help="seconds between injections")
    args = ap.parse_args()

    for cat in DEMO_CATALYSTS:
        fire(args.url, cat)
        time.sleep(args.delay)


if __name__ == "__main__":
    main()

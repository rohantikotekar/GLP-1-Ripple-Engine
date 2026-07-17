"""Nexla data-layer wrapper.

Nexla's pitch is multi-source fusion: it joins the 4 feeds (trials + FDA +
prices + news) into one per-tick context on our contract. This class is the
seam the loop pulls from. It is backed by `backend.feed_search.search_feeds`
(Nexla Express API) for the 3 catalyst-bearing sources, and by
`data.feeds.fetch_prices` (yfinance) for prices.
"""

from data import feeds

_CATALYST_SOURCES = {"clinicaltrials", "openfda", "news"}


class NexlaSource:
    def __init__(self, pipeline_id=None, api_key=None):
        # TODO(P2): Nexla pipeline id + credentials, if a single combined
        # Nexset replaces the per-source Nexsets `search_feeds` reads today.
        self.pipeline_id = pipeline_id
        self.api_key = api_key

    def pull(self):
        """Return a merged feed: {"catalysts": [...], "prices": {...}}.

        Issues exactly one `search_feeds` call (via
        `feeds.search_catalyst_sources`) rather than one per source, to avoid
        multiplying load on the rate-limited Nexla Express API. A source
        reported in `errors` is simply omitted from `catalysts`, not raised.
        """
        outcome = feeds.search_catalyst_sources()
        catalysts = [
            feeds.to_catalyst(result)
            for result in outcome["results"]
            if result.get("source") in _CATALYST_SOURCES
        ]
        prices = feeds.fetch_prices()
        return {
            "catalysts": catalysts,
            "prices": prices,
            "errors": outcome.get("errors") or [],
        }

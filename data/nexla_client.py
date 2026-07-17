"""Nexla data-layer wrapper (SPONSOR stub).

Nexla's pitch is multi-source fusion: it joins the 4 feeds (trials + FDA +
prices + news) into one per-tick context on our contract. This class is the
seam the loop pulls from.
"""

from data import feeds


class NexlaSource:
    def __init__(self, pipeline_id=None, api_key=None):
        # TODO(P2): Nexla pipeline id + credentials
        self.pipeline_id = pipeline_id
        self.api_key = api_key

    def pull(self):
        """Return a merged feed: {"catalysts": [...], "prices": {...}}.

        In production this is one Nexla pipeline output. For now it fans out to
        the local feed adapters so the loop has something to consume.
        """
        # TODO(P2): replace with a single Nexla pipeline pull
        catalysts = []
        catalysts += feeds.fetch_trials()
        catalysts += feeds.fetch_fda()
        catalysts += feeds.fetch_news()
        prices = feeds.fetch_prices()
        return {"catalysts": catalysts, "prices": prices}

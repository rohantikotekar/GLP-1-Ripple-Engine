"""On-demand, query-driven search across the GLP-1 Nexla feeds.

All 4 upstream sources (ClinicalTrials.gov, openFDA, Yahoo finance, pharma
news RSS) are gathered by Nexla per backend/datasources.md; this module never
calls those upstream APIs directly. It only reads live samples Nexla has
already collected, via the org's Nexla "Express API" wrapper
(NEXLA_API_URL) - a hackathon-provided proxy in front of Nexla that exposes
session-bearer auth (POST /login) and read access to nexsets
(GET /nexla/nexsets/{id}), rather than the raw Nexla API.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

# Logical source name -> env var holding that source's Nexset ID.
_NEXSET_ID_ENV_VARS = {
    "clinicaltrials": "NEXLA_NEXSET_ID_CLINICALTRIALS",
    "openfda": "NEXLA_NEXSET_ID_OPENFDA",
    "yahoo": "NEXLA_NEXSET_ID_YAHOO",
    "news": "NEXLA_NEXSET_ID_NEWS",
}

# The pre-joined Nexset that unions all 4 sources into one feed, so callers
# who don't need per-source isolation can read one Nexset instead of 4.
_UNIFIED_NEXSET_ID = 435573

_REQUEST_TIMEOUT = 20

# How long a Nexset read stays cached before we're willing to hit the Express
# API for it again. Nexla only refreshes these Nexsets on its own schedule
# (6h for trials/FDA, 15m for news - see datasources.md), so re-reading more
# often than this just burns rate-limit budget for no fresher data.
_SAMPLES_CACHE_TTL = 30

# One retry on a 429, honoring Retry-After if the Express API sends one.
_RATE_LIMIT_RETRY_DEFAULT_WAIT = 5


class _NexlaConfigError(RuntimeError):
    pass


class _ExpressNexlaClient:
    """Thin client for the Nexla Express API wrapper (login + nexset reads).

    Meant to be built once and reused (see `_get_client()`) rather than
    per-call: it caches both the bearer token and recent Nexset reads, since
    the Express API rate-limits `GET /nexla/nexsets/{id}` on rapid repeated
    calls and a fresh instance per call defeats both caches.
    """

    def __init__(self, base_url: str, service_key: str):
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._token_lock = threading.Lock()
        self._samples_cache: Dict[int, tuple] = {}  # nexset_id -> (fetched_at, samples)
        self._samples_cache_lock = threading.Lock()

    def _ensure_token(self) -> str:
        with self._token_lock:
            if self._access_token and time.time() < self._token_expiry - 30:
                return self._access_token

            response = requests.post(
                f"{self._base_url}/login",
                json={"service_key": self._service_key},
                timeout=_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            # expires_at is an epoch-seconds timestamp from the Express API.
            self._token_expiry = float(data.get("expires_at", time.time() + 3600))
            return self._access_token

    def _get(self, nexset_id: int, token: str) -> requests.Response:
        return requests.get(
            f"{self._base_url}/nexla/nexsets/{nexset_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_REQUEST_TIMEOUT,
        )

    def get_nexset_samples(self, nexset_id: int) -> List[Dict[str, Any]]:
        with self._samples_cache_lock:
            cached = self._samples_cache.get(nexset_id)
            if cached and time.time() - cached[0] < _SAMPLES_CACHE_TTL:
                return cached[1]

        token = self._ensure_token()
        response = self._get(nexset_id, token)

        if response.status_code == 429:
            wait = float(response.headers.get("Retry-After", _RATE_LIMIT_RETRY_DEFAULT_WAIT))
            time.sleep(wait)
            response = self._get(nexset_id, token)

        response.raise_for_status()
        samples = response.json().get("samples", [])

        with self._samples_cache_lock:
            self._samples_cache[nexset_id] = (time.time(), samples)
        return samples


_client_lock = threading.Lock()
_client: Optional[_ExpressNexlaClient] = None


def _build_client() -> _ExpressNexlaClient:
    """Return the shared `_ExpressNexlaClient`, building it once.

    A single long-lived client is what makes the token cache and samples
    cache in `_ExpressNexlaClient` actually do anything - building a fresh
    client per `search_feeds()` call (the old behavior) reset both caches
    every time and re-triggered a `/login` on every call.
    """
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        service_key = os.getenv("NEXLA_SERVICE_KEY")
        base_url = os.getenv("NEXLA_API_URL")
        if not service_key or not base_url:
            raise _NexlaConfigError(
                "Nexla is not configured: set NEXLA_SERVICE_KEY and NEXLA_API_URL "
                "in the environment before calling search_feeds()."
            )
        _client = _ExpressNexlaClient(base_url, service_key)
        return _client


def _resolve_nexset_id(source: str) -> Optional[int]:
    raw_value = os.getenv(_NEXSET_ID_ENV_VARS[source])
    if not raw_value:
        return None
    return int(raw_value)


def _matches_query(record: Dict[str, Any], query: str) -> bool:
    return query.lower() in str(record).lower()


def _text(value: Any) -> Optional[str]:
    """Pull display text out of an RSS-converted-to-JSON node.

    FiercePharma/Endpoints entries render title/creator as either a plain
    string or a nested {"a": {"#text": ...}} link node depending on feed.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "#text" in value:
            return value["#text"]
        if "a" in value:
            return _text(value["a"])
    if isinstance(value, list) and value:
        return _text(value[0])
    return None


def _normalize_shared_schema(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Normalize a record already in the {entity, event_type, event_date,
    source, payload} shared schema (clinicaltrials, openfda, yahoo)."""
    payload = record.get("payload") or {}

    title = record.get("entity") or f"{source} result"
    url = None
    summary = record.get("event_type")

    if source == "clinicaltrials":
        ident = (payload.get("protocolSection") or {}).get("identificationModule") or {}
        title = ident.get("briefTitle") or title
        nct_id = ident.get("nctId")
        url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None
    elif source == "openfda":
        products = payload.get("products") or []
        brand_name = products[0].get("brand_name") if products else None
        title = f"{brand_name} ({record.get('entity')})" if brand_name else title
        application_number = payload.get("application_number")
        summary = f"{record.get('event_type')} — {application_number}" if application_number else summary
    elif source == "yahoo":
        meta = payload.get("meta") or {}
        symbol = meta.get("symbol") or record.get("entity")
        title = f"{symbol} — {meta.get('longName')}" if meta.get("longName") else title
        url = f"https://finance.yahoo.com/quote/{symbol}" if symbol else None

    return {
        "source": source,
        "title": title,
        "summary": summary,
        "url": url,
        "ts": record.get("event_date"),
    }


def _normalize_news(record: Dict[str, Any]) -> Dict[str, Any]:
    item = record.get("item") or record
    return {
        "source": "news",
        "title": _text(item.get("title")) or "News result",
        "summary": _text(item.get("description")),
        "url": item.get("link"),
        "ts": item.get("pubDate"),
    }


def _normalize(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    if source == "news":
        return _normalize_news(record)
    return _normalize_shared_schema(record, source)


def _fetch_and_filter(
    client: _ExpressNexlaClient, source: str, query: str
) -> Dict[str, Any]:
    """Fetch samples for one source's Nexset and filter/normalize matches.

    Returns {"source": source, "results": [...]} or {"source": source, "error": "..."}.
    """
    try:
        nexset_id = _resolve_nexset_id(source)
        if nexset_id is None:
            raise _NexlaConfigError(
                f"{_NEXSET_ID_ENV_VARS[source]} is not set; "
                f"the {source} Nexset is not configured."
            )

        samples = client.get_nexset_samples(nexset_id)
        results = [
            _normalize(sample, source)
            for sample in samples
            if _matches_query(sample, query)
        ]
        return {"source": source, "results": results}
    except Exception as exc:  # noqa: BLE001 - isolate any per-source failure
        return {"source": source, "error": str(exc)}


def search_feeds(query: str) -> Dict[str, Any]:
    """Search the 4 GLP-1 Nexla-managed feeds for records matching `query`.

    All data comes from Nexla's already-collected Nexset samples -
    ClinicalTrials.gov, openFDA, Yahoo finance, and pharma news RSS are never
    called directly. Returns a JSON-serializable dict:
        {"results": [...], "errors": [{"source": ..., "reason": ...}, ...]}
    """
    client = _build_client()
    sources = list(_NEXSET_ID_ENV_VARS.keys())

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = [
            executor.submit(_fetch_and_filter, client, source, query)
            for source in sources
        ]
        for future in futures:
            outcome = future.result()
            if "error" in outcome:
                errors.append({"source": outcome["source"], "reason": outcome["error"]})
            else:
                results.extend(outcome["results"])

    return {"results": results, "errors": errors}


def search_unified_feed(query: str) -> Dict[str, Any]:
    """Search the single pre-joined Nexset (ID 435573) that unions all 4
    sources, instead of fanning out to per-source Nexsets.

    One request instead of 4 - use this over `search_feeds` when per-source
    error isolation isn't needed and avoiding extra load on the rate-limited
    Express API matters more. Each record is normalized using its own
    `source` field (clinicaltrials/openfda/yahoo/news), same as `search_feeds`.
    Returns a JSON-serializable dict:
        {"results": [...], "errors": [{"source": "union", "reason": ...}, ...]}
    """
    client = _build_client()

    try:
        samples = client.get_nexset_samples(_UNIFIED_NEXSET_ID)
        results = [
            _normalize(sample, sample.get("source"))
            for sample in samples
            if _matches_query(sample, query)
        ]
        return {"results": results, "errors": []}
    except Exception as exc:  # noqa: BLE001 - isolate failure like search_feeds does per-source
        return {"results": [], "errors": [{"source": "union", "reason": str(exc)}]}

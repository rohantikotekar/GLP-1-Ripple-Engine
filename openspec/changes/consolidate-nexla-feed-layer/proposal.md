## Why

`backend/feed_search.py` is the real, working Nexla Express API client (`search_feeds(query)`, used today by `backend/test.py`). Meanwhile `data/nexla_client.py` (`NexlaSource.pull()`) and `data/feeds.py` are an earlier stub scaffold — `fetch_trials`/`fetch_fda`/`fetch_news` all return `[]` — that nothing in the loop actually calls yet. Having two parallel, disconnected implementations of "get feed data from Nexla" is confusing and means the loop (`loop/engine.py` via `loop/server.py`'s `/inject`) has no real path to live catalyst data at all. We need one real data-gathering implementation, with the loop-facing shape built on top of it instead of duplicating it.

## What Changes

- Replace the stub bodies of `data/feeds.py` (`fetch_trials`, `fetch_fda`, `fetch_news`) with calls into `backend/feed_search.py`'s `search_feeds`, so they return real Nexla-sourced records instead of `[]`. `fetch_prices` is unchanged (already real, via `yfinance`).
- Update `data/nexla_client.py`'s `NexlaSource.pull()` to reshape `search_feeds` output into the existing `{"catalysts": [...], "prices": {...}}` contract the loop expects, normalizing each result into the catalyst-candidate shape (`headline`, `source`, `type`, `ticker_primary`, `phase`, `resolved`) described in `data/feeds.py`'s module docstring.
- `backend/feed_search.py` remains unchanged as the sole real Nexla Express API client (source of truth) — `data/feeds.py`/`data/nexla_client.py` become a thin adapter layer on top of it, not a competing implementation.
- `data/injector.py` is unchanged — it remains a separate demo-catalyst CLI that POSTs directly to `/inject`, independent of the live-feed path.
- `backend/test.py` continues to call `search_feeds` directly and is unaffected.

## Capabilities

### New Capabilities
- `loop-feed-adapter`: Adapts Nexla-backed feed search results (`backend/feed_search.py`) into the catalyst-candidate + price contract (`data/nexla_client.py`'s `NexlaSource.pull()`) that the loop engine consumes.

### Modified Capabilities
(none — `feed-search` has no synced spec in `openspec/specs/` yet, and `search_feeds`'s behavior/contract is not changing)

## Impact

- Modified code: `data/feeds.py`, `data/nexla_client.py`.
- Unchanged: `backend/feed_search.py`, `backend/test.py`, `data/injector.py`, `loop/*`.
- New dependency: `data/feeds.py` now imports `backend/feed_search.py` (cross-package import — `backend/` and `data/` currently have no shared package root, so this needs an import-path fix, e.g. adding `backend` to the path or restructuring as proper packages; see design.md).
- Config: no new env vars — reuses `NEXLA_SERVICE_KEY`, `NEXLA_API_URL`, and the 4 `NEXLA_NEXSET_ID_*` vars already required by `backend/feed_search.py`.

## Context

`backend/feed_search.py::search_feeds(query)` fetches **all 4** Nexla nexsets (clinicaltrials, openfda, yahoo, news) in one parallel call and returns a combined, query-filtered `{"results": [...], "errors": [...]}`. `data/feeds.py` currently exposes 4 separate parameterless functions (`fetch_trials`, `fetch_fda`, `fetch_prices`, `fetch_news`) that `data/nexla_client.py::NexlaSource.pull()` calls independently and concatenates into `{"catalysts": [...], "prices": {...}}` — the shape `loop/engine.py` expects for `state["catalyst"]`. `backend/` has no `__init__.py` (implicit namespace package); `data/` does. We just diagnosed a live 429 from Nexla's Express API proxy on repeated nexset reads, so redundant calls to `search_feeds` are a real, not theoretical, cost.

## Goals / Non-Goals

**Goals:**
- One real implementation of "talk to Nexla" (`backend/feed_search.py`), with `data/` adapting its output into the loop's catalyst contract.
- `NexlaSource.pull()` issues exactly one `search_feeds` call per `pull()` invocation, not one per source.
- Preserve the existing `data/feeds.py` function signatures (`fetch_trials()`, `fetch_fda()`, `fetch_prices()`, `fetch_news()`) so any future direct caller isn't surprised, but make them thin.

**Non-Goals:**
- Not touching `data/injector.py` or the `/inject` HTTP contract.
- Not changing `backend/feed_search.py`'s behavior or its `search_feeds` return shape.
- Not adding caching/scheduling beyond what's needed to avoid the redundant-call problem within a single `pull()`.
- Not solving Nexla's own rate limit server-side (no retry/backoff added here — separate concern).

## Decisions

**1. Single shared fetch inside `pull()`, not one `search_feeds` call per `fetch_*` function.**
`NexlaSource.pull()` calls `search_feeds("")` once (empty query matches every record, since `_matches_query` does a substring check against `""`), then splits `results` by the `source` field (`"clinicaltrials"`, `"openfda"`, `"news"`) locally. `fetch_trials()`/`fetch_fda()`/`fetch_news()` become optional standalone helpers that each call `search_feeds("")` and filter to their one source — fine for ad-hoc/manual use, but `pull()` does NOT call them, to avoid 4x-ing the Nexla Express API load that's already hitting 429s. Alternative considered: have `pull()` call the 3 `fetch_*` functions as before — rejected because it triples the request volume against an endpoint we've already seen rate-limited.

**2. Catalyst-shape mapping is best-effort, done in `nexla_client.py`.**
`search_feeds`'s normalized shape (`source`, `title`, `summary`, `url`, `ts`) doesn't carry `type`, `phase`, `ticker_primary`, or `resolved` — those are catalyst-contract fields specific to the loop, not the search layer. `NexlaSource.pull()` derives them:
- `ticker_primary`: match `data/feeds.py::TICKERS` against `title`/`summary` text (case-insensitive substring); `""` if no match.
- `type`: a fixed per-source default (`"trial_update"` for clinicaltrials, `"regulatory_update"` for openfda, `"news_mention"` for news) — coarser than `loop/model.py`'s classifier, which is expected to refine it downstream (`loop/engine.py` already calls `model.classify(catalyst)` after ingestion).
- `phase`: pulled from `summary` via a simple `"Phase N"` regex if present, else `None`.
- `resolved`: `False` (Nexla search results are point-in-time observations, not resolution events).
- `headline`: `title`.
Alternative considered: extend `backend/feed_search.py`'s normalization to include these fields — rejected because `type`/`phase`/`ticker_primary` are loop-specific concerns, not properties of "search results," and `feed_search.py` is also used standalone by `backend/test.py` where they'd be dead weight.

**3. Cross-package import via namespace package, no `__init__.py` added to `backend/`.**
`data/feeds.py` adds `from backend import feed_search`. This works as an implicit namespace-package import as long as the repo root is on `sys.path`, which holds for the existing entry points (`python -m data.injector` from repo root, `uvicorn loop.server:app` from repo root). No `sys.path` manipulation added. Risk noted below.

## Risks / Trade-offs

- [Repo root not on `sys.path` in some deployment path] → document that `data/feeds.py` must be imported with the repo root as CWD/on `PYTHONPATH`; matches current convention (`infra/Dockerfile` should be checked to confirm it sets `WORKDIR` to repo root — flagged in tasks).
- [`search_feeds("")` still fetches all 4 nexsets even when only 3 are needed for catalysts] → acceptable: this is already what `search_feeds` does internally (single combined fetch), and it's strictly fewer calls than today's 3-independent-`fetch_*` design once `pull()` is centralized.
- [Best-effort `type`/`phase`/`ticker_primary` extraction may misclassify] → acceptable for this stage since `loop/engine.py` already re-classifies via `model.classify(catalyst)` and validates via `gate.verify(catalyst)` before acting on it.
- [`fetch_prices()` untouched, still best-effort yfinance] → no change in behavior or risk profile.

## Migration Plan

1. Update `data/feeds.py`: implement `fetch_trials`/`fetch_fda`/`fetch_news` as thin single-source `search_feeds("")` filters (standalone use only).
2. Update `data/nexla_client.py`: `NexlaSource.pull()` calls `search_feeds("")` once, splits by source, maps to catalyst shape, keeps `fetch_prices()` for the `prices` half.
3. Manually verify `NexlaSource().pull()` returns non-empty `catalysts` when Nexla env vars are configured (reuse `backend/.env` already used by `backend/test.py`).
4. No rollback complexity — this only changes two files behind an interface (`pull()`) that nothing currently calls in production, so it can be reverted by `git revert` with no data migration.

## Open Questions

- Should `pull()`'s per-source `type` defaults live in `data/feeds.py` (module-level constant) or inline in `nexla_client.py`? Leaning inline since `nexla_client.py` owns the catalyst-shaping concern per decision 2 — left to implementation.

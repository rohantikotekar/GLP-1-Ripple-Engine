## 1. Cross-package import

- [x] 1.1 Confirmed `backend/` is importable as `from backend import feed_search` from repo root (namespace package, no `__init__.py` needed). Found `infra/Dockerfile` never copied `backend/` into the image at all — fixed by adding `COPY backend ./backend`.

## 2. `data/feeds.py`

- [x] 2.1 Added `search_catalyst_sources()` helper that calls `backend.feed_search.search_feeds("")` and returns its `results`/`errors`.
- [x] 2.2 Implemented `fetch_trials()`, `fetch_fda()`, `fetch_news()` as thin filters over that helper's `results`, keyed by `source in {"clinicaltrials", "openfda", "news"}`, mapped via the shared `to_catalyst()` function.
- [x] 2.3 `fetch_prices()` unchanged.
- [x] 2.4 Updated the module docstring — no longer framed as stubs.

## 3. `data/nexla_client.py`

- [x] 3.1 `NexlaSource.pull()` now calls `feeds.search_catalyst_sources()` (single `search_feeds("")` call) exactly once and splits `results` by `source`.
- [x] 3.2 Implemented the shared catalyst-mapping logic as `feeds.to_catalyst()` (ticker inference, per-source `type` default, `"Phase N"` regex, `resolved=False`, `headline=title`), used by both `pull()` and the standalone `fetch_*` functions. Placed in `feeds.py` rather than `nexla_client.py` (deviating from design.md's lean default) to avoid a circular import between the two modules.
- [x] 3.3 `prices` still populated via `feeds.fetch_prices()`, unchanged.
- [x] 3.4 A `search_feeds` error for one source is simply absent from `results`/only in `errors`; `pull()` never inspects `errors`, so it can't raise on a per-source failure — it just yields fewer catalysts.
- [x] 3.5 Updated the module docstring; removed the stale "replace with a single Nexla pipeline pull" TODO now that `pull()` is wired to the real client.

## 4. Verification

- [x] 4.1 Ran `NexlaSource().pull()` with `backend/.env` credentials: returned 10 non-empty `catalysts` across clinicaltrials/openfda sources. `prices` came back `{}` — traced to `yfinance` not being installed in this environment (pre-existing gap, `fetch_prices()` is unchanged and already had this silent fallback; not a regression from this change).
- [x] 4.2 Pointed `NEXLA_NEXSET_ID_OPENFDA` at an invalid ID and re-ran: `pull()` returned only `clinicaltrials`/`news` catalysts (10 total), no exception raised.
- [x] 4.3 Ran `backend/test.py` directly: still returns the combined `search_feeds` results/errors unchanged (including a live 429 on the yahoo/news nexsets from the ongoing rate-limit issue — unrelated to this change, `search_feeds` itself untouched).
- [x] 4.4 Verified by inspection: `data/injector.py` imports only `argparse`, `time`, `httpx` — no dependency on `data.feeds`/`data.nexla_client`, so it and `loop/server.py`'s `/inject` route are unaffected by this change.

## 1. Nexla provisioning check

- [x] 1.1 Confirm the 4 GLP-1 sources from `backend/datasources.md` §1-4 are provisioned as Nexla sources/Nexsets in the target org — confirmed live via `GET /nexla/nexsets/{id}`, all 4 return `status: ACTIVE` with real samples
- [x] 1.2 Record the 4 Nexset IDs for use as config — `435571` (clinicaltrials), `435565` (openfda), `435564` (yahoo), `435570` (news), stored in `backend/.env`

## 2. Module scaffold and config

- [x] 2.1 Create `backend/feed_search.py`. Note: originally planned to use `nexla_sdk.NexlaClient`, but live testing showed this org's `NEXLA_API_URL` is a custom "Express API" wrapper (`POST /login`, `GET /nexla/nexsets/{id}`), not the raw Nexla API the SDK targets — implemented a small `requests`-based `_ExpressNexlaClient` instead (see design.md)
- [x] 2.2 Add env-based config for `NEXLA_SERVICE_KEY` / `NEXLA_API_URL` and the 4 Nexset IDs (`NEXLA_NEXSET_ID_CLINICALTRIALS`, `NEXLA_NEXSET_ID_OPENFDA`, `NEXLA_NEXSET_ID_YAHOO`, `NEXLA_NEXSET_ID_NEWS`), documented in `backend/.env`
- [x] 2.3 Raise a clear configuration error if `NEXLA_SERVICE_KEY`/`NEXLA_API_URL` is missing, before any Nexset calls are attempted

## 3. Per-source Nexset query and normalization

- [x] 3.1 Implement a shared `_fetch_and_filter(client, source, query)` helper that calls `client.get_nexset_samples(nexset_id)` (via `GET /nexla/nexsets/{id}`) and filters records by case-insensitive substring match against the stringified sample
- [x] 3.2 Implement per-source normalization into `{source, title, summary, url, ts}` for each of `"clinicaltrials"`, `"openfda"`, `"yahoo"` (shared `{entity, event_type, event_date, source, payload}` schema) and `"news"` (raw RSS-as-JSON `item` shape, handled separately since that Nexset isn't normalized yet)
- [x] 3.3 Catch and isolate per-Nexset exceptions (auth, timeout, not-found, rate limit, malformed sample) into an `errors` list entry (`{source, reason}`) instead of propagating

## 4. Fan-out and aggregation

- [x] 4.1 Implement `search_feeds(query: str) -> dict` using `concurrent.futures.ThreadPoolExecutor` to run the 4 `_fetch_and_filter` calls in parallel against a single shared `_ExpressNexlaClient` instance
- [x] 4.2 Merge successful per-source results into a single `results` list matching the normalized schema
- [x] 4.3 Verify the full return value round-trips through `json.dumps`/`json.loads` with no custom encoder

## 5. Validation

- [x] 5.1 Manually run `search_feeds("semaglutide")`, `search_feeds("NVO")`, `search_feeds("FDA")`, `search_feeds("Novo")` against the real Nexla org — confirmed non-empty, correctly normalized `results` from clinicaltrials, openfda, and news sources (yahoo hit the Express API's rate limit during rapid back-to-back test calls, which was correctly isolated into `errors` rather than failing the whole search)
- [x] 5.2 Simulate a missing/misconfigured Nexset ID and confirm it lands in `errors` without raising
- [x] 5.3 Confirm behavior when `NEXLA_SERVICE_KEY` is unset (should raise a clear config error, not an opaque SDK exception)

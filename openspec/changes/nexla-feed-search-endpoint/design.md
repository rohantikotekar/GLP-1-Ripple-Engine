## Context

`backend/datasources.md` documents 4 GLP-1-relevant feeds wired into Nexla as scheduled-pull sources: ClinicalTrials.gov v2, openFDA `drugsfda`, Yahoo finance chart (via the undocumented endpoint `yfinance` wraps), and pharma news RSS (FiercePharma, Endpoints News). Per §5, each lands as a raw Nexset, gets normalized by a transform Nexset to a shared schema (`{entity, event_type, event_date, source, payload}`), and can optionally be unioned into one combined Nexset. Nexla — not this function — owns talking to the 4 upstream APIs.

The ripple-engine agent loop needs a synchronous, query-driven way to search what Nexla currently has on demand — e.g. when a catalyst is detected and the agent wants to check "has anything new happened with semaglutide" right now.

**Correction discovered during implementation:** this org does not expose the raw Nexla API that `nexla-sdk` targets (`https://dataops.nexla.io/nexla-api`, `/token` auth). Instead, `NEXLA_API_URL` points at a hackathon-provided "Express API" wrapper in front of Nexla (`GET /openapi.json` confirms `info.title: "Express API"`), with its own auth (`POST /login` with `{service_key}` → bearer `access_token`) and a `GET /nexla/nexsets/{id}` endpoint that returns `{..., samples: [...], output_schema: {...}}`. `search_feeds` is built as a thin `requests`-based client against this wrapper, not against `nexla_sdk.NexlaClient`. Confirmed live: all 4 Nexset IDs resolve, return `status: ACTIVE`, and return real samples matching the shared schema from `datasources.md` §5.

This is a hackathon project (`requirements.txt` has `nexla-sdk`, `requests`, `pydantic`) — favor a small, dependency-light, single-file implementation over a service framework.

## Goals / Non-Goals

**Goals:**
- One Python function, `search_feeds(query: str) -> dict`, that fans out to the 4 Nexla Nexsets (via `nexla_sdk.NexlaClient`) and filters each Nexset's samples against the query, returning one normalized JSON-serializable result.
- All external data access goes through Nexla — the function never calls ClinicalTrials.gov, openFDA, Yahoo, or the RSS feeds directly.
- Isolate failures per Nexset: an auth error, timeout, or empty/paused Nexset from one feed shows up as an error entry for that source, not an exception that kills the whole call.
- Keep it callable directly (for the "just a python function" ask) and trivially wrappable behind a web framework (Flask/FastAPI) later — no framework-specific request/response objects inside the core function.

**Non-Goals:**
- No actual HTTP server/route registration in this change — that's explicitly deferred ("right now, just a python function").
- No caching, rate-limit backoff, or persistence of search results beyond what Nexla itself does.
- No changes to the existing Nexla scheduled-source configs in `datasources.md` — this change assumes those 4 sources/Nexsets are already (or will be) provisioned in Nexla; it only adds a read/search layer on top.
- No relevance ranking/scoring beyond simple per-record query matching — results are returned as-is per Nexset, not merged/re-ranked.

## Decisions

**All feed access goes through Nexla (via the org's Express API wrapper), not direct HTTP to the 4 upstream APIs.**
The user asked specifically for Nexla to gather this data. Nexla already owns the schedules, auth, and normalization for these 4 sources (`datasources.md` §5); duplicating that with a second, hand-rolled HTTP client per source would fork the data path and drift from what Nexla actually has. `search_feeds` calls `GET /nexla/nexsets/{id}` on the Express wrapper for each of the 4 source Nexsets and filters the returned `samples`. Alternative considered and rejected: keep the earlier design of calling ClinicalTrials.gov/openFDA/Yahoo/RSS directly with `requests` — this bypasses Nexla entirely, which is the opposite of what was asked.

**A small hand-rolled `requests` client against the Express API, not `nexla_sdk.NexlaClient`.**
Originally planned to use `nexla-sdk` (already in `requirements.txt`), since it's the standard way to talk to Nexla. Live testing showed `NEXLA_API_URL` for this org (`https://dev-api-express-code.nexla.com`) is not the raw Nexla API the SDK expects — `NexlaClient`'s `/token` auth call 404s against it. Inspecting `/openapi.json` on that host revealed a custom "Express API" wrapper with its own auth (`POST /login` → bearer token) and a read endpoint (`GET /nexla/nexsets/{id}` → `{samples: [...], output_schema: {...}}`). `_ExpressNexlaClient` in `feed_search.py` is a ~40-line client for exactly these two calls — `requests` was already a transitive dependency and no new package was needed. `nexla-sdk` remains in `requirements.txt` but is unused by this module; worth revisiting if this org ever exposes the raw Nexla API instead of/alongside the Express wrapper.

**Fan-out via `concurrent.futures.ThreadPoolExecutor`, not `asyncio`.**
The 4 Nexset reads are independent blocking HTTP requests. A thread pool keeps `search_feeds` itself synchronous (`def`, not `async def`) so it's a plain callable usable from any context (script, notebook, sync web framework), while still running the 4 lookups in parallel instead of serially.

**Nexset IDs and credentials are external configuration, not hardcoded.**
The function reads a mapping of logical source name → Nexset ID (`NEXLA_NEXSET_ID_CLINICALTRIALS`, `NEXLA_NEXSET_ID_OPENFDA`, `NEXLA_NEXSET_ID_YAHOO`, `NEXLA_NEXSET_ID_NEWS`) plus `NEXLA_SERVICE_KEY`/`NEXLA_API_URL` from the environment (`backend/.env`, gitignored). Confirmed live: all 4 IDs resolve to `status: ACTIVE` Nexsets in the org.

**Query filtering happens client-side, over whatever schema each Nexset actually returns.**
The Express wrapper's nexset endpoint returns recent samples, not a text-search API. `search_feeds` matches the query as a case-insensitive substring against the stringified sample. In practice 3 of the 4 Nexsets (clinicaltrials, openfda, yahoo) already conform to the `{entity, event_type, event_date, source, payload}` shared schema from `datasources.md` §5; the news Nexset returns unnormalized RSS-as-JSON (`{item: {title, link, pubDate, description, ...}}`) — its normalizer hasn't been applied to that Nexset. `_normalize()` branches on source: shared-schema sources use `entity`/`event_type`/`event_date`/`payload`, `news` extracts from the raw RSS `item` shape (title text can be a plain string or a `{"a": {"#text": ...}}` link node depending on feed, handled by the `_text()` helper).

**Normalized result shape.**
Every matched Nexset record is mapped into `{source, title, summary, url, ts}` so the caller gets one flat `results` list plus an `errors` list for failed Nexsets, rather than 4 differently-shaped payloads.

**Timeouts and error isolation.**
Each HTTP call (`login`, per-Nexset `get`) has a 20s timeout. All exceptions per source — auth failure, timeout, 404/429/5xx, missing Nexset ID config — are caught in `_fetch_and_filter` and recorded in `errors`, not raised. Confirmed live: a 429 from the Express API on one Nexset during rapid testing showed up as an isolated error while the other 3 sources still returned results.

## Risks / Trade-offs

- ["On demand" is bounded by Nexla's own schedule] → Nexla still pulls the 4 upstream sources on the schedules in `datasources.md` (every 6h / 15m poll); `search_feeds` searches whatever Nexla currently has, it does not force Nexla to re-poll an upstream API synchronously. The Express wrapper's `/nexla/nexsets/{id}` endpoint has no "run now"/sync-trigger. Mitigation: document this bound clearly to callers, and rely on the existing 15m (news) / 6h (trials, FDA) schedules being fresh enough for the agent's use case.
- [Nexset endpoint is not a search API] → It returns recent samples, not query-matched ones; client-side substring filtering is a rough relevance signal only, acceptable for hackathon scope.
- [Express API rate-limits per Nexset] → Confirmed live: rapid successive calls to `GET /nexla/nexsets/{id}` return `429 Too Many Requests`. Already isolated per-source into `errors` rather than failing the whole search, but callers issuing `search_feeds` in a tight loop should expect occasional single-source 429s. No retry/backoff implemented yet — acceptable for hackathon scope, worth adding if the agent loop calls this frequently.
- [News Nexset isn't normalized to the shared schema] → Confirmed live: `clinicaltrials`/`openfda`/`yahoo` Nexsets return `{entity, event_type, event_date, source, payload}` per §5, but the `news` Nexset returns raw RSS-as-JSON. `_normalize()` handles this with a source-specific branch; if the news Nexset is later normalized upstream in Nexla, `_normalize_news` will need updating (or removing) to match.
- [Yahoo chart endpoint is undocumented/unofficial per `datasources.md` §3] → Already flagged upstream at the source-config level; once ingested into Nexla, `search_feeds` treats a stale/missing Yahoo Nexset the same as any other per-source failure (isolated, doesn't block the other 3).
- [openFDA "new indication" has no clean boolean field] → Documented in `datasources.md` §2; unaffected by routing through Nexla — the ambiguity lives in the source data, not in how it's fetched.

## Migration Plan

Additive only — new file (`backend/feed_search.py`), no changes to existing code. Requires `NEXLA_SERVICE_KEY`, `NEXLA_API_URL`, and the 4 Nexset ID env vars in `backend/.env` (confirmed present and working against the live org). No rollback concerns beyond removing the new file.

## Open Questions

- Should `search_feeds` cache/reuse the Express API bearer token across calls (currently re-logs-in whenever the cached token is near expiry, scoped to one client instance per `search_feeds()` call)? Fine for hackathon call volume; revisit if this becomes a hot path.
- When this is wrapped as an actual HTTP endpoint (future change), which framework (Flask vs FastAPI) and auth model will Nexla's "request" trigger use to call it?

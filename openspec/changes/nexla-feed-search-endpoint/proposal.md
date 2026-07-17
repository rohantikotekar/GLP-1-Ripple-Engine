## Why

Nexla is the system of record for the 4 GLP-1 data feeds (ClinicalTrials.gov, openFDA, Yahoo market prices, pharma news RSS) per `backend/datasources.md` — each is (or will be) configured as a Nexla source feeding a normalized Nexset. Today there's no way for an agent to ask Nexla, on demand, "what do you currently have that matches this query" (e.g. "semaglutide phase 3" or "Novo Nordisk approval"). We need a query-driven search entry point, built on the `nexla-sdk` already in `requirements.txt`, so the ripple-engine agent loop pulls fresh Nexla-managed data instead of talking to the 4 upstream APIs directly and instead of waiting for someone to eyeball the Nexla UI.

## What Changes

- Add a `search_feeds(query: str)` Python function that uses `nexla_sdk.NexlaClient` to fetch live samples from the 4 GLP-1 Nexsets configured in Nexla (per `datasources.md` §5: ClinicalTrials, openFDA, Yahoo, news, each normalized to `{entity, event_type, event_date, source, payload}` or optionally one combined Nexset) — in parallel — and filters each Nexset's returned records against the query string.
- Nexla is the sole data-gathering layer: the function does **not** call ClinicalTrials.gov, openFDA, Yahoo, or the RSS feeds directly — it always goes through Nexla's `/data_sets/{id}/samples` (nexset samples) API via the SDK.
- Normalize each Nexset's matched records into a shared result shape (`source`, `title`, `summary`, `url`/`id`, `ts`) and return one combined JSON payload.
- Handle per-Nexset failures gracefully (auth errors, timeouts, empty/paused Nexsets) so one broken feed doesn't fail the whole search.
- No persistence layer yet — this is a synchronous fetch-and-return function, callable directly or wrapped by an HTTP framework later.

## Capabilities

### New Capabilities
- `feed-search`: On-demand, query-driven search across the 4 configured GLP-1 data feeds **via Nexla**, returning normalized JSON results.

### Modified Capabilities
(none — no existing specs)

## Impact

- New code: `backend/feed_search.py` implementing `search_feeds`, built on a small `requests`-based client against the org's Nexla "Express API" wrapper (`NEXLA_API_URL`) — not the raw Nexla API, and not `nexla-sdk` (present in `requirements.txt` but unused here; see design.md for why).
- Dependencies: `requests` only (already a transitive dependency via `nexla-sdk`); no direct HTTP calls to the upstream APIs.
- Required config (now confirmed live and working): `NEXLA_SERVICE_KEY`, `NEXLA_API_URL`, and the 4 Nexset IDs (`NEXLA_NEXSET_ID_CLINICALTRIALS`, `NEXLA_NEXSET_ID_OPENFDA`, `NEXLA_NEXSET_ID_YAHOO`, `NEXLA_NEXSET_ID_NEWS`) in `backend/.env`.
- The 4 sources in `backend/datasources.md` are confirmed provisioned and `ACTIVE` in the Nexla org — this change only adds a read/search layer on top, it does not change the source configs.

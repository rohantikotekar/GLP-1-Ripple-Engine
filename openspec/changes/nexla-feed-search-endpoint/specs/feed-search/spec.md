## ADDED Requirements

### Requirement: Query-driven multi-source search via Nexla
The system SHALL provide a `search_feeds(query: str) -> dict` function that retrieves data for the 4 GLP-1 sources (ClinicalTrials.gov, openFDA `drugsfda`, Yahoo finance chart, pharma news RSS) exclusively through Nexla — reading samples from the corresponding Nexla Nexset(s) via the org's Nexla API access (currently a Nexla "Express API" wrapper exposing session-bearer auth and per-Nexset reads) — filters the retrieved records against the given query string, and returns a single combined result. The function SHALL NOT issue direct HTTP requests to ClinicalTrials.gov, openFDA, Yahoo, or the RSS feed URLs.

#### Scenario: Query matches results across all sources
- **WHEN** `search_feeds("semaglutide")` is called
- **THEN** the function fetches samples from each of the 4 configured Nexsets via the Nexla API, filters them against the query, and returns a dict containing a `results` list with normalized entries from each Nexset that returned matching data

#### Scenario: Empty or no-match query
- **WHEN** `search_feeds` is called with a query that matches no records in any Nexset
- **THEN** the function returns a dict with an empty `results` list and no unhandled exception is raised

#### Scenario: Nexset not provisioned
- **WHEN** one of the 4 expected Nexset IDs is not configured or does not exist in the Nexla org
- **THEN** the function SHALL record an error for that source in `errors` and continue querying the remaining Nexsets, rather than raising

### Requirement: Nexla connection configuration
The system SHALL read Nexla API credentials (service key / API URL) and the 4 source Nexset IDs (or a single combined Nexset ID) from environment configuration, and SHALL NOT hardcode Nexla org-specific IDs or secrets in source code.

#### Scenario: Missing Nexla credentials
- **WHEN** `search_feeds` is called without `NEXLA_SERVICE_KEY` (or equivalent) configured in the environment
- **THEN** the function SHALL raise a clear configuration error before attempting any Nexset lookups, rather than failing with an opaque SDK/auth exception per source

### Requirement: Normalized result schema
Each entry in the `results` list SHALL be normalized to the fields `source`, `title`, `summary`, `url`, and `ts`, regardless of which of the 4 feeds' Nexset it came from.

#### Scenario: ClinicalTrials.gov result normalization
- **WHEN** a ClinicalTrials.gov-sourced Nexset record matches the query
- **THEN** the corresponding result entry SHALL have `source` set to `"clinicaltrials"`, `title` derived from the record's condition/phase fields, and `url` pointing to the study record

#### Scenario: openFDA result normalization
- **WHEN** an openFDA-sourced Nexset record matches the query
- **THEN** the corresponding result entry SHALL have `source` set to `"openfda"` and `title`/`summary` derived from sponsor, brand name, and submission fields

#### Scenario: Yahoo price result normalization
- **WHEN** a Yahoo-sourced Nexset record matches the query
- **THEN** the corresponding result entry SHALL have `source` set to `"yahoo"` and `summary` containing the latest price/interval data

#### Scenario: RSS news result normalization
- **WHEN** a news-sourced Nexset record's title or summary matches the query (case-insensitive substring)
- **THEN** the corresponding result entry SHALL have `source` set to `"news"` and `url` set to the entry's link

### Requirement: Per-source failure isolation
The system SHALL isolate failures (auth errors, timeouts, paused/empty Nexsets, malformed samples) to the individual Nexset that failed, without raising an exception from `search_feeds` or omitting results from the other sources.

#### Scenario: One Nexset lookup times out
- **WHEN** the `get_samples` call for the Yahoo-sourced Nexset times out or the SDK raises an error during a call to `search_feeds`
- **THEN** the returned dict SHALL include an `errors` list with an entry identifying `"yahoo"` and the failure reason, while `results` still contains any successful entries from the other 3 sources

#### Scenario: All Nexset lookups fail
- **WHEN** all 4 Nexset lookups fail (e.g. Nexla API unreachable)
- **THEN** `search_feeds` SHALL return a dict with an empty `results` list and 4 entries in `errors`, rather than raising

### Requirement: JSON-serializable output
The dict returned by `search_feeds` SHALL be directly serializable via `json.dumps` with no additional transformation, so it can be returned as-is by an HTTP endpoint wrapper.

#### Scenario: Output serialization
- **WHEN** the return value of `search_feeds("tirzepatide")` is passed to `json.dumps`
- **THEN** serialization SHALL succeed without a `TypeError` or custom encoder

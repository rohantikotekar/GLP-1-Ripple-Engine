## ADDED Requirements

### Requirement: Single combined Nexla fetch per pull
`NexlaSource.pull()` SHALL retrieve data for all 3 catalyst-bearing sources (clinicaltrials, openfda, news) via exactly one call to `backend.feed_search.search_feeds`, rather than one call per source.

#### Scenario: pull() issues one search_feeds call
- **WHEN** `NexlaSource().pull()` is invoked
- **THEN** `backend.feed_search.search_feeds` is called exactly once, and the returned `results` are split by their `source` field to build the catalyst list

### Requirement: Catalyst contract mapping
`NexlaSource.pull()` SHALL map each `search_feeds` result (for clinicaltrials, openfda, and news sources) into the catalyst-candidate shape `{"headline": str, "source": str, "type": str, "ticker_primary": str, "phase": str | None, "resolved": bool}` before returning it in the `catalysts` list.

#### Scenario: Mapping a clinicaltrials result
- **WHEN** a `search_feeds` result has `source == "clinicaltrials"`
- **THEN** the mapped catalyst SHALL have `headline` set from the result's `title`, `type` set to `"trial_update"`, and `resolved` set to `False`

#### Scenario: Mapping an openfda result
- **WHEN** a `search_feeds` result has `source == "openfda"`
- **THEN** the mapped catalyst SHALL have `headline` set from the result's `title`, `type` set to `"regulatory_update"`, and `resolved` set to `False`

#### Scenario: Mapping a news result
- **WHEN** a `search_feeds` result has `source == "news"`
- **THEN** the mapped catalyst SHALL have `headline` set from the result's `title`, `type` set to `"news_mention"`, and `resolved` set to `False`

#### Scenario: Ticker inference from text
- **WHEN** a mapped result's `title` or `summary` contains one of `data.feeds.TICKERS` as a case-insensitive substring
- **THEN** the mapped catalyst's `ticker_primary` SHALL be set to that ticker; otherwise `ticker_primary` SHALL be `""`

#### Scenario: Phase extraction
- **WHEN** a mapped result's `summary` contains a `"Phase N"` pattern
- **THEN** the mapped catalyst's `phase` SHALL be set to the matched `"Phase N"` string; otherwise `phase` SHALL be `None`

### Requirement: Standalone fetch_* functions remain single-source
`data.feeds.fetch_trials()`, `fetch_fda()`, and `fetch_news()` SHALL each remain independently callable, filtering `search_feeds("")` results down to their own source, for callers that don't go through `NexlaSource.pull()`.

#### Scenario: Calling fetch_trials directly
- **WHEN** `fetch_trials()` is called
- **THEN** it returns only catalyst-candidate entries derived from `search_feeds` results with `source == "clinicaltrials"`

### Requirement: Nexla failure isolation preserved through the adapter
If `search_feeds` reports an error for a given source (via its `errors` list), `NexlaSource.pull()` SHALL omit that source's catalysts from the result without raising, while still returning catalysts from unaffected sources and the `prices` dict from `fetch_prices()`.

#### Scenario: One source errors during pull
- **WHEN** `search_feeds`'s `errors` list contains an entry for `"openfda"` (e.g. a 429 from the Nexla Express API)
- **THEN** `NexlaSource.pull()` SHALL return a `catalysts` list containing entries from `clinicaltrials` and `news` (if present) and no entries for `openfda`, and SHALL NOT raise an exception

### Requirement: Prices unaffected
`NexlaSource.pull()` SHALL continue to populate `prices` via `data.feeds.fetch_prices()`, unchanged from current behavior.

#### Scenario: pull() returns prices alongside catalysts
- **WHEN** `NexlaSource().pull()` is invoked and `yfinance` is reachable
- **THEN** the returned dict's `prices` key SHALL contain the same `{ticker: last_price}` mapping `fetch_prices()` would return on its own

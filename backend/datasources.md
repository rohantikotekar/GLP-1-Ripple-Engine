# Data sources

Confidence key: ✅ verified live against the API/docs today · ⚠️ best-effort from docs/search, confirm before relying on it · 🔴 unresolved risk, validate in hour 1.

---

## 1. ClinicalTrials.gov v2 API ✅

Base: `https://clinicaltrials.gov/api/v2/studies` (no key required).

Verified field paths (response is `{ studies: [...], nextPageToken }`):

| Field | Path |
|---|---|
| Phase | `studies[].protocolSection.designModule.phases` |
| Status | `studies[].protocolSection.statusModule.overallStatus` |
| Primary completion date | `studies[].protocolSection.statusModule.primaryCompletionDateStruct.date` |
| Condition | `studies[].protocolSection.conditionsModule.conditions` |
| Sponsor | `studies[].protocolSection.sponsorCollaboratorsModule.leadSponsor.name` |

Filter by condition/sponsor with `query.cond` / `query.spons` params (e.g. `query.cond=obesity`, `query.spons=Novo+Nordisk`).

```json
{
  "name": "clinicaltrials-glp1",
  "source_type": "generic_rest",
  "source_config": {
    "url": "https://clinicaltrials.gov/api/v2/studies",
    "method": "GET",
    "query_params": {
      "query.cond": "obesity OR type 2 diabetes",
      "query.spons": "Novo Nordisk|Eli Lilly|Pfizer|Amgen",
      "pageSize": "100",
      "format": "json"
    },
    "auth": { "type": "none" },
    "data_path": "studies",
    "pagination": {
      "enabled": true,
      "iteration_type": "token",
      "token_param": "pageToken",
      "next_token_path": "nextPageToken"
    },
    "schedule": "0 */6 * * *"
  }
}
```

---

## 2. openFDA — drug approvals & labels ✅

Two distinct endpoints — don't conflate them:

- `https://api.fda.gov/drug/label.json` — indication/usage text, no structured approval date.
- `https://api.fda.gov/drug/drugsfda.json` — structured approval history (this is the one for "new indication" tracking).

Verified `drugsfda` field paths:

| Field | Path |
|---|---|
| Application number | `results[].application_number` |
| Sponsor | `results[].sponsor_name` |
| Product (brand/dosage/status) | `results[].products[].brand_name`, `.dosage_form`, `.marketing_status` |
| Submission type/status/date | `results[].submissions[].submission_type`, `.submission_status`, `.submission_status_date` |

⚠️ "New indication" is only queryable indirectly: filter `submissions.submission_type:"SUPPL"` (supplemental application) and read `submissions[].submission_class_code_description` for "Labeling"/"Efficacy" — there's no clean boolean flag. Treat this as a heuristic, not ground truth; keep RSS/news (source 4) as the backstop for indication-expansion events.

Free tier is unauthenticated but rate-limited to 40 req/min, 1000/day; add `api_key` param once you register a free key to raise that.

```json
{
  "name": "openfda-drugsfda-glp1",
  "source_type": "generic_rest",
  "source_config": {
    "url": "https://api.fda.gov/drug/drugsfda.json",
    "method": "GET",
    "query_params": {
      "search": "openfda.generic_name:(semaglutide OR tirzepatide OR liraglutide)",
      "limit": "100",
      "api_key": "{{OPENFDA_API_KEY}}"
    },
    "auth": { "type": "none" },
    "data_path": "results",
    "pagination": {
      "enabled": true,
      "iteration_type": "page_offset",
      "offset_param": "skip",
      "page_size_param": "limit",
      "page_size": 100
    },
    "schedule": "0 */6 * * *"
  }
}
```

---

## 3. Market prices — yfinance ⚠️🔴

`yfinance` is a **Python library**, not a hosted REST API — Nexla's generic REST connector can't point at it directly. Two options:

**Option A (recommended for the hackathon): skip yfinance, hit the Yahoo endpoint it wraps directly.**
`yfinance` itself calls `https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}` under the hood. This is unauthenticated and Nexla-reachable, but it's an undocumented/unofficial endpoint Yahoo can rate-limit or change without notice — confirm it still resolves your tickers (`NVO`, `LLY`, `PFE`, `AMGN`) before relying on it live.

```json
{
  "name": "yahoo-chart-glp1-tickers",
  "source_type": "generic_rest",
  "source_config": {
    "url": "https://query1.finance.yahoo.com/v8/finance/chart/{{ticker}}",
    "method": "GET",
    "query_params": { "interval": "1d", "range": "5d" },
    "url_macros": { "ticker": ["NVO", "LLY", "PFE", "AMGN"] },
    "auth": { "type": "none" },
    "headers": { "User-Agent": "Mozilla/5.0" },
    "data_path": "chart.result",
    "schedule": "*/15 9-16 * * 1-5"
  }
}
```

**Option B (fallback if Option A gets blocked): run `yfinance` in a small scheduled script and push results into Nexla as a file/webhook source** instead of REST-pull. Slower to wire up — only fall back to this if Yahoo's endpoint 429s or changes shape mid-hackathon.

---

## 4. News / catalyst headlines — RSS recommended ✅⚠️

**Recommended: RSS, no key, no rate limit.**

| Source | Feed URL | Confidence |
|---|---|---|
| FiercePharma | `https://www.fiercepharma.com/rss/xml` | ✅ live |
| Endpoints News | `http://endpts.com/feed` | ⚠️ resolve redirect, confirm still active |

```json
{
  "name": "pharma-news-rss",
  "source_type": "rss",
  "source_config": {
    "feed_urls": [
      "https://www.fiercepharma.com/rss/xml",
      "http://endpts.com/feed"
    ],
    "poll_interval": "15m"
  }
}
```

**Fallback: NewsAPI.org** — free tier requires a key, is capped at 100 req/day, and delays articles ~24h (not usable for same-day catalyst detection). Only reach for this if the RSS feeds don't cover a needed source.

```json
{
  "name": "newsapi-glp1-fallback",
  "source_type": "generic_rest",
  "source_config": {
    "url": "https://newsapi.org/v2/everything",
    "method": "GET",
    "query_params": {
      "q": "GLP-1 OR semaglutide OR tirzepatide",
      "sortBy": "publishedAt",
      "language": "en"
    },
    "auth": { "type": "api_key_header", "header": "X-Api-Key", "value": "{{NEWSAPI_KEY}}" },
    "data_path": "articles",
    "schedule": "0 * * * *"
  }
}
```

---

## 5. Nexla — joining feeds 1–4 into one contract ⚠️

The `source_config` field names above (`url`, `data_path`, `pagination.*`) are inferred from Nexla's REST connector UI labels ("Set API URL", "Set Path to Data in Response", "This API is paginated", etc.) — Nexla's docs show the UI flow, not the raw JSON schema, so **confirm exact key names against your Nexla org's `POST /data_sources` schema (or with the sponsor's solutions engineer) before building against them.**

Fastest path to a live pipeline:
1. Create 4 sources above via Nexla UI or `POST /data_sources` (each needs `name`, `source_type`, `source_config`, `data_credentials_id` — use a "none"/no-auth credential stub for the keyless ones).
2. Each source lands as a raw **Nexset**. Add a transform Nexset per source to normalize to a shared schema (e.g. `{ entity, event_type, event_date, source, payload }`).
3. Union the 4 normalized Nexsets into one combined Nexset (Nexla supports multi-input transforms/joins).
4. Attach a **webhook or REST destination** on the combined Nexset so the agent polls/receives one unified JSON contract instead of 4 separate feeds.
5. Validate end-to-end with one row from each source before trusting the union.

---

## 6. Akash — hosting the model + the loop ⚠️

- Deploy is declarative via an **SDL** file (YAML, Docker-Compose-like), submitted with `provider-services tx deployment create deploy.yaml --from <wallet> --node <node-url> --chain-id <chain-id> --fees <fees>`, or via the visual [Akash Console SDL Builder](https://console.akash.network/sdl-builder).
- Public URL comes from the **Leases** tab after a provider accepts the deployment — set `expose.to.global: true` in the SDL for the service that needs a public endpoint.
- 🔴 Cold-start time is provider-dependent and not documented centrally — test this in hour 1, don't assume it's fast enough for a live demo.
- Model choice: hosting your own model on Akash gives control but adds cold-start/ops risk during a hackathon; **keep a hosted-API fallback (e.g. Claude API) wired up in parallel** so a slow Akash deploy doesn't block the demo.

---

## 7. Pomerium — guardrails on outbound calls 🔴 (validate first, per your own flag)

Important nuance found in docs: Pomerium is built and documented as an **identity-aware *reverse* proxy** — it gates *inbound* requests to services behind it. A hard outbound domain allowlist for an agent's own HTTP egress (only letting it reach feeds 1–4) is not a documented out-of-the-box feature; Pomerium is an intended fit only via its Rego-based custom authorization (Enterprise tier) or by running it in an atypical forward-proxy mode.

Don't assume this "just works" — confirm at the sponsor table specifically:
- Does the version/tier you have access to support forward-proxy / egress mode at all?
- If not, the honest fallback is a plain allowlist at the network layer (e.g. an egress firewall rule or a thin custom HTTP proxy) rather than Pomerium.

This matches your own instinct to de-risk it first — it's the one item on this list most likely to not do what the name suggests.

---

## 8. LLM / inference ⚠️

- Primary: whatever model is hosted per §6 (Akash) or a hosted inference endpoint if Akash isn't ready in time.
- Confirm the endpoint supports **structured/JSON output** (tool-use / forced schema, not just free-text) for the extraction step that turns feeds 1–4 into the combined contract from §5.
- Keep a fallback hosted API (e.g. Claude API) wired with the same prompt/schema so a slow or unstable Akash endpoint doesn't block the pipeline.

# P3 — Infra & Security

Everything that makes the loop **run somewhere, safely**. Two guardrails wrap the
autonomous book:

| Layer | What it does | Where | Status |
|---|---|---|---|
| **Container** | packages P1's loop server (FastAPI on :8000) | `Dockerfile` | ✅ builds & runs |
| **Egress guardrail** | default-deny forward proxy — agent may reach ONLY the 4 data feeds | `guardrail/` | ✅ enforced + demoed |
| **Ingress guardrail** | Pomerium in front of the control API — `/inject` & `/reset` need the operator token | `pomerium-config.yaml` | ✅ valid config |
| **Akash deploy** | runs both containers on Akash, public URL for the UI | `akash-deploy.yaml`, `deploy.sh` | ⏳ needs registry login + funded AKT wallet |

## Run the whole thing locally (loop behind the guardrail)

```bash
docker compose -f infra/docker-compose.yaml up --build
```

- Loop API → http://localhost:8000  (P4 points the UI here: `GET /state`, `POST /inject`, `POST /reset`)
- Guardrail proxy → :3128

## Demo the guardrail (the "guardrails on an autonomous book" rubric item)

From inside the running loop container — allowed feed passes, anything else is blocked:

```bash
# ALLOWED → HTTP 200
docker compose -f infra/docker-compose.yaml exec ripple-engine \
  python -c "import httpx;print(httpx.get('https://clinicaltrials.gov/api/v2/studies?pageSize=1',timeout=15).status_code)"

# BLOCKED → httpx.ProxyError: 403 Forbidden
docker compose -f infra/docker-compose.yaml exec ripple-engine \
  python -c "import httpx;print(httpx.get('https://api.openai.com/v1/models',timeout=15).status_code)"

# The decision stream (show this on screen):
docker compose -f infra/docker-compose.yaml logs -f guardrail
#   [guardrail] ALLOW clinicaltrials.gov
#   [guardrail] DENY  api.openai.com
```

The allowlist is a single source of truth: **`guardrail/allowlist.txt`**
(clinicaltrials.gov · api.fda.gov/open.fda.gov · query1/2.finance.yahoo.com · newsapi.org).
Add a source there and rebuild — nothing else to change.

## Deploy to Akash

Akash pulls from a **public registry** (it can't build). One command does build + push:

```bash
docker login                                  # once
REGISTRY=docker.io/<your-user> ./infra/deploy.sh
```

Then deploy `infra/akash-deploy.generated.yaml` via **console.akash.network → Deploy → Upload SDL**
(easiest), or `provider-services tx deployment create ...` with a funded wallet.
Copy the public URI it returns for port 80 → that's the loop URL. Hand it to P1 & P4.

### What's blocked on you (needs your accounts — can't be automated)
1. `docker login` to a registry (Docker Hub / GHCR).
2. A funded Akash wallet (AKT) + provider bid, **or** the Akash Console web flow.

Until then, `docker-compose` gives P4 a live local URL to build against — no one is blocked.

## Sponsor story (honest version)
- **Akash** — hosts the loop + guardrail (`akash-deploy.yaml`, one deployment, public URL).
- **Pomerium** — ingress guardrail on the control API; injecting/resetting the book requires the
  operator token (native identity-aware-proxy use). Config in `pomerium-config.yaml`.
- **Egress fence** — the outbound allowlist is enforced by the lightweight proxy in `guardrail/`
  (stdlib, auditable). It's the thing that actually blocks `evil.com` in the live demo. Pomerium is
  the ingress half; this is the egress half. Present them as the two-sided guardrail — don't claim
  Pomerium itself does the outbound filtering.

## Files
```
infra/
  Dockerfile              loop container (P1's server)
  docker-compose.yaml     loop + guardrail, wired via *_PROXY  ← run this
  akash-deploy.yaml       Akash SDL, both services
  deploy.sh               build + push both images, print deploy steps
  pomerium-config.yaml    Pomerium ingress policy on the control API
  guardrail/
    proxy.py              default-deny egress forward proxy (stdlib)
    allowlist.txt         the 4 allowed domains — single source of truth
    Dockerfile            tiny proxy image
```

# GLP-1 Ripple Engine

An autonomous agent **loop** that trades the *second-order* effects of GLP-1 /
weight-loss drug catalysts. Everyone trades Lilly on GLP-1 news — we trade the
snack aisle, the liquor store, and the CPAP maker one step downstream.

## The loop

```
   ┌─────────────────────────────────────────────────────────┐
   │  sense ─► plan (gate) ─► act (graph) ─► observe ─► decide │
   └───────────────────────────────▲────────────────────┬─────┘
                                    └────────── repeat ◄─┘
```

- **Goal:** for every catalyst on the GLP-1 watchlist, propagate its market
  impact through the graph and update the book, until all watched catalysts
  resolve.
- **Stop condition:** all watched catalysts resolved (not infinite).
- **State** is persisted outside the model in `state.json`.
- **Self-correction:** a deterministic verification gate re-extracts trial
  fields on schema mismatch before committing.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn loop.server:app --reload --port 8000
```

- `GET  http://localhost:8000/state`  — current tick state (the UI polls this)
- `POST http://localhost:8000/inject` — queue a catalyst
- `POST http://localhost:8000/reset`  — reset the book

Fire the scripted demo catalysts at the running loop:

```bash
python -m data.injector
```

Open `frontend/index.html` in a browser and hit **Play** to see the mock run.
For live mode, swap the embedded `EVENTS` const for a poll of
`http://localhost:8000/state` every 2s.

## Ownership lanes

- **P1 (loop):** flesh out `loop/engine.py` tick logic + stop condition + gate.
- **P2 (data):** make `data/feeds.py` real, route through
  `data/nexla_client.py`, drive `data/injector.py`.
- **P3 (infra):** Akash deploy + Pomerium egress allowlist (validate Pomerium
  first — de-risk in hour 1).
- **P4 (Diya):** `frontend/index.html` — switch it to live-poll `/state`.

## Sponsor integration points

- **Nexla** — `data/nexla_client.py`. Fuses 4 live feeds (trials + FDA + prices
  + news) into one per-tick context.
- **Akash** — `infra/Dockerfile` + `infra/akash-deploy.yaml`. Hosts the loop.
- **Pomerium** — `infra/pomerium-config.yaml`. Egress allowlist so the agent can
  only reach the four data feeds.

## Layout

```
contracts/   schema.md (tick contract) · mock-events.json (P1↔P4 contract)
loop/        state · impact_graph · gate · engine · server
data/        feeds · nexla_client · injector
infra/       Dockerfile · akash-deploy.yaml · pomerium-config.yaml
frontend/    index.html (ripple UI)
```

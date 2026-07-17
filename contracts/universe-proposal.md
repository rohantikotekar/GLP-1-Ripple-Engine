# GLP-1 Ripple Engine — Proposed Tracking Universe

**For:** P1 (book in `loop/state.py`) · P2 (edges in `loop/impact_graph.py`)
**Status:** proposal — thesis calls to confirm before wiring.

21 names across 8 sectors. `sector` is the shared key between the book and the
impact graph. `side` is long/short. The thesis line is what P2 turns into a
signed edge per catalyst type.

---

## LONGS — beneficiaries

| Ticker | Company | Sector | Thesis | Flag |
|---|---|---|---|---|
| LLY | Eli Lilly | `drug_maker` | Zepbound/Mounjaro — category leader | in book |
| NVO | Novo Nordisk | `drug_maker` | Wegovy/Ozempic | in book |
| VKTX | Viking Therapeutics | `drug_maker` | VK2735 obesity pipeline | in book |
| GPCR | Structure Therapeutics | `drug_maker` | oral GLP-1 (demo primary) | in book |
| AMGN | Amgen | `drug_maker` | MariTide monthly obesity drug | |
| RHHBY | Roche | `drug_maker` | Carmot obesity pipeline | OTC ADR |
| PFE | Pfizer | `drug_maker` | oral GLP-1 (danuglipron), weak | optional |
| HIMS | Hims & Hers | `telehealth` | D2C GLP-1 distribution volume | high-beta |

## SHORTS — disrupted incumbents

| Ticker | Company | Sector | Thesis | Flag |
|---|---|---|---|---|
| HSY | Hershey | `food_cpg` | confection demand down | in book |
| MDLZ | Mondelez | `food_cpg` | snack demand down | in book |
| PEP | PepsiCo | `food_cpg` | Frito-Lay + soda down | |
| NSRGY | Nestlé | `food_cpg` | confection/frozen down | OTC ADR |
| STZ | Constellation Brands | `alcohol` | GLP-1 cuts alcohol cravings | in book |
| DEO | Diageo | `alcohol` | spirits demand down | in book |
| RMD | ResMed | `sleep_apnea` | weight loss reduces OSA | in book |
| INSP | Inspire Medical | `sleep_apnea` | OSA implant demand down | in book |
| MDT | Medtronic | `medical_devices` | diabetes tech + bariatric surgery down | |
| DXCM | DexCom | `medical_devices` | CGM demand (fewer diabetics) | debated |
| DVA | DaVita | `dialysis` | diabetic kidney disease down long-term | in book |
| UNH | UnitedHealth | `payers` | GLP-1 drug-cost pressure on insurers | |
| CVS | CVS Health | `payers` | Aetna cost up (Caremark partly offsets) | mixed |

---

## Changes this requires

- **3 new sectors:** `telehealth`, `medical_devices`, `payers`.
- **Rename `snacks` → `food_cpg`** so Nestlé/Pepsi fit. (Frontend, book, and
  graph all key off the sector name — change it in all three or keep `snacks`.)
- **8 longs / 13 shorts** is intentional: one winner category, many disrupted
  incumbents. P1 sizes shares to balance dollar exposure.

## Open thesis calls (settle as a team)

- **DXCM** — GLP-1 bull/bear case is genuinely contested. Keep muted or drop.
- **CVS** — PBM/dispensing volume offsets the insurance cost. Keep muted or drop.

## Data caveats (P2)

- **RHHBY** and **NSRGY** are OTC ADRs — confirm the price feed resolves them,
  or use their primary-listing tickers.

## Bench (swap in to stretch toward 25)

`KHC` / `GIS` (food_cpg) · `BUD` (alcohol) · `FMS` (dialysis pair for DVA) ·
`ABT` (medical_devices, but diversified → muted signal).

---

## Modeling note (P2)

Today each catalyst moves a whole **sector** uniformly. For per-name divergence
inside a sector — e.g. a competitor's Phase 3 win helping the challenger while
pressuring LLY/NVO — the graph needs per-ticker weights, not just per-sector.
Optional stretch, not required for the demo.

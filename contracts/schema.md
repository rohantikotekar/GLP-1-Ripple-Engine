# Tick Contract — source of truth

Every layer agrees on this object. It is the contract between **P1's loop** and
**P4's UI**. The loop emits one of these per tick; the UI renders it.

```jsonc
{
  "tick": 0,
  "status": "running | stopped",
  "catalyst": { "headline": "...", "source": "...", "type": "..." } | null,
  "active_sectors": [ { "sector": "drug_maker", "delta": 1.0 } ],
  "log": [ { "level": "info|muted|good|warn|catalyst|stop", "text": "..." } ],
  "positions": [
    { "ticker": "LLY", "name": "Eli Lilly", "sector": "drug_maker",
      "side": "long|short", "entry": 812.0, "price": 812.0,
      "shares": 10, "pnl": 0.0 }
  ],
  "pnl_total": 0.0
}
```

## Field notes

- `status` — `running` until the stop condition is met, then `stopped`.
- `catalyst` — the sensed event this tick, or `null` on an idle/gate tick.
- `active_sectors[]` — `{sector, delta}`. Drives the ripple highlight in the UI.
  `delta > 0` glows green (up), `delta < 0` glows red (down). Sign here is a
  *display* signal, not the raw price multiplier.
- `log[]` — `{level, text}`. Streamed append-only into the UI log pane.
  Levels: `info`, `muted`, `good`, `warn`, `catalyst`, `stop`.
- `positions[]` — the full long/short book every tick. `shares` negative = short.
- `pnl_total` — sum of position `pnl`.

## Important

`contracts/mock-events.json` (copied from Cowork) is a **valid sequence of these
objects**. P4's UI already renders it, so the loop **must emit the same shape**.
When P1's loop goes live, P4 swaps the embedded `EVENTS` const for a poll of
`GET /state` — the render code does not change.

## Catalyst types the impact graph understands

- `phase3_readout`
- `new_indication`
- `approval`
- `rx_volume`

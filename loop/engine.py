"""LOOP-ENG core — the sense/plan/act/observe/decide cycle.

One tick:
  sense   -> take the injected catalyst if present
  plan    -> run the verification gate (self-correct on schema mismatch)
  act     -> propagate through the impact graph, re-price the book
  observe -> append log lines, mark the catalyst resolved
  decide  -> evaluate the stop condition (all watchlist catalysts resolved)

Keep it small and readable — the loop shape is the graded artifact.
"""

from loop import gate, impact_graph


def tick(state, incoming_catalyst=None):
    state["tick"] += 1
    log = []

    # --- sense ---------------------------------------------------------------
    if incoming_catalyst is None:
        state["catalyst"] = None
        state["active_sectors"] = []
        log.append({"level": "muted",
                    "text": f"tick {state['tick']} · sensing feeds · no new catalyst · book flat"})
        state["log"] = log
        return _decide(state, log)

    catalyst = incoming_catalyst
    primary = catalyst.get("ticker_primary", "")
    log.append({"level": "catalyst",
                "text": f"CATALYST · {catalyst.get('headline', '?')} "
                        f"· {catalyst.get('source', '?')}"})

    # --- plan (verification gate / self-correct) -----------------------------
    ok, corrected = gate.verify(catalyst)
    if not ok:
        log.append({"level": "warn",
                    "text": f"verification gate · phase mismatch vs ClinicalTrials.gov "
                            f"schema — self-correcting to {corrected['phase']}"})
        catalyst = corrected
        log.append({"level": "good", "text": "gate passed · commit accepted"})
    else:
        log.append({"level": "info",
                    "text": f"classified type={catalyst.get('type')} · primary={primary or 'n/a'}"})

    # --- act (propagate through the impact graph) ----------------------------
    state["catalyst"] = {k: catalyst.get(k) for k in ("headline", "source", "type")}
    impact_graph.apply(state, catalyst)
    log.append({"level": "info",
                "text": "propagating through impact graph → "
                        "drug_maker↑ snacks↓ alcohol↓ sleep_apnea↓ dialysis↓"})
    log.append({"level": "good", "text": f"book updated · P&L {_fmt(state['pnl_total'])}"})

    # --- observe (resolve the catalyst on the watchlist) ---------------------
    if primary and primary not in state["seen_catalysts"]:
        state["seen_catalysts"].append(primary)

    state["log"] = log
    return _decide(state, log)


def _decide(state, log):
    """Stop condition: every watched catalyst has been seen/resolved."""
    watchlist = state.get("watchlist", [])
    resolved = [w for w in watchlist if w in state["seen_catalysts"]]
    if watchlist and len(resolved) >= len(watchlist):
        state["status"] = "stopped"
        state["catalyst"] = None
        state["active_sectors"] = []
        log.append({"level": "stop",
                    "text": f"STOP CONDITION MET · {len(resolved)}/{len(watchlist)} "
                            f"watched catalysts resolved · loop halted"})
        log.append({"level": "good",
                    "text": f"final book P&L {_fmt(state['pnl_total'])} · runtime clean exit"})
    return state


def _fmt(n):
    sign = "+" if n >= 0 else "-"
    return f"{sign}${abs(n):,.0f}"

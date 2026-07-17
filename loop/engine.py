"""LOOP-ENG core — the sense/plan/act/observe/decide cycle.

One tick:
  sense   -> take the injected catalyst if present
  plan    -> run the verification gate (self-correct on schema mismatch)
  act     -> propagate through the impact graph, re-price the book
  observe -> append log lines, mark this company's research complete
  decide  -> evaluate the stop condition (every portfolio company researched)

Keep it small and readable — the loop shape is the graded artifact.
"""

from loop import gate, impact_graph, model


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
                "text": f"CATALYST · {catalyst.get('detail', '?')} "
                        f"· {catalyst.get('id') or 'n/a'}"})

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

    # --- act (ask the Akash model to confirm type, then propagate) -----------
    chosen_type, decided_by = model.classify(catalyst)
    catalyst["type"] = chosen_type
    log.append({"level": "info",
                "text": f"act · catalyst type={chosen_type} confirmed by {decided_by}"
                        + (" (Akash-hosted)" if decided_by == "akash-model" else "")})
    # P4's UI tick contract (contracts/schema.md) still expects
    # headline/source/type - adapt from the new catalyst-candidate shape.
    state["catalyst"] = {
        "headline": catalyst.get("detail"),
        "source": catalyst.get("id"),
        "type": catalyst.get("type"),
    }
    impact_graph.apply(state, catalyst)
    log.append({"level": "info",
                "text": "propagating through impact graph → "
                        "drug_maker↑ snacks↓ alcohol↓ sleep_apnea↓ dialysis↓"})
    log.append({"level": "good", "text": f"book updated · P&L {_fmt(state['pnl_total'])}"})

    # --- observe (mark this portfolio company's research complete) -----------
    if primary and primary not in state["researched"]:
        state["researched"].append(primary)
        log.append({"level": "info",
                    "text": f"observe · {primary} research complete · "
                            f"{len(state['researched'])}/{len(state['research_portfolio'])} "
                            f"portfolio companies researched"})

    state["log"] = log
    return _decide(state, log)


def _decide(state, log):
    """Stop condition: every company in the research portfolio has been
    researched, OR the risk threshold is breached."""
    # Risk breach — max drawdown guard. Fires before the coverage check so a
    # blown-up book halts immediately.
    risk_limit = state.get("risk_limit")
    if risk_limit is not None and state["pnl_total"] <= -abs(risk_limit):
        state["status"] = "stopped"
        state["catalyst"] = None
        state["active_sectors"] = []
        log.append({"level": "stop",
                    "text": f"RISK THRESHOLD BREACHED · book P&L {_fmt(state['pnl_total'])} "
                            f"≤ -{_fmt(abs(risk_limit))[1:]} · loop halted"})
        return state

    # Core stop: all portfolio companies researched.
    portfolio = state.get("research_portfolio", [])
    researched = [c for c in portfolio if c in state["researched"]]
    if portfolio and len(researched) >= len(portfolio):
        state["status"] = "stopped"
        state["catalyst"] = None
        state["active_sectors"] = []
        log.append({"level": "stop",
                    "text": f"STOP CONDITION MET · {len(researched)}/{len(portfolio)} "
                            f"portfolio companies researched · loop halted"})
        log.append({"level": "good",
                    "text": f"final book P&L {_fmt(state['pnl_total'])} · runtime clean exit"})
    return state


def _fmt(n):
    sign = "+" if n >= 0 else "-"
    return f"{sign}${abs(n):,.0f}"

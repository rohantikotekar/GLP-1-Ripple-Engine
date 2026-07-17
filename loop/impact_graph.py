# The "secret sauce" the agent traverses: catalyst type -> {sector: signed
# magnitude multiplier}. Hand-built from GLP-1 consumption data (snacks down,
# alcohol down, CPAP/sleep-apnea threatened, dialysis marginally affected).
# P1/P2 tune the edges.
IMPACT = {
    "phase3_readout_positive": {
        "drug_maker": +0.06, "snacks": -0.02, "alcohol": -0.015,
        "sleep_apnea": -0.02, "dialysis": -0.005,
    },
    "new_indication_sleep_apnea": {"sleep_apnea": -0.05, "drug_maker": +0.02},
    "approval": {
        "drug_maker": +0.04, "snacks": -0.015, "alcohol": -0.01, "sleep_apnea": -0.015,
    },
    "rx_volume": {"drug_maker": +0.02, "snacks": -0.02, "alcohol": -0.015},
}

# Primary ticker of a catalyst gets an outsized move.
PRIMARY_BONUS = {"GPCR": 0.45, "VKTX": 0.10}


def apply(state, catalyst):
    """Propagate a catalyst through the graph, re-pricing the book in place."""
    edges = IMPACT.get(catalyst["type"], {})
    active = [{"sector": k, "delta": v} for k, v in edges.items()]
    total = 0.0
    for p in state["positions"]:
        mult = 1.0 + edges.get(p["sector"], 0.0)
        if p["ticker"] == catalyst.get("ticker_primary"):
            mult += PRIMARY_BONUS.get(p["ticker"], 0.0)
        # Compound onto the running price so successive catalysts stack.
        base = p["entry"] if p["price"] == p["entry"] else p["price"]
        p["price"] = round(base * mult, 2)
        p["pnl"] = round((p["price"] - p["entry"]) * p["shares"], 2)
        total += p["pnl"]
    state["pnl_total"] = round(total, 2)
    state["active_sectors"] = active
    return state

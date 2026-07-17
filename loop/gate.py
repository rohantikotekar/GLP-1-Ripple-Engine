# LOOP-ENG: verification gate / self-correction.
# Deterministic schema check on extracted trial fields. On mismatch we correct
# and flag it so the loop can re-commit — this is the graded self-correct step.

VALID_PHASES = {"Phase 1", "Phase 2", "Phase 3", "Phase 4"}


def verify(extracted: dict):
    """Return (ok, corrected). Demo of a deterministic verification gate.

    Phase schema only applies to trial-shaped catalysts. News / FDA / inject
    payloads without a phase should not trip a false self-correct.
    """
    phase = extracted.get("phase")
    if phase is None and extracted.get("type") != "phase3_readout":
        return True, extracted
    if phase not in VALID_PHASES:
        return False, {**extracted, "phase": "Phase 3", "_corrected": True}
    return True, extracted

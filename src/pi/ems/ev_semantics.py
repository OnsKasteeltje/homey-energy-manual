from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvSemanticInput:
    decision_mode: str
    flex_W: float
    charger_available: bool
    deadline_active: bool
    core_revision: int


def build_ev_control(inp: EvSemanticInput) -> dict[str, object]:
    mode_map = {
        "TESLA_CHARGE_DEADLINE": "DEADLINE",
        "TESLA_CHARGE_OPPORTUNITY": "OPPORTUNITY",
        "TESLA_BUFFER_EXPORT": "BUFFER_EXPORT",
    }
    ev_mode = mode_map.get(str(inp.decision_mode).upper(), "HOLD")
    flex_w = max(0.0, float(inp.flex_W or 0.0))

    if ev_mode == "HOLD":
        requested_power_class = 0
    elif flex_w < 4140:
        requested_power_class = 1
    else:
        requested_power_class = min(16, int(flex_w // 690))

    return {
        "schema": "EM2_CONTROL_EV_V0.1",
        "semanticRevision": int(inp.core_revision),
        "coreRevision": int(inp.core_revision),
        "mode": ev_mode,
        "requestedPowerClass": requested_power_class,
        "chargerAvailable": bool(inp.charger_available),
        "deadlineActive": bool(inp.deadline_active),
        "safetyState": "OK" if inp.charger_available else "BLOCKED",
    }


def semantic_equal(a: dict[str, object], b: dict[str, object]) -> bool:
    """Compare EV-control semantics while ignoring volatile publication timestamps."""
    keys = {
        "schema",
        "semanticRevision",
        "coreRevision",
        "mode",
        "requestedPowerClass",
        "chargerAvailable",
        "deadlineActive",
        "safetyState",
    }
    return all(a.get(k) == b.get(k) for k in keys)

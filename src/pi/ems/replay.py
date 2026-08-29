from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import EmsState, Observation, Quality


def _obs(value: Any, observed_at: str, source: str, stale_after_s: int = 30) -> Observation:
    return Observation(
        value=value,
        observed_at=datetime.fromisoformat(observed_at),
        received_at=datetime.now(timezone.utc),
        source=source,
        quality=Quality.GOOD,
        stale_after_s=stale_after_s,
    )


def state_from_fixture(payload: dict[str, Any]) -> EmsState:
    """Build canonical state from a deterministic replay fixture.

    This function performs no external I/O and is safe to run while Homey is throttled.
    """
    ts = payload["grid_observed_at"]
    state = EmsState()
    state.grid.power_W = _obs(payload["grid_power_W"], ts, "fixture:p1")
    state.pv.solaredge_W = _obs(payload["pv"]["solaredge_W"], ts, "fixture:solaredge", 300)
    state.pv.goodwe4200_W = _obs(payload["pv"]["goodwe4200_W"], ts, "fixture:goodwe4200", 300)
    state.pv.goodwe2000_W = _obs(payload["pv"]["goodwe2000_W"], ts, "fixture:goodwe2000", 300)
    state.ev.power_W = _obs(payload["ev"]["power_W"], ts, "fixture:easee", 60)
    state.ev.charger_available = _obs(
        payload["ev"]["charger_available"], ts, "fixture:easee", 60
    )
    state.ev.deadline_active = _obs(
        payload["ev"]["deadline_active"], ts, "fixture:deadline", 300
    )
    state.ww.boiler_on = _obs(payload["ww"]["boiler_on"], ts, "fixture:boiler", 60)
    state.ww.boiler_power_W = _obs(
        payload["ww"]["boiler_power_W"], ts, "fixture:boiler", 60
    )
    state.ww.goal_reached_today = _obs(
        payload["ww"]["goal_reached_today"], ts, "fixture:ww-state", 900
    )
    return state


def replay_projection(state: EmsState, now: datetime) -> dict[str, Any]:
    """Return deterministic derived values used for replay comparison."""
    grid = state.grid.power_W
    grid_quality = Quality.MISSING if grid is None else grid.effective_quality(now)

    pv_total = state.pv.valid_total_W()
    house_power = None
    if grid is not None and grid.value is not None and pv_total is not None:
        house_power = float(grid.value) + float(pv_total)

    reasons: list[str] = []
    if grid is None:
        reasons.append("GRID_POWER_MISSING")
    elif grid_quality is not Quality.GOOD or grid.value is None:
        reasons.append(f"GRID_POWER_{grid_quality.value}")

    return {
        "grid_quality": grid_quality.value,
        "pv_total_W": pv_total,
        "house_power_W": house_power,
        "positive_writes_allowed": not reasons,
        "block_reasons": reasons,
    }

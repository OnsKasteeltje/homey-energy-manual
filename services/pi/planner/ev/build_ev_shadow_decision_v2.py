#!/usr/bin/env python3
"""Compose Planner V2 EV shadow inputs into one observable decision.

Pure/read-only: no Homey calls, no device writes, no /control/current changes.
"""
from dataclasses import asdict
from typing import Iterable, Optional

from build_ev_opportunity_v2 import (
    MODES, better_normal_opportunity_later, decide_start, modulate,
)


def decide_ev_shadow(
    *,
    connected: bool,
    current_mode: str,
    p1_export_w: float,
    now_forecast_w: float,
    future_slots,
    available_pv_samples_w: Iterable[float],
    deadline_active: bool,
    deadline_required_now: bool,
    deadline_max_a: Optional[int],
    horizon_end=None,
):
    """Return OFF/GRAY/NORMAL/DEADLINE with target A and explicit reason."""
    if not connected:
        return {"mode":"OFF","targetA":0,"reason":"EV_NOT_CONNECTED","readOnly":True}

    if deadline_active and deadline_required_now:
        try:
            max_a = int(deadline_max_a)
        except (TypeError, ValueError):
            return {"mode":"OFF","targetA":0,"reason":"INVALID_DEADLINE_MAX_A","readOnly":True}
        if not 6 <= max_a <= 16:
            return {"mode":"OFF","targetA":0,"reason":"INVALID_DEADLINE_MAX_A","readOnly":True}
        return {"mode":"DEADLINE","targetA":max_a,"reason":"HARD_DEADLINE_REQUIRED_NOW","readOnly":True}

    mode = current_mode if current_mode in MODES else "OFF"
    if mode == "OFF":
        wait = better_normal_opportunity_later(
            p1_export_w=p1_export_w,
            now_forecast_w=now_forecast_w,
            future_slots=future_slots,
            horizon_end=horizon_end,
        )
        decision = decide_start(
            p1_export_w=p1_export_w,
            better_normal_opportunity_later=wait,
        )
    else:
        decision = modulate(mode=mode, samples_w=available_pv_samples_w)

    out = asdict(decision)
    return {
        "mode":out["mode"],
        "targetA":out["target_a"],
        "reason":out["reason"],
        "rolling5mW":out["rolling5m_w"],
        "readOnly":True,
    }

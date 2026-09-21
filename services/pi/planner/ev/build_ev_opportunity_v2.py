#!/usr/bin/env python3
"""Planner V2 EV shadow decision core.

Pure/read-only logic. Forecast only decides whether a 2.0..6A gray opportunity
is worth taking now. Realtime P1 is authority; a rolling five-minute
P1+actual-EV reconstruction symmetrically modulates an active opportunity.
"""
from dataclasses import dataclass
from typing import Iterable, Optional

EV_W_PER_A = 690
MIN_A = 6
OPPORTUNITY_MAX_A = 11
GRAY_MIN_W = 2000
NORMAL_MIN_W = MIN_A * EV_W_PER_A
MODES = {"OFF", "GRAY_OPPORTUNITY", "NORMAL_PV_OPPORTUNITY"}


@dataclass(frozen=True)
class EvOpportunityDecision:
    mode: str
    target_a: int
    reason: str
    rolling5m_w: Optional[float] = None


def available_pv_w(*, ev_power_w: float, p1_export_w: float, p1_import_w: float) -> float:
    """Reconstruct PV opportunity while EV load is already consuming export."""
    return max(0.0, float(ev_power_w) + float(p1_export_w) - float(p1_import_w))


def rolling_average_w(samples_w: Iterable[float]) -> Optional[float]:
    """Average at most the latest five one-minute opportunity samples."""
    values = [max(0.0, float(v)) for v in samples_w][-5:]
    return sum(values) / len(values) if values else None


def amps_for_available_w(available_w: float) -> int:
    """Map available PV directly to a whole 6..11 A opportunity target."""
    amps = int(max(0.0, float(available_w)) // EV_W_PER_A)
    return max(MIN_A, min(OPPORTUNITY_MAX_A, amps))


def decide_start(*, p1_export_w: float, better_normal_opportunity_later: bool) -> EvOpportunityDecision:
    export_w = max(0.0, float(p1_export_w))
    if export_w >= NORMAL_MIN_W:
        return EvOpportunityDecision("NORMAL_PV_OPPORTUNITY", MIN_A, "P1_NORMAL_START")
    if export_w >= GRAY_MIN_W:
        if better_normal_opportunity_later:
            return EvOpportunityDecision("OFF", 0, "GRAY_WAIT_FOR_BETTER_FORECAST_OPPORTUNITY")
        return EvOpportunityDecision("GRAY_OPPORTUNITY", MIN_A, "GRAY_START_NO_BETTER_FORECAST_OPPORTUNITY")
    return EvOpportunityDecision("OFF", 0, "P1_BELOW_GRAY_START_MINIMUM")


def modulate(*, mode: str, samples_w: Iterable[float]) -> EvOpportunityDecision:
    """Symmetric up/down modulation from the same rolling five-minute value."""
    if mode not in MODES:
        raise ValueError(f"invalid opportunity mode: {mode}")
    avg = rolling_average_w(samples_w)
    if mode == "OFF" or avg is None:
        return EvOpportunityDecision("OFF", 0, "NO_ACTIVE_OPPORTUNITY", avg)

    if mode == "GRAY_OPPORTUNITY":
        if avg < GRAY_MIN_W:
            return EvOpportunityDecision("OFF", 0, "GRAY_ROLLING5M_BELOW_MINIMUM", avg)
        if avg >= NORMAL_MIN_W:
            return EvOpportunityDecision(
                "NORMAL_PV_OPPORTUNITY", amps_for_available_w(avg),
                "GRAY_PROMOTED_TO_NORMAL", avg,
            )
        return EvOpportunityDecision("GRAY_OPPORTUNITY", MIN_A, "GRAY_HOLD_6A", avg)

    if avg < NORMAL_MIN_W:
        return EvOpportunityDecision("OFF", 0, "NORMAL_ROLLING5M_BELOW_6A", avg)
    return EvOpportunityDecision(
        "NORMAL_PV_OPPORTUNITY", amps_for_available_w(avg),
        "NORMAL_ROLLING5M_TARGET", avg,
    )


def better_normal_opportunity_later(
    *,
    p1_export_w: float,
    now_forecast_w: float,
    future_slots,
    horizon_end=None,
) -> bool:
    """Return whether forecast shows enough *additional* PV for a normal 6 A start.

    PV Forecast V2 predicts production, not export. Therefore it is never
    treated as future export. We anchor the decision in measured P1 export now
    and use only the forecast production *uplift* versus the current forecast.

    A future slot is 'better normal' when:
        current P1 export + forecast PV uplift >= 6 A equivalent.

    horizon_end is an optional ISO-8601 boundary supplied by the EV requirement
    layer (for example the deadline/known availability end). Confidence is
    deliberately not a gate.
    """
    from datetime import datetime, timezone

    export_w = max(0.0, float(p1_export_w))
    now_pv = max(0.0, float(now_forecast_w))

    def parse(value):
        if not value:
            return None
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    end = parse(horizon_end)
    for slot in future_slots or []:
        start = parse(slot.get("start"))
        if start is None:
            continue
        if end is not None and start >= end:
            continue
        future_pv = max(0.0, float(slot.get("pvForecastW") or 0))
        if export_w + max(0.0, future_pv - now_pv) >= NORMAL_MIN_W:
            return True
    return False

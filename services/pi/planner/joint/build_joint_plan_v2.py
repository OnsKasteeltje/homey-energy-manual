#!/usr/bin/env python3
"""Build the canonical read-only Planner V2 joint-plan projection.

This module deliberately contains no device writes.  It joins planner-owned
15-minute projections into one presentation/validation contract.  Missing
lanes stay explicit instead of being invented by the frontend.
"""

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA = "EMS_PI_JOINT_PLAN_V2"
SLOT_MINUTES = 15


def _iso(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _slots_by_start(source):
    result = {}
    if not isinstance(source, dict):
        return result
    for slot in source.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        start = _iso(slot.get("start") or slot.get("slotStart") or slot.get("slot_start"))
        if start:
            result[start] = slot
    return result


def build_joint_plan(*, pv_forecast=None, ev_plan=None, ww_plan=None, heating_plan=None, generated_at=None):
    """Return one slot-aligned, read-only Planner V2 contract.

    No baseline household profile or expected grid power is fabricated here.
    Those fields remain unavailable until a validated canonical source exists.
    """
    pv = _slots_by_start(pv_forecast)
    ev = _slots_by_start(ev_plan)
    ww = _slots_by_start(ww_plan)
    heating = _slots_by_start(heating_plan)
    starts = sorted(set(pv) | set(ev) | set(ww) | set(heating))

    slots = []
    for start in starts:
        p = pv.get(start, {})
        e = ev.get(start, {})
        w = ww.get(start, {})
        h = heating.get(start, {})
        slots.append({
            "start": start,
            "pv": {
                "forecastW": _num(p.get("forecastW") if "forecastW" in p else p.get("powerW")),
                "confidence": p.get("confidence"),
            },
            "ev": {
                "plannedW": _num(e.get("plannedW") if "plannedW" in e else e.get("targetW")),
                "plannedA": _num(e.get("plannedA") if "plannedA" in e else e.get("targetA")),
                "mode": e.get("mode"),
                "reason": e.get("reason"),
            },
            "ww": {
                "plannedW": _num(w.get("plannedW") if "plannedW" in w else w.get("targetW")),
                "mode": w.get("mode"),
                "reason": w.get("reason"),
            },
            "heating": {
                "plannedW": _num(h.get("plannedW") if "plannedW" in h else h.get("targetW")),
                "flexState": h.get("flexState"),
                "reason": h.get("reason"),
            },
            "consequence": {
                "expectedFlexW": sum(v for v in (
                    _num(e.get("plannedW") if "plannedW" in e else e.get("targetW")),
                    _num(w.get("plannedW") if "plannedW" in w else w.get("targetW")),
                    _num(h.get("plannedW") if "plannedW" in h else h.get("targetW")),
                ) if v is not None),
                "expectedGridW": None,
                "baselineHouseW": None,
            },
        })

    return {
        "schema": SCHEMA,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "READ_ONLY",
        "controlWrites": False,
        "slotMinutes": SLOT_MINUTES,
        "authority": {
            "realtime": "P1",
            "forecast": "PV_FORECAST_V2",
            "frontendPolicy": "NONE",
        },
        "availability": {
            "pv": bool(pv),
            "ev": bool(ev),
            "ww": bool(ww),
            "heating": bool(heating),
            "baselineHouse": False,
            "expectedGrid": False,
        },
        "slots": slots,
    }

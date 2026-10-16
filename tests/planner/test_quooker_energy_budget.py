#!/usr/bin/env python3
"""Contract test for Quooker planner energy-budget semantics."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PATH = Path("src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py")
spec = importlib.util.spec_from_file_location("dynamic_shadow_plan", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TZ = ZoneInfo("Europe/Amsterdam")

assert mod.QUOOKER_W == 1580
assert mod.QUOOKER_ENERGY_BUDGET_KWH == 0.25
assert mod.QUOOKER_PLANNING_SLOT_W == 1000
assert mod.QUOOKER_EXPECTED_HEAT_MINUTES == 9.5

for day, forced_hour in ((29, 17), (26, 13)):
    slots = [
        datetime(2026, 9, day, forced_hour, minute, tzinfo=TZ)
        for minute in (0, 15, 30, 45)
    ]
    assert all(mod.quooker_mode(slot) == "FORCED_ON" for slot in slots)
    planned_w = [mod.quooker_plan_w(slot) for slot in slots]
    assert planned_w == [1000, 0, 0, 0]
    planned_kwh = sum(planned_w) * mod.SLOT_H / 1000
    assert abs(planned_kwh - 0.25) < 1e-9

weekday_opportunity = datetime(2026, 9, 29, 16, 45, tzinfo=TZ)
weekday_off = datetime(2026, 9, 29, 18, 0, tzinfo=TZ)
assert mod.quooker_mode(weekday_opportunity) == "OPPORTUNITY"
assert mod.quooker_plan_w(weekday_opportunity) == 0
assert mod.quooker_mode(weekday_off) == "OFF"
assert mod.quooker_plan_w(weekday_off) == 0

# One regression covers the distinct risk: same reservation, PV after EV,
# and a consistent grid balance; the Homey control envelope is unchanged.
def make_slots(midday_export, later_export):
    slots = []
    for hour, minute, export_w, mode, q_w in (
        (12, 15, midday_export, "OPPORTUNITY", 0),
        (14, 45, later_export, "OPPORTUNITY", 0),
        (17, 0, 0, "FORCED_ON", 1000),
    ):
        slots.append({
            "slot_start_utc": datetime(2026, 9, 29, hour, minute, tzinfo=TZ)
                .astimezone(timezone.utc).isoformat(),
            "quookerMode": mode,
            "quookerPlanW": q_w,
            "quookerPlanEnergyKWh": q_w * mod.SLOT_H / 1000,
            "pvForecastW": 3000 if hour < 17 else 0,
            "baseLoadForecastW": 500,
            "quattForecastW": 0,
            "wwPlanW": 0,
            "evPlanW": 0,
            "gridExportAfterFlexW": export_w,
            "gridImportAfterFlexW": 1000 if hour == 17 else 0,
        })
    return slots


now = datetime(2026, 9, 29, 8, tzinfo=TZ).astimezone(timezone.utc)
moved = mod.allocate_quooker_pv_reservation(make_slots(1550, 1050), now)
assert [s["quookerPlanW"] for s in moved] == [1000, 0, 0]
assert moved[0]["quookerAllocationReason"] == "PV_FORECAST_OPPORTUNITY"
assert moved[2]["quookerAllocationReason"] == "FORCED_WINDOW_STANDBY"
assert sum(s["quookerPlanEnergyKWh"] for s in moved) == 0.25
assert moved[0]["gridExportAfterFlexW"] == 1500
assert moved[2]["gridImportAfterFlexW"] == 500

# EV consumed the midday export: no Quooker PV booking.
fallback = mod.allocate_quooker_pv_reservation(make_slots(200, 1050), now)
assert [s["quookerPlanW"] for s in fallback] == [0, 0, 1000]
assert fallback[2]["quookerAllocationReason"] == "FORCED_WINDOW_FALLBACK"

print("PASS: one Quooker reservation on residual PV or forced fallback")

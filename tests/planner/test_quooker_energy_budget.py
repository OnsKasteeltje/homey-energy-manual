#!/usr/bin/env python3
"""Contract test for Quooker planner energy-budget semantics."""

import importlib.util
from datetime import datetime
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

print("PASS: Quooker planner reserves exactly 0.25 kWh per forced window")

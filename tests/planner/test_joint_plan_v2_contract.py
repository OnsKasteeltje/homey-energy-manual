#!/usr/bin/env python3
"""Contract tests for the canonical read-only Planner V2 joint plan."""

import importlib.util
from pathlib import Path

PATH = Path("services/pi/planner/joint/build_joint_plan_v2.py")
spec = importlib.util.spec_from_file_location("joint_plan_v2", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

start = "2026-09-22T10:00:00Z"
plan = mod.build_joint_plan(
    pv_forecast={"slots": [{"start": start, "forecastW": 3100, "confidence": "HIGH"}]},
    ev_plan={"slots": [{"start": start, "targetW": 2070, "targetA": 3, "mode": "NORMAL_PV_OPPORTUNITY", "reason": "PV_AVAILABLE"}]},
    ww_plan={"slots": [{"start": start, "targetW": 1900, "mode": "PV_OPPORTUNITY", "reason": "WW_WINDOW"}]},
    heating_plan={"slots": [{"start": start, "targetW": 500, "flexState": "ADVANCED", "reason": "PREHEAT_PV"}]},
    generated_at="2026-09-22T09:55:00Z",
)

assert plan["schema"] == "EMS_PI_JOINT_PLAN_V2"
assert plan["mode"] == "READ_ONLY"
assert plan["controlWrites"] is False
assert plan["slotMinutes"] == 15
assert plan["authority"]["realtime"] == "P1"
assert plan["authority"]["frontendPolicy"] == "NONE"
assert len(plan["slots"]) == 1
slot = plan["slots"][0]
assert slot["pv"] == {"forecastW": 3100, "confidence": "HIGH"}
assert slot["ev"]["plannedW"] == 2070
assert slot["ev"]["plannedA"] == 3
assert slot["ww"]["plannedW"] == 1900
assert slot["heating"]["plannedW"] == 500
assert slot["consequence"]["expectedFlexW"] == 4470

# Critical architecture rule: do not fabricate household baseline or grid result.
assert slot["consequence"]["baselineHouseW"] is None
assert slot["consequence"]["expectedGridW"] is None
assert plan["availability"]["baselineHouse"] is False
assert plan["availability"]["expectedGrid"] is False

# Missing lanes remain explicit and do not become invented load.
pv_only = mod.build_joint_plan(
    pv_forecast={"slots": [{"start": start, "forecastW": 1000}]},
    generated_at="2026-09-22T09:55:00Z",
)
assert pv_only["slots"][0]["consequence"]["expectedFlexW"] == 0
assert pv_only["slots"][0]["ev"]["plannedW"] is None
assert pv_only["availability"]["ev"] is False

text = PATH.read_text(encoding="utf-8")
for forbidden in ("requests.post(", "requests.put(", "requests.patch(", "subprocess.run("):
    assert forbidden not in text, forbidden

print("PASS: Planner V2 joint-plan read-only contract")

#!/usr/bin/env python3
"""Contract test for phase-aware EV forecasting in the active Dynamic Pi Planner."""

import importlib.util
from pathlib import Path

PLANNER = Path("src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py")
START6 = Path("src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan_start6.py")
STATUS = Path("services/pi/api/status/server.py")

spec = importlib.util.spec_from_file_location("dynamic_plan", PLANNER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

assert m.EV_1P_W_PER_A == 230
assert m.EV_3P_W_PER_A == 690
assert m.EV_1P_MIN_W == 1380
assert m.EV_1P_MAX_W == 3680
assert m.EV_3P_MIN_W == 4140
assert m.EV_3P_MAX_W == 11040
assert m.EV_START_1P_W == 1500
assert m.EV_STOP_1P_W == 1100
assert m.EV_ENTER_3P_W == 4400
assert m.EV_LEAVE_3P_W == 3600
assert m.EV_MIN_MODE_DWELL_SEC == 120

cases = [
    (1499, ("OFF", 0, 0)),
    (1500, ("1P", 6, 1380)),
    (2500, ("1P", 10, 2300)),
    (3680, ("1P", 16, 3680)),
    (4399, ("1P", 16, 3680)),
    (4400, ("3P", 6, 4140)),
    (5000, ("3P", 7, 4830)),
    (11040, ("3P", 16, 11040)),
    (12000, ("3P", 16, 11040)),
]
for residual, expected in cases:
    actual = m.ev_phase_option(residual)
    assert actual == expected, (residual, actual, expected)
    assert actual[2] <= residual or actual[2] == 0

assert m.ev_best_option(2500) == (2300, 2300.0)
assert m.ev_best_option(4400) == (4140, 4140.0)

start6 = START6.read_text(encoding="utf-8")
assert "planner.EV_RUN_MIN_W = planner.EV_RUN_MIN_A * planner.EV_1P_W_PER_A" in start6
assert "planner.EV_MIN_WINDOW_SLOTS = 1" in start6

status = STATUS.read_text(encoding="utf-8")
for literal in (
    '"start1p_W": 1500',
    '"stop1p_W": 1100',
    '"enter3p_W": 4400',
    '"leave3p_W": 3600',
    '"minModeDwellSec": 120',
):
    assert literal in status, literal

planner_text = PLANNER.read_text(encoding="utf-8")
assert "EV_IMPORT_PENALTY" not in planner_text
assert '"evForecastPhaseAware": True' in planner_text
assert '"evOpportunityIntentionalGridImportAllowed": False' in planner_text

print("PASS: Dynamic Pi Planner EV forecast matches production 1P/3P entry bands")

#!/usr/bin/env python3
"""Static safety contract for the Pi warm-water source gate."""

import importlib.util
from pathlib import Path

path = Path("services/pi/planner/warm-water/build_ww_plan.py")
dynamic_path = Path(
    "src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py"
)
text = path.read_text(encoding="utf-8")

required = [
    'hot_water_state = energy_state.get("hot_water") or {}',
    'hot_water_mode = hot_water_state.get("mode")',
    'hot_water_source = "BOILER"',
    'hot_water_source = "CV"',
    'hot_water_source = "UNKNOWN"',
    'ww_flex_eligible = True',
    'ww_flex_eligible = False',
    'electrical_need_kwh = need_kwh if ww_flex_eligible else 0.0',
    'if ww_flex_eligible and not goal_reached and required_slots > 0:',
    '"electricalFlexEligible": ww_flex_eligible',
    '"sourceBlockReason": ww_source_block_reason',
]

for token in required:
    assert token in text, token

assert 'ww_source_block_reason or "HOLD"' in text
print("PASS: electrical WW flex fails closed unless canonical source is BOILER")


# The active Dynamic Pi Planner must enforce the same canonical source gate.
spec = importlib.util.spec_from_file_location("dynamic_plan_ww_gate", dynamic_path)
dynamic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dynamic)

assert dynamic.hot_water_source_gate(
    {"hot_water": {"mode": True}}
) == ("BOILER", True, None)
assert dynamic.hot_water_source_gate(
    {"hot_water": {"mode": False}}
) == ("CV", False, "BLOCKED_SOURCE_CV")
assert dynamic.hot_water_source_gate(
    {"hot_water": {}}
) == ("UNKNOWN", False, "BLOCKED_SOURCE_UNKNOWN")
assert dynamic.hot_water_source_gate(
    {}
) == ("UNKNOWN", False, "BLOCKED_SOURCE_UNKNOWN")

dynamic_text = dynamic_path.read_text(encoding="utf-8")
for token in [
    'hot_water_source_gate(energy_state)',
    'electrical_remaining_min = remaining_min if ww_flex_eligible else 0',
    'and ww_flex_eligible',
    '"sourceMode": hot_water_source',
    '"electricalFlexEligible": ww_flex_eligible',
    '"sourceBlockReason": ww_source_block_reason',
    's["wwAllocationReason"] = ww_source_block_reason or "HOLD"',
    '"wwElectricalFlexEligible": ww_flex_eligible',
]:
    assert token in dynamic_text, token

print("PASS: Dynamic Pi Planner fails closed for electrical WW unless source=BOILER")

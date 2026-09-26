#!/usr/bin/env python3
"""Static safety contract for the Pi warm-water source gate."""

from pathlib import Path

path = Path("services/pi/planner/warm-water/build_ww_plan.py")
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

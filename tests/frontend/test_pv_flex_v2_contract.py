#!/usr/bin/env python3
"""Static contract checks for the PV & Flex Analysis V2 frontend."""
from pathlib import Path

index=Path("frontend/pv-flex/index.html").read_text()
state=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()
css=Path("frontend/pv-flex/styles/pv-flex.css").read_text()

for token in ("PV & Flex Analyse","Forecast versus werkelijk PV-gebruik","EV uit PV","Overig eigen gebruik","Export","HEATING PREHEAT V0.3 · SHADOW","Voorverwarming"):
    assert token in index, token
for removed in ("flex-panel","ww-lane","evlane","EV laden","heating-note","WW boiler","Heating Flex"):
    assert removed not in index, f"duplicate/legacy render surface remains: {removed}"
assert 'const API_ROOT="/web/analysis/pv-flex/day"' in state
assert '{cache:"no-store"}' in state
assert 'EMS_WEB_PV_FLEX_ANALYSIS_V1' in state
assert 'PREHEAT_ROOT="/web/planner/heating-preheat-shadow"' in state
assert 'EMS_WEB_HEATING_PREHEAT_SHADOW_V1' in state
assert 'FLEX_PRIORITY_ROOT="/web/planner/flex-priority-shadow"' in state
assert 'EMS_WEB_FLEX_PRIORITY_SHADOW_V1' in state
assert "forecast?.confidence" in render
assert 'function lane(' not in render
assert 'evPowerW' in render
assert 'loadHeatingPreheatShadow' in render
assert 'loadFlexPriorityShadow' in render
assert 'Heating eerst' in render
assert 'EV eerst' in render
assert 'EV residual via P1' in render
assert 'roomPlannerState' in render
assert 'SHADOW_GRANT' in render
assert 'Kamer niet klaar voor planner-grant' in render
assert 'Planner:' in render
assert 'PREHEAT_READY_FOR_GRANT' in render
assert 'Volgende shadow-stap' in render
assert 'Planner grant' in render
assert 'CV actief' in render
assert 'Tesla werkelijk' in render
assert 'evPvW' in render
assert 'class:cls' in render
assert '.pv-ev' in css and '.pv-self' in css and '.pv-export' in css
assert '.preheat-room' in css and '.preheat-state' in css
assert '.evbar' not in css and '.evlane' not in css
assert 'boilerPowerW' not in render
assert "fetch(" not in render, "renderer must use state adapter"
print("PASS: PV & Flex Analysis V2 single-render frontend contract")

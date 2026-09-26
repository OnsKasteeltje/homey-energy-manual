#!/usr/bin/env python3
"""Static contract checks for the PV & Flex Analysis V2 frontend."""
from pathlib import Path

index=Path("frontend/pv-flex/index.html").read_text()
state=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()
css=Path("frontend/pv-flex/styles/pv-flex.css").read_text()

for token in ("PV & Flex Analyse","Forecast versus werkelijk PV-gebruik","EV uit PV","Overig eigen gebruik","Export"):
    assert token in index, token
for removed in ("flex-panel","ww-lane","evlane","EV laden","heating-note","WW boiler","Heating Flex"):
    assert removed not in index, f"duplicate/legacy render surface remains: {removed}"
assert 'const API_ROOT="/web/analysis/pv-flex/day"' in state
assert '{cache:"no-store"}' in state
assert 'EMS_WEB_PV_FLEX_ANALYSIS_V1' in state
assert "forecast?.confidence" in render
assert 'function lane(' not in render
assert 'evPowerW' in render
assert 'Tesla werkelijk' in render
assert 'evPvW' in render
assert 'class:cls' in render
assert '.pv-ev' in css and '.pv-self' in css and '.pv-export' in css
assert '.evbar' not in css and '.evlane' not in css
assert 'boilerPowerW' not in render
assert "fetch(" not in render, "renderer must use state adapter"
print("PASS: PV & Flex Analysis V2 single-render frontend contract")

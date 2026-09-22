#!/usr/bin/env python3
"""Static contract checks for the PV & Flex Analysis V2 frontend."""
from pathlib import Path

index=Path("frontend/pv-flex/index.html").read_text()
state=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()

for token in ("PV & Flex Analyse","Forecast versus werkelijke PV"):
    assert token in index, token
for removed in ("flex-panel","ev-lane","ww-lane","heating-note","WW boiler","Heating Flex"):
    assert removed not in index, f"duplicate/legacy render surface remains: {removed}"
assert 'const API_ROOT="/web/analysis/pv-flex/day"' in state
assert '{cache:"no-store"}' in state
assert 'EMS_WEB_PV_FLEX_ANALYSIS_V1' in state
assert "forecast?.confidence" in render
assert 'function lane(' not in render
assert 'evPowerW' not in render and 'boilerPowerW' not in render
assert "fetch(" not in render, "renderer must use state adapter"
print("PASS: PV & Flex Analysis V2 single-render frontend contract")

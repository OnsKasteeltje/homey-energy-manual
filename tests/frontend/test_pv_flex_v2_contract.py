#!/usr/bin/env python3
"""Static contract checks for the PV & Flex Analysis V2 frontend."""
from pathlib import Path

index=Path("frontend/pv-flex/index.html").read_text()
state=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()

for token in ("PV & Flex Analyse","Forecast versus werkelijke PV","EV","WW boiler","Heating Flex"):
    assert token in index, token
assert 'const API_ROOT="/web/analysis/pv-flex/day"' in state
assert '{cache:"no-store"}' in state
assert 'EMS_WEB_PV_FLEX_ANALYSIS_V1' in state
assert "forecast?.confidence" in render
assert "evPowerW" in render and "boilerPowerW" in render
assert "fetch(" not in render, "renderer must use state adapter"
print("PASS: PV & Flex Analysis V2 frontend contract")

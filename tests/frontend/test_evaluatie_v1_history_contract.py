#!/usr/bin/env python3
"""Evaluatie must not mistake V2 archive values for actual canonical V1."""
from pathlib import Path
src=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()
html=Path("frontend/pv-flex/index.html").read_text()
api=Path("services/pi/api/web-data/server.py").read_text()
for token in ("/web/analysis/planner/day/","EMS_WEB_PLANNER_EVALUATION_V1",
              "forecast:historical?.forecast||null","plan:historical?.plan||null"):
    assert token in src,token
for token in ("PV-FORECAST V1","Tesla gepland","Warm water gepland","archive-status"):
    assert token in html,token
for token in ("planned-ev-line","planned-ww-line","boilerPowerW","planSlots","historicalPlannerAvailable"):
    assert token in render,token
assert '["web", "analysis", "planner", "day"]' in api
assert "fetch(" not in render
print("PASS: V1 evaluation source and no V2 display fallback")

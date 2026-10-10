#!/usr/bin/env python3
"""Decision-centric retrospective evaluation uses archived V1, not V2 or fixed-lead scoring."""
from pathlib import Path
src=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()
html=Path("frontend/pv-flex/index.html").read_text()
api=Path("services/pi/api/web-data/server.py").read_text()
for token in ("/web/analysis/planner/day/","EMS_WEB_PLANNER_EVALUATION_V2",
              "forecast:historical?.forecast||null","plan:historical?.plan||null"):
    assert token in src,token
for token in ("PV BIJ BESLISSING","Besloten versus gemeten energie",
              "Quooker gepland","decision-evidence","archive-status"):
    assert token in html,token
for token in ("renderEvidence","planned-quooker-line","boilerPowerW",
              "quookerPlanW","planSlots","historicalPlannerAvailable","Gemiste kans"):
    assert token in render,token
for token in ('"SAME_AS_VALID_PLAN_DECISION"','"quookerOpportunityAllowed"',
              '"quookerMode"','"quookerPlanW"','"wwSourceMode"'):
    assert token in api,token
assert "12 uur vooraf" not in html
assert "kwartieren met voldoende P1/PV-dekking" in render
assert "Nog geen beoordeling: kwartier niet afgesloten" in render
assert "Onvoldoende meetgegevens: P1/PV-dekking onvolledig" in render
assert "renderEvidence(x)" not in render
assert "fetch(" not in render
print("PASS: evaluation uses one decision-time PV and flex snapshot, with provenance and uncertainty")

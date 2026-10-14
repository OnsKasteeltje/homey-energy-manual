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
for token in ("Besloten versus gemeten energie","Quooker gepland","pv-chart",
              "daily-report-panel","day-title"):
    assert token in html,token
for token in ("planned-quooker-line","quookerPlanW",
              "slotEvidence","closestEvaluationSeries","renderDailyReport"):
    assert token in render,token
for token in ("decision-evidence","archive-status"):
    assert f'id="{token}"' not in html,token
assert '<section class="intro">' not in html
for token in ('"SAME_AS_VALID_PLAN_DECISION"','"quookerOpportunityAllowed"',
              '"quookerMode"','"quookerPlanW"','"wwSourceMode"'):
    assert token in api,token
assert "12 uur vooraf" not in html
assert "Dekking kalenderdag" in render
assert 'id="report-self"' in html
assert 'accounting.pvSelfConsumedKWh' in render
assert 'id="kpi-' not in html
assert "function slotEvidence(slot,nowMs=Date.now())" in render
assert "renderEvidence(" not in render
assert "renderEvidence(x)" not in render
assert "fetch(" not in render
print("PASS: evaluation uses one decision-time PV and flex snapshot, with provenance and uncertainty")

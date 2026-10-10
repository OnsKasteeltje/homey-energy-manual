#!/usr/bin/env python3
"""Planner must display V1 values actually embedded in the Dynamic Pi Planner."""
from pathlib import Path

html=Path("frontend/planner/index.html").read_text()
js=Path("frontend/planner/render/planner.js").read_text()
css=Path("frontend/planner/styles/planner.css").read_text()
api=Path("services/pi/api/web-data/server.py").read_text()
assert "EMS-planning" in html
for label in ("PV voorspeld","Tesla gepland","Warm water gepland","Export verwacht","Import verwacht","EV-deadline"):
    assert label in html or label in js, label
for token in ("/web/planner/current", "EMS_WEB_DYNAMIC_PLAN_V1",
              "evPlanW","wwPlanW","gridImportAfterFlexW","gridExportAfterFlexW",
              "evReason","wwReason","validUntil"):
    assert token in js and token in api, token
assert "/web/planner/pv-forecast" not in js, "Planner may not show V2 as active source"
assert "innerHTML" not in js
assert ".importline" in css
print("PASS: Planner uses canonical V1 Dynamic Pi Planner; V2 remains rollback-only")

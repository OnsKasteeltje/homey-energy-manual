#!/usr/bin/env python3
"""Read-only contract test for the actual Dynamic Pi Planner projection."""
import importlib.util
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE = Path("services/pi/api/web-data/server.py")

spec = importlib.util.spec_from_file_location("ems_web_dynamic_plan", SOURCE)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

now = datetime.now(timezone.utc)
origin = now.replace(minute=now.minute//15*15, second=0, microsecond=0)
iso = lambda dt: dt.isoformat().replace("+00:00", "Z")
slot = {
    "pvForecastW": 2200, "evPlanW": 1400, "wwPlanW": 0,
    "gridImportAfterFlexW": 0, "gridExportAfterFlexW": 400,
    "confidence": 0.8, "evAllocationReason": "PV_OPPORTUNITY",
    "wwAllocationReason": "BLOCKED_SOURCE_CV",
}
source = {
    "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
    "mode": "PURE_SHADOW", "readOnly": True, "control_writes": False,
    "generated_at": iso(now-timedelta(seconds=10)),
    "validUntil": iso(now+timedelta(minutes=15)),
    "guardrails": {"wwSourceMode":"CV", "secret":"never expose"},
    "slots":[dict(slot,slot_start_utc=iso(origin+timedelta(minutes=15*i))) for i in range(96)],
    "secret":"not exposed",
}

with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/"plan.json"
    api.DYNAMIC_PLAN_FILE=str(path)
    def project(data):
        path.write_text(json.dumps(data))
        return api.dynamic_planner_resource()
    result=project(source)
    assert result["schema"]=="EMS_WEB_DYNAMIC_PLAN_V1"
    assert result["forecastSource"]=="PV_V1_EMBEDDED_IN_DYNAMIC_PLAN"
    assert result["controlWrites"] is False
    assert len(result["slots"])==96
    assert result["slots"][0]["pvForecastW"]==2200
    assert result["slots"][0]["evPlanW"]==1400
    assert result["slots"][0]["evReason"]=="PV_OPPORTUNITY"
    assert "secret" not in json.dumps(result)
    assert "guardrails" not in result
    assert "geometryBasis" not in result
    for mutation in (
        lambda d: d.update(validUntil=iso(now-timedelta(seconds=1))),
        lambda d: d["slots"].pop(),
        lambda d: d["slots"][2].update(slot_start_utc=d["slots"][1]["slot_start_utc"]),
        lambda d: d["slots"][3].update(evPlanW=-1),
        lambda d: d.update(control_writes=True),
    ):
        mutated=json.loads(json.dumps(source))
        mutation(mutated)
        try: project(mutated)
        except ValueError: pass
        else: raise AssertionError("invalid plan must fail closed")

    text=SOURCE.read_text()
    assert 'if path.path == "/web/planner/current":' in text
    assert '"/web/planner/pv-forecast"' in text, "V2 rollback route must remain during cutover"
    print("PASS: dynamic V1 planner allowlist, freshness, 96-slot axis, no writes")

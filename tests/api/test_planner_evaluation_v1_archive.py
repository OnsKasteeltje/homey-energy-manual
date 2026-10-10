#!/usr/bin/env python3
"""Decision-time evidence: original forecast must belong to same valid plan, not 12h weather."""
import importlib.util
import json
import sqlite3
import tempfile
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec=importlib.util.spec_from_file_location("eval_server","services/pi/api/web-data/server.py")
api=importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
def iso(t): return t.isoformat().replace("+00:00","Z")
slot=datetime(2026,10,8,22,tzinfo=timezone.utc)
axis=[iso(slot+timedelta(minutes=15*i)) for i in range(96)]

def write(con,generated,valid,pv,ev,quooker,mode="OPPORTUNITY"):
    plan={
        "schema":"EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
        "mode":"PURE_SHADOW","readOnly":True,"control_writes":False,
        "generated_at":iso(generated),
        "guardrails":{"wwSourceMode":"CV","secret":"not exported"},
        "slots":[{
            "slot_start_utc":s,"pvForecastW":pv,"confidence":0.7,
            "evPlanW":ev,"wwPlanW":0,"quookerPlanW":quooker,
            "quookerMode":mode,"quookerOpportunityAllowed":mode=="OPPORTUNITY",
            "evAllocationReason":"PV_OPPORTUNITY",
            "wwAllocationReason":"BLOCKED_CV",
            "gridImportAfterFlexW":0,"gridExportAfterFlexW":300,
            "teslaAvailableForecast":True,
            "secret":"not exported",
        } for s in axis],
    }
    data=json.dumps({"plan":plan}).encode()
    con.execute("INSERT INTO planner_snapshots VALUES(?,?,?)",
                (iso(generated),iso(valid),zlib.compress(data)))

with tempfile.TemporaryDirectory() as tmp:
    db=Path(tmp)/"history.sqlite"
    api.PLANNER_HISTORY_DB=str(db)
    con=sqlite3.connect(db)
    con.execute("CREATE TABLE planner_snapshots (generated_at_utc TEXT,valid_until_utc TEXT,snapshot_zlib BLOB)")
    old=datetime(2026,10,8,9,tzinfo=timezone.utc)
    recent=slot-timedelta(minutes=10)
    future=slot+timedelta(minutes=5)
    write(con,old,old+timedelta(minutes=15),1800,100,0)
    write(con,recent,slot+timedelta(minutes=10),4900,1400,1000,"FORCED_ON")
    write(con,future,future+timedelta(minutes=15),9000,9000,2000)
    con.commit()
    con.close()
    result=api.planner_evaluation_resource("2026-10-09")
    assert len(result["series"])==96
    assert result["schema"]=="EMS_WEB_PLANNER_EVALUATION_V2"
    assert result["forecastSource"]=="ARCHIVED_CANONICAL_V1_DYNAMIC_PLAN"
    assert result["forecastSelection"]["kind"]=="SAME_AS_VALID_PLAN_DECISION"
    assert result["controlWrites"] is False
    first=result["series"][0]
    assert first["forecast"]["pvForecastW"]==4900,first
    assert first["forecast"]["generatedAt"]==iso(recent)
    assert first["plan"]["evPlanW"]==1400
    assert first["plan"]["quookerPlanW"]==1000
    assert first["plan"]["quookerMode"]=="FORCED_ON"
    assert first["plan"]["quookerOpportunityAllowed"] is False
    assert first["plan"]["wwSourceMode"]=="CV"
    assert first["plan"]["teslaAvailableForecast"] is True
    assert first["plan"]["generatedAt"]==first["forecast"]["generatedAt"]
    assert first["forecast"]["pvForecastW"]!=1800, "12-hour forecast must not drive EMS evaluation"
    assert first["forecast"]["pvForecastW"]!=9000, "future run is hindsight"
    assert "secret" not in json.dumps(result)
    assert result["summary"]["quookerPlanSlots"]>=1
    assert result["summary"]["plannedQuookerKWh"] is not None
    # Missing or incomplete archival evidence must stay unknown.
    con=sqlite3.connect(db)
    con.execute("DELETE FROM planner_snapshots")
    con.commit()
    con.close()
    missing=api.planner_evaluation_resource("2026-10-09")
    assert missing["summary"]["forecastKWh"] is None
    assert missing["summary"]["plannedQuookerKWh"] is None
    assert all(row["forecast"] is None and row["plan"] is None for row in missing["series"])
    print("PASS: single original plan V1 PV, Tesla/WW/Quooker, no hindsight, no fabricated evidence")

#!/usr/bin/env python3
"""Regression: V1 forecast uses 12-hour lead; flex uses last valid earlier plan."""
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

def write(con,generated,valid,pv,ev):
    plan={"schema":"EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3","mode":"PURE_SHADOW",
          "readOnly":True,"control_writes":False,"generated_at":iso(generated),
          "slots":[{"slot_start_utc":s,"pvForecastW":pv,"confidence":0.7,
                    "evPlanW":ev,"wwPlanW":0,"gridImportAfterFlexW":0,
                    "gridExportAfterFlexW":300} for s in axis]}
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
    write(con,old,old+timedelta(minutes=15),1800,100)
    write(con,recent,slot+timedelta(minutes=10),4900,1400)
    write(con,future,future+timedelta(minutes=15),9000,9000)
    con.commit()
    con.close()
    result=api.planner_evaluation_resource("2026-10-09")
    assert len(result["series"])==96
    assert result["forecastSource"]=="ARCHIVED_CANONICAL_V1_DYNAMIC_PLAN"
    first=result["series"][0]
    assert first["forecast"]["pvForecastW"]==1800
    assert first["forecast"]["leadMinutes"]==780
    assert first["plan"]["evPlanW"]==1400
    assert first["plan"]["generatedAt"]==iso(recent)
    assert result["summary"]["planSlots"]==1
    assert result["controlWrites"] is False
print("PASS: V1 forecast 12h and last valid plan; no hindsight")

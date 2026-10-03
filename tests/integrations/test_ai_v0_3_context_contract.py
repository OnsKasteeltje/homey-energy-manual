#!/usr/bin/env python3
import importlib.util
import json
import sqlite3
import tempfile
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_ai_v03_contract", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_history(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE devices (
        id INTEGER PRIMARY KEY,
        source TEXT,
        source_device_id TEXT,
        device_key TEXT UNIQUE,
        name TEXT,
        device_type TEXT
    );
    CREATE TABLE metrics (
        id INTEGER PRIMARY KEY,
        metric_key TEXT UNIQUE,
        unit TEXT,
        value_type TEXT,
        description TEXT
    );
    CREATE TABLE measurements (
        id INTEGER PRIMARY KEY,
        ts_utc TEXT,
        device_id INTEGER,
        metric_id INTEGER,
        value_real REAL,
        value_text TEXT,
        quality TEXT,
        source_resolution_seconds INTEGER
    );
    CREATE TABLE measurements_15m (
        slot_start_utc TEXT,
        device_id INTEGER,
        metric_id INTEGER,
        value_avg REAL,
        value_min REAL,
        value_max REAL,
        sample_count INTEGER,
        energy_wh REAL,
        quality TEXT
    );
    CREATE TABLE pv_forecast_v2_archive (
        slot_start_utc TEXT,
        forecast_w REAL,
        confidence REAL,
        model_basis TEXT,
        generated_at TEXT
    );
    INSERT INTO metrics VALUES (1,'electrical_power_w','W','number','power');
    INSERT INTO metrics VALUES (2,'active',NULL,'boolean','active');
    """)
    devices = [
        (1,'grid_p1'), (2,'pv_solaredge'), (3,'pv_goodwe4200'),
        (4,'pv_goodwe2000'), (5,'tesla'), (6,'boiler'),
        (7,'quatt_cic'), (8,'washer'), (9,'dryer')
    ]
    for ident,key in devices:
        con.execute(
            "INSERT INTO devices(id,source,source_device_id,device_key,name,device_type) VALUES(?,?,?,?,?,?)",
            (ident,'test','test:'+key,key,key,'test'),
        )
    ts='2026-10-03T12:00:00Z'
    power = {
        1:-400.0, 2:2000.0, 3:1200.0, 4:800.0,
        5:1600.0, 6:500.0, 7:700.0,
    }
    for device_id,value in power.items():
        con.execute(
            "INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality,source_resolution_seconds) VALUES(?,?,?,?,?,?)",
            (ts,device_id,1,value,'observed',300),
        )
    con.execute("INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality,source_resolution_seconds) VALUES(?,?,?,?,?,?)",
                (ts,8,2,1.0,'observed',300))
    con.execute("INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality,source_resolution_seconds) VALUES(?,?,?,?,?,?)",
                (ts,9,2,0.0,'observed',300))

    energy = {
        1:-100.0, 2:500.0, 3:300.0, 4:200.0, 5:400.0, 6:125.0,
    }
    for device_id,wh in energy.items():
        avg = power.get(device_id, 0.0)
        con.execute(
            "INSERT INTO measurements_15m(slot_start_utc,device_id,metric_id,value_avg,value_min,value_max,sample_count,energy_wh,quality) VALUES(?,?,?,?,?,?,?,?,?)",
            (ts,device_id,1,avg,avg,avg,3,wh,'complete'),
        )
    con.execute(
        "INSERT INTO pv_forecast_v2_archive(slot_start_utc,forecast_w,confidence,model_basis,generated_at) VALUES(?,?,?,?,?)",
        (ts,3600.0,0.9,'TEST_MODEL','2026-10-03T00:00:00Z'),
    )
    con.commit()
    con.close()


def create_planner(path):
    con=sqlite3.connect(path)
    con.execute("""
    CREATE TABLE planner_snapshots (
        id INTEGER PRIMARY KEY,
        generated_at_utc TEXT,
        snapshot_zlib BLOB
    )
    """)
    snap={
        "schema":"EMS_PI_PLANNER_DECISION_SNAPSHOT_V0.2",
        "objective":"MAXIMIZE_PV_SELF_CONSUMPTION",
        "context":{
            "contextSource":"PLAN_EMBEDDED_DECISION_OUTPUT",
            "realtime":{"actualP1ExportW":400,"recentLocalAccuracy":0.95,"p1CorrectionPolicy":"TEST"},
            "tesla":{"deadline":{"active":False,"connected":True,"remainingKWh":3.0}},
        },
        "plan":{
            "objective":"MAXIMIZE_PV_SELF_CONSUMPTION",
            "guardrails":{"wwSourceMode":"CV","wwElectricalFlexEligible":False,"teslaRole":"SECONDARY_FLEX_LOAD_WHEN_WW_COMFORT_REMAINS_FEASIBLE"},
            "slots":[{
                "slot_start_utc":"2026-10-03T12:00:00Z",
                "localDate":"2026-10-03",
                "baseLoadForecastW":500,
                "pvForecastW":3600,
                "quattForecastW":100,
                "forecastExportBeforeFlexW":3000,
                "correctedExportBeforeFlexW":1200,
                "confidence":0.9,
                "wwPlanW":0,
                "wwAllocationReason":"BLOCKED_SOURCE_CV",
                "wwCandidateSourceEligible":False,
                "evPlanW":2300,
                "evPlanA":10,
                "evPlanPhaseMode":"1P",
                "evAllocationReason":"DYNAMIC_PV_1P",
                "evOpportunityWindowClass":"1P",
                "evOpportunityWindowSelectionReason":"PV_OPPORTUNITY",
                "gridImportAfterFlexW":0,
                "gridExportAfterFlexW":0
            }],
        },
    }
    blob=zlib.compress(json.dumps(snap).encode("utf-8"))
    con.execute("INSERT INTO planner_snapshots(generated_at_utc,snapshot_zlib) VALUES(?,?)",
                ('2026-10-03T11:55:00Z', sqlite3.Binary(blob)))
    con.commit()
    con.close()


def main():
    ai=load_module()
    with tempfile.TemporaryDirectory() as temp:
        history=Path(temp)/"history.sqlite"
        planner=Path(temp)/"planner.sqlite"
        create_history(history)
        create_planner(planner)
        ai.HISTORY_DB=str(history)
        ai.PLANNER_DB=str(planner)

        day=date(2026,10,3)
        anchors=ai._question_anchors("Wat gebeurde er rond 14:00?", day, {}, [])
        assert len(anchors)==1 and anchors[0].hour==14

        timeline=ai._timeline(day)
        assert len(timeline)==1
        point=timeline[0]
        assert point["boilerW"]==500
        assert point["quattW"]==700
        assert point["washerActive"] is True
        assert point["dryerActive"] is False

        planner_window=ai._planner_decision_window(day, anchors)
        assert len(planner_window)==1
        assert planner_window[0]["snapshotAgeMinutes"]==5.0
        assert planner_window[0]["action"]["evAllocationReason"]=="DYNAMIC_PV_1P"
        assert planner_window[0]["action"]["evPlanW"]==2300
        assert planner_window[0]["action"]["wwAllocationReason"]=="BLOCKED_SOURCE_CV"

        forecast=ai._forecast_vs_actual_15m(day, anchors)
        assert forecast["available"] is True
        assert forecast["summary"]["slotCount"]==1
        assert forecast["summary"]["actualKWh"]==1.0
        assert forecast["summary"]["forecastKWh"]==0.9
        assert forecast["summary"]["biasKWhActualMinusForecast"]==0.1
        assert forecast["slots"][0]["forecastLeadMinutes"]==720.0
        assert forecast["slots"][0]["exportKWh"]==0.1

    print("PASS: AI V0.3 context evidence contract")


if __name__ == "__main__":
    main()

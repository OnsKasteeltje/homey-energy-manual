#!/usr/bin/env python3
import importlib.util
import json
import sqlite3
import tempfile
import zlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_ai_v04_contract", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_planner_db(path):
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE flex_context_snapshots (
            id INTEGER PRIMARY KEY,
            captured_at_utc TEXT,
            semantic_hash TEXT,
            snapshot_zlib BLOB
        )
    """)
    snap = {
        "schema": "EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1",
        "capturedAt": "2026-10-03T13:58:00Z",
        "readOnly": True,
        "controlWrites": False,
        "historicalBackfill": False,
        "heating": {
            "generatedAt": "2026-10-03T13:54:00Z",
            "baselineAuthority": "HONEYWELL",
            "house": {"baselineHeatingDemandPresent": False},
            "cvGuard": {"status": "OK", "reason": "CURRENT_QUATT_OBSERVER", "cvActive": False},
            "rooms": [{
                "key": "serre",
                "preheatScope": True,
                "current": {"temperature_C": 19.8},
                "candidate": {"status": "ELIGIBLE_UP_TRANSITION"},
                "shadow": {"state": "PREHEAT_READY_FOR_GRANT", "reason": "AWAITING_CENTRAL_PV_PRIORITY"},
            }],
        },
        "priority": {
            "generatedAt": "2026-10-03T13:57:00Z",
            "heating": {"readyRooms": ["serre"]},
            "ev": {"urgency": "NONE"},
            "decision": {
                "priorityOwner": "HEATING",
                "heatingShadowGrant": "SHADOW_GRANT",
                "reason": "HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE",
                "physicalWriteAllowed": False,
            },
        },
        "progression": {
            "generatedAt": "2026-10-03T13:57:20Z",
            "physicalWriteAllowed": False,
            "sourceFreshness": {
                "heating": {"status": "OK"},
                "priority": {"status": "OK"},
            },
            "rooms": [{
                "key": "serre",
                "currentTemperature_C": 19.8,
                "futureHoneywellTarget_C": 21.0,
                "heatingEligibility": {
                    "state": "PREHEAT_READY_FOR_GRANT",
                    "reason": "AWAITING_CENTRAL_PV_PRIORITY",
                },
                "planner": {
                    "domainGrant": "SHADOW_GRANT",
                    "priorityReason": "HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE",
                },
                "progression": {
                    "state": "STEP_WAIT",
                    "reason": "SHADOW_STEP_STARTED",
                    "activeStepTarget_C": 20.3,
                    "activeStepReached": False,
                    "physicalWritePerformed": False,
                },
            }],
        },
        "warmWaterInput": {
            "warmWater": {"goalReached": False, "remainingFallbackMin": 60}
        },
        "warmWaterSeasonal": {
            "status": "OK", "currentMode": "CV", "advice": "KEEP_CURRENT"
        },
        "energyState": {
            "hotWater": {"mode": False, "boilerOn": False, "boilerPowerW": 0}
        },
    }
    con.execute(
        "INSERT INTO flex_context_snapshots(captured_at_utc,semantic_hash,snapshot_zlib) VALUES(?,?,?)",
        ("2026-10-03T13:58:00Z", "x", sqlite3.Binary(zlib.compress(json.dumps(snap).encode()))),
    )
    con.commit()
    con.close()


def create_history_db(path):
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE quooker_control_events (
            id INTEGER PRIMARY KEY,
            ts_utc TEXT,
            control_mode TEXT,
            control_target_on INTEGER,
            control_reason TEXT,
            modeled_power_w REAL,
            avg_grid_w REAL,
            p1_fresh INTEGER,
            start_export_w REAL,
            stop_import_w REAL,
            actuator_control_valid INTEGER,
            actuator_control_fresh INTEGER,
            actuator_desired_on INTEGER,
            actuator_actual_on INTEGER,
            actuator_would_write INTEGER,
            actuator_reason TEXT,
            detector_valid INTEGER,
            detector_switch_on INTEGER,
            detector_active INTEGER,
            detector_status TEXT,
            detector_power_w REAL,
            detector_reason TEXT,
            detector_last_heating_at TEXT,
            detector_last_heating_power_w REAL,
            physical_write_performed INTEGER,
            raw_json TEXT
        )
    """)
    raw = json.dumps({
        "actuator": {
            "schema": "EM2_QUOOKER_ACTUATOR_STATUS_V0.2",
            "mode": "LIVE",
            "controlValid": True,
            "controlFresh": True,
            "desiredOn": True,
            "actualOnBefore": False,
            "actualOnAfter": True,
            "physicalWritePerformed": True,
            "writeError": None,
            "reason": "OPPORTUNITY_START_EXPORT",
            "safety": {
                "shadow": False,
                "deviceWrites": True,
                "soleWriterClaimed": True,
            },
        }
    })
    con.execute(
        """
        INSERT INTO quooker_control_events VALUES
        (1,'2026-10-03T14:00:00Z','OPPORTUNITY',1,'OPPORTUNITY_START_EXPORT',
         1580,-2200,1,1250,600,1,1,1,NULL,NULL,'OPPORTUNITY_START_EXPORT',
         1,1,0,'ON_IDLE',0,'ON_IDLE_BASELINE_TRACK','2026-10-03T12:30:00Z',
         1570,0,?)
        """,
        (raw,),
    )
    con.commit()
    con.close()


def main():
    ai = load_module()
    with tempfile.TemporaryDirectory() as temp:
        planner = Path(temp) / "planner.sqlite"
        history = Path(temp) / "history.sqlite"
        create_planner_db(planner)
        create_history_db(history)
        ai.PLANNER_DB = str(planner)
        ai.HISTORY_DB = str(history)

        day = date(2026, 10, 3)
        anchors = ai._question_anchors("Waarom niet rond 16:00?", day, {}, [])
        flex = ai._flex_context_window(day, anchors)
        assert len(flex) == 1
        assert flex[0]["snapshotAgeMinutes"] == 2.0
        room = flex[0]["progression"]["rooms"][0]
        assert room["planner"]["domainGrant"] == "SHADOW_GRANT"
        assert room["progression"]["physicalWritePerformed"] is False

        q = ai._quooker_events(day)
        assert len(q) == 1
        assert q[0]["control"]["targetOn"] is True
        assert q[0]["detector"]["status"] == "ON_IDLE"
        assert q[0]["actuator"]["schema"] == "EM2_QUOOKER_ACTUATOR_STATUS_V0.2"
        assert q[0]["actuator"]["mode"] == "LIVE"
        assert q[0]["actuator"]["actualOnBefore"] is False
        assert q[0]["actuator"]["actualOnAfter"] is True
        assert q[0]["actuator"]["physicalWritePerformed"] is True
        assert q[0]["physicalWritePerformed"] is True

        ai._load_performance = lambda _day: {
            "schema": "EMS_PI_DAY_PERFORMANCE_V0.1",
            "surplusWindowsForReplay": [],
        }
        ai._ev_telemetry = lambda _day: []
        ai._ev_control_events = lambda _day: []
        ai._timeline = lambda _day: []
        ai._planner_decision_window = lambda _day, _anchors: []
        ai._forecast_vs_actual_15m = lambda _day, _anchors: {
            "available": True, "summary": {}, "slots": []
        }
        ai._load_health = lambda: {"schema": "EMS_PI_HEALTH_V0.1", "status": "HEALTHY"}

        evidence = ai.build_evidence(day, "Waarom niet rond 16:00?")
        assert evidence["schema"] == "EMS_AI_EVIDENCE_V0.4"
        assert len(evidence["flexContextWindow"]) == 1
        assert len(evidence["quookerEvents"]) == 1
        assert any(
            "Quooker actuator mode is evidence-driven" in item
            for item in evidence["limitations"]
        )

    print("PASS: AI V0.4 flex context contract")


if __name__ == "__main__":
    main()

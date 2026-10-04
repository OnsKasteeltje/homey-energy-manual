#!/usr/bin/env python3
"""Regression for EV realtime reason projection into EMS AI evidence."""

from datetime import date
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile


SERVER = Path("services/pi/api/analysis/server.py")
spec = importlib.util.spec_from_file_location("ems_ai_analysis_server", SERVER)
server = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(server)


payload = {
    "schema": "EMS_HOMEY_EV_CONTROL_EVIDENCE_V0.1",
    "intent": {
        "schema": "EM2_POWER_INTENT_V0.2",
        "policyProjection": {
            "reason": "1P_TO_OFF_ROLLING_LOW",
            "realtime": {
                "applied": True,
                "phaseShadow": {
                    "mode": "OFF",
                    "requestedA": 0,
                    "requestedW": 0,
                    "phaseReason": "1P_TO_OFF_ROLLING_LOW",
                    "currentReason": "MODE_OFF",
                    "availableTotalW": 420,
                    "availableTotalAvg2mW": 980,
                    "rollingReady": True,
                    "rollingCoverageMs": 120000,
                },
            },
        },
        "targets": {
            "ev": {
                "target_W": 0,
                "status": "IDLE",
                "source": "HOMEY_PHASE_CURRENT_CONTROLLER_V0.1",
                "phase_mode": "OFF",
                "phase_requested_A": 0,
            },
        },
    },
    "gate": {
        "status": "PASS",
        "errors": [],
    },
    "actuator": {
        "status": "STABLE",
        "reason": "OFF_ZERO_A_HOLD",
        "targetA": 0,
        "phaseMode": "OFF",
        "confirmedMode": "1P",
        "physicalWritePerformed": True,
    },
    "deviceHealth": {
        "status": "OK",
        "reason": "OK",
    },
}

with tempfile.TemporaryDirectory() as tmp:
    db_path = Path(tmp) / "history.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE ev_control_events (
                event_hash TEXT NOT NULL UNIQUE,
                ts_utc TEXT NOT NULL,
                source_revision INTEGER,
                control_revision TEXT,
                target_w REAL,
                requested_a REAL,
                phase_mode TEXT,
                gate_status TEXT,
                gate_errors_json TEXT,
                actuator_status TEXT,
                actuator_reason TEXT,
                actuator_target_a REAL,
                actuator_phase_mode TEXT,
                actuator_confirmed_mode TEXT,
                transition_stage TEXT,
                transition_failure TEXT,
                charge_state TEXT,
                device_health_status TEXT,
                device_health_reason TEXT,
                physical_write_performed INTEGER,
                raw_json TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO ev_control_events (
                event_hash, ts_utc, source_revision, control_revision,
                target_w, requested_a, phase_mode,
                gate_status, gate_errors_json,
                actuator_status, actuator_reason, actuator_target_a,
                actuator_phase_mode, actuator_confirmed_mode,
                transition_stage, transition_failure, charge_state,
                device_health_status, device_health_reason,
                physical_write_performed, raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "test-event",
                "2026-10-04T10:48:02Z",
                12886,
                "test-control-revision",
                0,
                0,
                "OFF",
                "PASS",
                "[]",
                "STABLE",
                "OFF_ZERO_A_HOLD",
                0,
                "OFF",
                "1P",
                "STABLE",
                None,
                "plugged_in_paused",
                "OK",
                "OK",
                1,
                json.dumps(payload),
            ),
        )

    server.HISTORY_DB = str(db_path)
    events = server._ev_control_events(date(2026, 10, 4))

assert len(events) == 1, events
event = events[0]
assert event["atLocal"].startswith("2026-10-04T12:48:02"), event
assert event["targetW"] == 0
assert event["gateStatus"] == "PASS"
assert event["intentReason"] == "1P_TO_OFF_ROLLING_LOW"
assert event["intentSource"] == "HOMEY_PHASE_CURRENT_CONTROLLER_V0.1"
assert event["realtimeApplied"] is True
assert event["realtimePhaseReason"] == "1P_TO_OFF_ROLLING_LOW"
assert event["realtimeCurrentReason"] == "MODE_OFF"
assert event["realtimeAvailableTotalW"] == 420
assert event["realtimeAvailableTotalAvg2mW"] == 980
assert event["realtimeRollingReady"] is True
assert event["realtimeRollingCoverageMs"] == 120000

malformed = server._ev_intent_reason_context("{not-json")
assert all(value is None for value in malformed.values()), malformed

print("PASS: EMS AI EV control evidence exposes recorded phase/current reasons")

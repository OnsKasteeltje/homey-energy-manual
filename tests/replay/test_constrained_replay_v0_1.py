#!/usr/bin/env python3

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/history/constrained_replay_v0_1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("constrained_replay_v0_1", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


replay = load_module()


def control_event(
    *,
    at,
    mode="3P",
    requested_a=6,
    offered_a=6,
    max_a=16,
    available_w=7000,
    rolling_w=7000,
    rolling_ready=True,
    current_reason="HOLD_A",
    phase_reason="HOLD_MODE",
    physical_settled=True,
    charge_state="plugged_in_charging",
    gate_status="PASS",
    actuator_status="STABLE",
    transition_failure=None,
    mode_since=None,
    deadline=False,
):
    if mode_since is None:
        mode_since = at - timedelta(minutes=10)
    raw = {
        "intent": {
            "policyRevision": "TEST",
            "policyProjection": {
                "reason": "TEST_REASON",
                "deadlineGuardApplied": deadline,
                "deadlineMaxA": max_a if deadline else None,
                "realtime": {
                    "eligible": True,
                    "applied": True,
                    "envelopeAllowed": True,
                    "maxA": max_a,
                    "phasePolicy": {
                        "start1p_W": 1500,
                        "enter3p_W": 4400,
                    },
                    "phaseShadow": {
                        "mode": mode,
                        "requestedA": requested_a,
                        "currentReason": current_reason,
                        "phaseReason": phase_reason,
                        "availableTotalW": available_w,
                        "availableTotalAvg2mW": rolling_w,
                        "rollingReady": rolling_ready,
                        "rollingCoverageMs": 120000,
                        "physicalTargetSettled": physical_settled,
                        "modeSinceAt": replay._iso_z(mode_since),
                        "offReentryDwellMs": 120000,
                        "onePTo3pDwellMs": 180000,
                    },
                },
            },
        },
        "deviceHealth": {
            "easee": {
                "offeredA": offered_a,
            },
        },
    }
    return replay.ControlEvent(
        at=at,
        requested_a=requested_a,
        phase_mode=mode,
        gate_status=gate_status,
        actuator_status=actuator_status,
        actuator_reason="TEST",
        actuator_target_a=requested_a,
        transition_stage=None,
        transition_failure=transition_failure,
        charge_state=charge_state,
        raw=raw,
    )


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)

    def test_disconnected_export_is_unavoidable_by_ev_scope(self):
        event = control_event(
            at=self.at,
            charge_state="plugged_out",
            requested_a=0,
            offered_a=0,
        )
        result = replay.classify_export_interval(
            at=self.at,
            export_w=3000,
            ev_w=0,
            event=event,
        )
        self.assertEqual(result["classification"], replay.CLASS_UNAVOIDABLE)
        self.assertEqual(result["reason"], "EV_NOT_CONNECTED")

    def test_bounded_3p_upscale_is_constraint_driven(self):
        event = control_event(
            at=self.at,
            requested_a=7,
            offered_a=7,
            available_w=7000,
            rolling_w=7000,
            current_reason="PREDICTIVE_UP_BOUNDED",
        )
        result = replay.classify_export_interval(
            at=self.at,
            export_w=2500,
            ev_w=4830,
            event=event,
        )
        self.assertEqual(result["classification"], replay.CLASS_CONSTRAINT)
        self.assertEqual(result["reason"], "CURRENT_RAMP_OR_SETTLING_LIMIT")

    def test_unused_3p_headroom_without_constraint_is_real_miss(self):
        event = control_event(
            at=self.at,
            requested_a=6,
            offered_a=6,
            available_w=7000,
            rolling_w=7000,
            current_reason="HOLD_A",
        )
        result = replay.classify_export_interval(
            at=self.at,
            export_w=2600,
            ev_w=4140,
            event=event,
        )
        self.assertEqual(result["classification"], replay.CLASS_MISSED)
        self.assertEqual(result["reason"], "3P_CURRENT_HEADROOM_UNUSED")
        self.assertGreater(result["additionalFeasibleW"], 0)

    def test_maximum_3p_current_is_unavoidable_by_ev_scope(self):
        event = control_event(
            at=self.at,
            requested_a=16,
            offered_a=16,
            available_w=14000,
            rolling_w=14000,
            current_reason="HOLD_A",
        )
        result = replay.classify_export_interval(
            at=self.at,
            export_w=2500,
            ev_w=11040,
            event=event,
        )
        self.assertEqual(result["classification"], replay.CLASS_UNAVOIDABLE)
        self.assertEqual(result["reason"], "EV_AT_MAX_3P_CURRENT")

    def test_off_reentry_dwell_is_constraint_driven(self):
        event = control_event(
            at=self.at,
            mode="OFF",
            requested_a=0,
            offered_a=0,
            available_w=5000,
            rolling_w=5000,
            current_reason="MODE_OFF",
            mode_since=self.at - timedelta(seconds=60),
        )
        result = replay.classify_export_interval(
            at=self.at,
            export_w=5000,
            ev_w=0,
            event=event,
        )
        self.assertEqual(result["classification"], replay.CLASS_CONSTRAINT)
        self.assertEqual(result["reason"], "OFF_REENTRY_DWELL_ACTIVE")

    def test_missing_control_event_is_never_guessed(self):
        result = replay.classify_export_interval(
            at=self.at,
            export_w=4000,
            ev_w=0,
            event=None,
        )
        self.assertEqual(result["classification"], replay.CLASS_INSUFFICIENT)
        self.assertEqual(result["reason"], "NO_EV_CONTROL_EVIDENCE")


class ReplayIntegrationTests(unittest.TestCase):
    def test_build_replay_uses_canonical_history_and_semantic_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ems-history.sqlite"
            con = sqlite3.connect(db)
            con.executescript(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_key TEXT NOT NULL UNIQUE
                );
                CREATE TABLE metrics (
                    id INTEGER PRIMARY KEY,
                    metric_key TEXT NOT NULL UNIQUE
                );
                CREATE TABLE measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    device_id INTEGER NOT NULL,
                    metric_id INTEGER NOT NULL,
                    value_real REAL,
                    quality TEXT
                );
                CREATE TABLE ev_control_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    requested_a REAL,
                    phase_mode TEXT,
                    gate_status TEXT,
                    actuator_status TEXT,
                    actuator_reason TEXT,
                    actuator_target_a REAL,
                    transition_stage TEXT,
                    transition_failure TEXT,
                    charge_state TEXT,
                    raw_json TEXT NOT NULL
                );
                CREATE TABLE semantic_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    subject TEXT,
                    provenance_class TEXT NOT NULL
                );
                """
            )
            devices = {
                "grid_p1": 1,
                "tesla": 2,
                "pv_solaredge": 3,
                "pv_goodwe4200": 4,
                "pv_goodwe2000": 5,
            }
            con.executemany(
                "INSERT INTO devices(id,device_key) VALUES (?,?)",
                [(v, k) for k, v in devices.items()],
            )
            con.execute(
                "INSERT INTO metrics(id,metric_key) VALUES (1,'electrical_power_w')"
            )

            start = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
            for minute in range(3):
                ts = replay._iso_z(start + timedelta(minutes=minute))
                values = {
                    "grid_p1": -2000,
                    "tesla": 4140,
                    "pv_solaredge": 3500,
                    "pv_goodwe4200": 2000,
                    "pv_goodwe2000": 1000,
                }
                con.executemany(
                    """
                    INSERT INTO measurements(
                        ts_utc,device_id,metric_id,value_real,quality
                    ) VALUES (?,?,?,?,?)
                    """,
                    [
                        (ts, devices[key], 1, value, "GOOD")
                        for key, value in values.items()
                    ],
                )

            event = control_event(
                at=start,
                requested_a=6,
                offered_a=6,
                available_w=6500,
                rolling_w=6500,
                current_reason="HOLD_A",
            )
            con.execute(
                """
                INSERT INTO ev_control_events(
                    ts_utc,requested_a,phase_mode,gate_status,
                    actuator_status,actuator_reason,actuator_target_a,
                    transition_stage,transition_failure,charge_state,raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    replay._iso_z(event.at),
                    event.requested_a,
                    event.phase_mode,
                    event.gate_status,
                    event.actuator_status,
                    event.actuator_reason,
                    event.actuator_target_a,
                    event.transition_stage,
                    event.transition_failure,
                    event.charge_state,
                    json.dumps(event.raw),
                ),
            )
            con.execute(
                """
                INSERT INTO semantic_events(
                    ts_utc,event_type,domain,subject,provenance_class
                ) VALUES (?,?,?,?,?)
                """,
                (
                    replay._iso_z(start),
                    "EV_CHARGING_STARTED",
                    "EV",
                    "tesla",
                    "OBSERVED_STATE",
                ),
            )
            con.commit()
            con.close()

            report = replay.build_replay(date(2026, 10, 4), db_path=db)

        self.assertEqual(report["schema"], "EMS_PI_CONSTRAINED_REPLAY_V0.1")
        self.assertTrue(report["readOnly"])
        self.assertFalse(report["controlWrites"])
        self.assertEqual(report["scope"], "EV_EXPORT_ONLY")
        self.assertEqual(report["coverage"]["controlEvents"], 1)
        self.assertEqual(report["coverage"]["semanticEvents"], 1)
        self.assertGreater(
            report["totals"]["byClassificationKWh"][replay.CLASS_MISSED],
            0,
        )
        self.assertGreater(report["totals"]["realMissedOpportunityCaptureKWh"], 0)
        self.assertEqual(
            report["windows"][0]["semanticEvents"][0]["eventType"],
            "EV_CHARGING_STARTED",
        )


if __name__ == "__main__":
    unittest.main()

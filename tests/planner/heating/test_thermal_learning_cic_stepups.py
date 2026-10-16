"""Targeted, stdlib-only regression: CV mode at scheduled step-up, and no evidence."""
import importlib.util
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[3]
          / "services/pi/planner/heating/build_thermal_learning_episodes.py")
spec = importlib.util.spec_from_file_location("thermal_learning", SOURCE)
learning = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learning)


def monday_schedule():
    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "zones": [{
            "key": "douwe_slaapkamer",
            "scheduleStatus": "OK",
            "weeklySchedule": [{
                "day_of_week": "monday",
                "switchpoints": [
                    {"time_of_day": "06:30:00", "heat_setpoint": 17.5},
                    {"time_of_day": "07:30:00", "heat_setpoint": 20.5},
                ],
            }],
        }],
    }


def database():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT UNIQUE);
        CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT UNIQUE);
        CREATE TABLE measurements (
            ts_utc TEXT, device_id INTEGER, metric_id INTEGER,
            value_real REAL, quality TEXT, source_resolution_seconds INTEGER
        );
        CREATE TABLE measurements_15m (
            slot_start_utc TEXT, device_id INTEGER, metric_id INTEGER,
            value_avg REAL, value_min REAL, value_max REAL,
            sample_count INTEGER, energy_wh REAL, quality TEXT
        );
        INSERT INTO devices (device_key) VALUES ('quatt_cic'), ('grid_p1');
        INSERT INTO metrics (metric_key)
            VALUES ('supervisory_control_mode'), ('gas_meter_m3');
    """)
    return db


def build(db):
    return learning.build_episodes(
        db, schedule=monday_schedule(),
        start=datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc),
        end=datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc),
        generated_at=datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc),
    )


class CicStepUpTest(unittest.TestCase):
    def test_scheduled_douwe_up_links_real_mode_and_gas_without_claiming_flame(self):
        db = database()
        try:
            with db:
                db.executemany(
                    """INSERT INTO measurements
                       (ts_utc, device_id, metric_id, value_real, quality,
                        source_resolution_seconds)
                       VALUES (?, ?, ?, ?, 'observed', ?)""",
                    [
                        ("2026-10-19T05:28:00Z", 1, 1, 2, 60),
                        ("2026-10-19T05:34:00Z", 1, 1, 2, 60),
                        ("2026-10-19T05:35:00Z", 1, 1, 3, 60),
                        ("2026-10-19T05:36:00Z", 1, 1, 4, 60),
                        ("2026-10-19T05:39:00Z", 1, 1, 2, 60),
                        ("2026-10-19T05:24:00Z", 2, 2, 18126.5, None),
                        ("2026-10-19T05:45:00Z", 2, 2, 18126.54, None),
                    ],
                )
            result = build(db)
        finally:
            db.close()
        self.assertEqual(result["episodeCount"], 1)
        episode = result["episodes"][0]
        self.assertEqual(episode["room"], "douwe_slaapkamer")
        self.assertEqual(episode["transition"]["baselineAfter_C"], 20.5)
        cic = episode["evidence"]["quatt"]["cicSupervisoryMode"]
        self.assertEqual(cic["firstBoilerModeAfterStepUpAt"],
                         "2026-10-19T05:35:00Z")
        self.assertIs(cic["boilerModeAlsoObservedBeforeStepUp"], False)
        self.assertEqual([s["mode"] for s in cic["samples"]], [2, 2, 3, 4, 2])
        self.assertEqual(len(episode["evidence"]["grid"]["gasMeterObservations"]), 2)
        self.assertEqual(episode["assessment"]["status"], "UNASSESSED")
        self.assertIs(result["policy"]["physicalWritesAllowed"], False)

    def test_absent_or_invalid_cic_signal_never_implies_no_boiler(self):
        db = database()
        try:
            db.execute(
                """INSERT INTO measurements
                   (ts_utc, device_id, metric_id, value_real, quality,
                    source_resolution_seconds)
                   VALUES ('2026-10-19T05:35:00Z', 1, 1, 3, 'held', 60)"""
            )
            result = build(db)
        finally:
            db.close()
        episode = result["episodes"][0]
        cic = episode["evidence"]["quatt"]["cicSupervisoryMode"]
        self.assertEqual(cic["samples"], [])
        self.assertIsNone(cic["firstBoilerModeAfterStepUpAt"])
        self.assertIsNone(cic["boilerModeAlsoObservedBeforeStepUp"])
        self.assertEqual(episode["quality"]["cicModeObservedSamples"], 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "services/pi/history/archive_planner_snapshot.py"
)

spec = importlib.util.spec_from_file_location("planner_history", MODULE_PATH)
planner_history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner_history)


class PlannerSnapshotArchiveTest(unittest.TestCase):
    def test_archives_hardened_plan_and_context_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            planner_history.DATA = data
            planner_history.PLAN_FILE = data / "dynamic-shadow-plan.json"
            planner_history.STATE_FILE = data / "energy-state-v2.json"
            planner_history.WW_FILE = data / "ww-input.json"
            planner_history.DB_FILE = data / "planner-history.sqlite"
            planner_history.STATUS_FILE = data / "planner-history-status.json"

            planner_history.PLAN_FILE.write_text(json.dumps({
                "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
                "generated_at": "2026-09-14T18:15:00Z",
                "validUntil": "2026-09-14T18:35:00Z",
                "objective": "MAXIMIZE_PV_SELF_CONSUMPTION_SUBJECT_TO_WW_COMFORT",
                "contract": {"mode": "FIXED", "id": "ENGIE_3Y_2026_2029"},
                "slots": [{
                    "slot_start_utc": "2026-09-14T18:15:00Z",
                    "pvForecastW": 1000,
                    "wwPlanW": 0,
                    "evPlanW": 0,
                    "gridExportAfterFlexW": 500,
                }],
            }))
            planner_history.STATE_FILE.write_text(json.dumps({
                "meta": {
                    "state_revision": 42,
                    "source_sample_at": "2026-09-14T18:14:59Z",
                    "heartbeat_at": "2026-09-14T18:14:59Z",
                    "publisher_version": "EM2_CORE_STATE_TEST",
                },
                "grid": {"power_w": -500, "import_w": 0, "export_w": 500},
                "tesla": {
                    "connected": True,
                    "charging": False,
                    "deadline_active": True,
                    "deadline_at": "2026-09-15T05:00:00Z",
                    "remaining_kwh": 10.0,
                    "deadline_max_a": 16,
                },
                "hot_water": {"boiler_power_w": 0},
            }))
            planner_history.WW_FILE.write_text(json.dumps({
                "warmWater": {
                    "goalReachedToday": False,
                    "remainingFallbackMin": 120,
                }
            }))

            first = planner_history.archive()
            second = planner_history.archive()

            self.assertTrue(first["inserted"])
            self.assertFalse(second["inserted"])
            self.assertEqual(second["snapshotCount"], 1)
            self.assertEqual(second["stateRevision"], 42)

            con = sqlite3.connect(planner_history.DB_FILE)
            row = con.execute(
                "SELECT generated_at_utc, state_revision, snapshot_zlib "
                "FROM planner_snapshots"
            ).fetchone()
            con.close()

            self.assertEqual(row[0], "2026-09-14T18:15:00Z")
            self.assertEqual(row[1], 42)
            snapshot = json.loads(zlib.decompress(row[2]).decode("utf-8"))
            self.assertEqual(
                snapshot["plan"]["contract"]["id"],
                "ENGIE_3Y_2026_2029",
            )
            self.assertTrue(snapshot["context"]["state"]["tesla"]["connected"])
            self.assertEqual(
                snapshot["context"]["warmWater"]["remainingFallbackMin"],
                120,
            )


if __name__ == "__main__":
    unittest.main()

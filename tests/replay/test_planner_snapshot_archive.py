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
    def test_archives_plan_embedded_context_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            planner_history.DATA = data
            planner_history.PLAN_FILE = data / "dynamic-shadow-plan.json"
            planner_history.DB_FILE = data / "planner-history.sqlite"
            planner_history.STATUS_FILE = data / "planner-history-status.json"

            planner_history.PLAN_FILE.write_text(json.dumps({
                "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
                "generated_at": "2026-09-14T18:15:00Z",
                "validUntil": "2026-09-14T18:35:00Z",
                "objective": "MAXIMIZE_PV_SELF_CONSUMPTION_SUBJECT_TO_WW_COMFORT",
                "contract": {"mode": "FIXED", "id": "ENGIE_3Y_2026_2029"},
                "realtime": {
                    "actualP1ExportW": 500,
                    "recentLocalAccuracy": 0.91,
                    "recentP1ExportSamples": [500, 450],
                    "p1CorrectionPolicy": "TEST_POLICY",
                },
                "tesla": {
                    "connectedNow": True,
                    "chargingNow": False,
                    "availabilityPolicy": "LIVE_CONNECTED_CURRENT_STATE_ONLY",
                    "deadlinePlan": {
                        "active": True,
                        "deadlineAt": "2026-09-15T05:00:00Z",
                        "remainingKWh": 10.0,
                        "maxA": 16,
                    },
                    "qualifiedWindows": [],
                },
                "dailyPlans": [{
                    "date": "2026-09-14",
                    "goalReached": False,
                    "remainingFallbackMin": 120,
                    "deadlineLocal": "19:00",
                }],
                "slots": [{
                    "slot_start_utc": "2026-09-14T18:15:00Z",
                    "pvForecastW": 1000,
                    "wwPlanW": 0,
                    "evPlanW": 0,
                    "gridExportAfterFlexW": 500,
                }],
            }))

            first = planner_history.archive()
            second = planner_history.archive()

            self.assertTrue(first["inserted"])
            self.assertFalse(second["inserted"])
            self.assertEqual(second["snapshotCount"], 1)
            self.assertEqual(
                second["contextSource"],
                "PLAN_EMBEDDED_DECISION_OUTPUT",
            )
            self.assertIsNone(second["stateRevision"])
            self.assertIsNone(second["sourceSampleAt"])
            self.assertEqual(second["actualP1ExportW"], 500)

            con = sqlite3.connect(planner_history.DB_FILE)
            row = con.execute(
                "SELECT generated_at_utc, state_revision, source_sample_at_utc, "
                "tesla_connected, tesla_deadline_active, snapshot_zlib "
                "FROM planner_snapshots"
            ).fetchone()
            con.close()

            self.assertEqual(row[0], "2026-09-14T18:15:00Z")
            self.assertIsNone(row[1])
            self.assertIsNone(row[2])
            self.assertEqual(row[3], 1)
            self.assertEqual(row[4], 1)

            snapshot = json.loads(zlib.decompress(row[5]).decode("utf-8"))
            self.assertEqual(snapshot["schema"], "EMS_PI_PLANNER_DECISION_SNAPSHOT_V0.2")
            self.assertEqual(
                snapshot["plan"]["contract"]["id"],
                "ENGIE_3Y_2026_2029",
            )
            self.assertTrue(snapshot["context"]["tesla"]["connected"])
            self.assertEqual(snapshot["context"]["realtime"]["actualP1ExportW"], 500)
            self.assertEqual(
                snapshot["context"]["warmWater"]["remainingFallbackMin"],
                120,
            )


if __name__ == "__main__":
    unittest.main()

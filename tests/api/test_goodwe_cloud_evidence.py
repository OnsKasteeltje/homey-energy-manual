#!/usr/bin/env python3
"""Focused contract tests: GoodWe SEMS+ observations stay non-authoritative."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

API = Path(__file__).resolve().parents[2] / "services/pi/api/web-data/server.py"
spec = importlib.util.spec_from_file_location("goodwe_web_api", API)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class GoodweEvidenceTest(unittest.TestCase):
    def observe(self, at, counters):
        return {"generatedAt": at, "goodwe": {
            "fetchedAt": at, "status": "RECEIVED_SOURCE_TIME_UNKNOWN",
            "inverters": [
                {"deviceKey": "a"*16, "serialSuffix": "0071",
                 "powerW": 450, "lifetimeKWh": counters[0]},
                {"deviceKey": "b"*16, "serialSuffix": "0285",
                 "powerW": 200, "lifetimeKWh": counters[1]},
            ]}}

    def resource(self, samples, date="2026-10-24"):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.json"
            history.write_text(json.dumps({
                "schema": "EMS_PV_CLOUD_SHADOW_HISTORY_V0.1", "samples": samples
            }))
            with patch.dict("os.environ", {"EMS_PV_CLOUD_HISTORY_FILE": str(history)}):
                return server.goodwe_cloud_evidence_resource(date)

    def test_positive_counter_window_never_authoritative(self):
        d = self.resource([
            self.observe("2026-10-24T09:15:00Z", (24036.8, 10825.5)),
            self.observe("2026-10-24T09:30:00Z", (24037.1, 10825.6)),
            self.observe("2026-10-24T09:45:00Z", (24037.2, 10825.6)),
        ])
        self.assertEqual(d["schema"], "EMS_WEB_GOODWE_CLOUD_EVIDENCE_V1")
        self.assertFalse(d["eligibleForHouseBalance"])
        self.assertFalse(d["eligibleForControl"])
        self.assertTrue(d["readOnly"])
        self.assertEqual(d["timeBasis"], "PI_FETCH_TIME_SOURCE_TIME_UNKNOWN")
        self.assertEqual([v["lifetimeCounterDeltaKWh"] for v in d["devices"]], [.4, .1])
        self.assertNotIn("pvKWh", d)
        self.assertNotIn("houseKWh", d)

    def test_counter_only_updates_last_fetch_without_inventing_power(self):
        day = self.observe("2026-10-24T17:30:00Z", (24043.0, 10828.1))
        night = self.observe("2026-10-24T18:45:00Z", (24043.0, 10828.1))
        night["goodwe"]["status"] = "COUNTER_ONLY_SOURCE_TIME_UNKNOWN"
        for inverter in night["goodwe"]["inverters"]:
            inverter["powerW"] = None
            inverter["todayKWh"] = 6.8 if inverter["serialSuffix"] == "0071" else 3.0
        d = self.resource([day, night])
        self.assertEqual(d["sampleCount"], 2)
        self.assertEqual(d["status"], "OBSERVED_COUNTER_ONLY_UNVERIFIED_FRESHNESS")
        self.assertEqual(d["lastFetchedAt"], "2026-10-24T18:45:00+00:00")
        self.assertTrue(all(dev["lastPowerW"] is None for dev in d["devices"]))
        self.assertTrue(all(dev["lifetimeCounterDeltaKWh"] == 0 for dev in d["devices"]))
        self.assertFalse(d["eligibleForHouseBalance"])

    def test_counter_decrease_stays_unknown(self):
        d = self.resource([
            self.observe("2026-10-24T09:15:00Z", (24036.8, 10825.5)),
            self.observe("2026-10-24T09:30:00Z", (24036.3, 10825.6)),
        ])
        self.assertIsNone(d["devices"][0]["lifetimeCounterDeltaKWh"])
        self.assertEqual(d["devices"][0]["counterEvidence"], "NON_MONOTONIC")
        self.assertEqual(d["devices"][1]["lifetimeCounterDeltaKWh"], .1)

    def test_missing_day_means_unknown_not_zero(self):
        d = self.resource([self.observe("2026-10-23T09:30:00Z", (24036.8, 10825.5))])
        self.assertEqual(d["status"], "NO_SAMPLES")
        self.assertEqual(d["devices"], [])
        self.assertIsNone(d["lastFetchedAt"])



class GoodweDurableHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        collector_file = (Path(__file__).resolve().parents[2] /
                          "services/pi/integrations/pv_cloud/collect_shadow.py")
        spec = importlib.util.spec_from_file_location("goodwe_collector_archive", collector_file)
        cls.collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.collector)

    def sample(self, when, day_values, life_values, status="RECEIVED_SOURCE_TIME_UNKNOWN"):
        return {"goodwe": {
            "status": status, "fetchedAt": when, "inverters": [
                {"deviceKey": "a"*16, "serialSuffix": "0071",
                 "todayKWh": day_values[0], "lifetimeKWh": life_values[0],
                 "powerW": None if "COUNTER_ONLY" in status else 100.0},
                {"deviceKey": "b"*16, "serialSuffix": "0285",
                 "todayKWh": day_values[1], "lifetimeKWh": life_values[1],
                 "powerW": None if "COUNTER_ONLY" in status else 200.0},
            ]}}

    def archive_and_read(self, samples):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "goodwe.sqlite"
            inserted = self.collector.archive_goodwe_samples(path, samples)
            repeated = self.collector.archive_goodwe_samples(path, samples)
            self.assertEqual(repeated, 0, "Must not duplicate retried samples")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with patch.dict("os.environ", {"EMS_GOODWE_COUNTER_ARCHIVE_DB": str(path)}):
                current = server.goodwe_daily_counter_resource("2026-10-24")
                other = server.goodwe_daily_counter_resource("2026-10-23")
            return inserted, current, other

    def test_reported_day_counters_not_confused_with_window_growth(self):
        rows = [
            self.sample("2026-10-24T09:30:00Z", (0.6, 0.4), (24036.8, 10825.5)),
            self.sample("2026-10-24T18:45:00Z", (6.8, 3.0), (24043.0, 10828.1),
                        "COUNTER_ONLY_SOURCE_TIME_UNKNOWN"),
            self.sample("2026-10-24T21:30:00Z", (6.8, 3.0), (24043.0, 10828.1),
                        "COUNTER_ONLY_SOURCE_TIME_UNKNOWN"),
        ]
        inserted, report, other = self.archive_and_read(rows)
        self.assertEqual(inserted, 6)
        self.assertEqual(report["reportedDayKWh"], 9.8)
        self.assertEqual(report["windowCounterGrowthKWh"], 8.8)
        self.assertEqual(report["status"], "LATE_DAY_COUNTER_OBSERVED")
        self.assertEqual(report["samplePairs"], 3)
        self.assertEqual([r["lastPowerW"] for r in report["devices"]], [None, None])
        self.assertFalse(report["eligibleForHouseBalance"])
        self.assertFalse(report["eligibleForControl"])
        self.assertIsNone(other["reportedDayKWh"])
        self.assertEqual(other["status"], "NO_SAMPLES")

    def test_counter_reset_blocks_day_total_and_duplicate_identity(self):
        samples = [
            self.sample("2026-10-24T08:00:00Z", (1.2, 0.9), (24037.0, 10826.0)),
            self.sample("2026-10-24T18:00:00Z", (0.1, 3.0), (24043.0, 10828.1)),
        ]
        _, report, _ = self.archive_and_read(samples)
        self.assertEqual(report["status"], "COUNTER_DISCONTINUITY")
        self.assertIsNone(report["reportedDayKWh"])

    def test_incomplete_sample_is_not_archived(self):
        s = self.sample("2026-10-24T18:45:00Z", (6.8, 3.0), (24043.0, 10828.1))
        s["goodwe"]["inverters"][1]["lifetimeKWh"] = None
        inserted, report, _ = self.archive_and_read([s])
        self.assertEqual(inserted, 0)
        self.assertEqual(report["status"], "NO_SAMPLES")
        self.assertIsNone(report["reportedDayKWh"])


if __name__ == "__main__":
    unittest.main()

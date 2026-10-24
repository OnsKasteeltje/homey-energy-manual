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


if __name__ == "__main__":
    unittest.main()

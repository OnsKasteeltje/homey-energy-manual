"""Focused offline PV shadow evidence tests, without actual API requests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[3] / "services/pi/integrations/pv_cloud/collect_shadow.py"
spec = importlib.util.spec_from_file_location("pv_cloud_shadow", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PvCloudShadowTest(unittest.TestCase):
    def test_goodwe_two_inverters_and_counter_units(self):
        got = module.goodwe_projection({"inverter": [
            {"sn": "sample-0071", "invert_full": {"pac": 211, "eday": .4, "etotal": 24036.6}},
            {"sn": "sample-0285", "invert_full": {"pac": 124, "eday": .3, "etotal": 10825.4}},
        ], "powerflow": {"pv": "324.0"}}, "2026-10-24T08:00:00Z")
        self.assertEqual(got["status"], "RECEIVED_SOURCE_TIME_UNKNOWN")
        self.assertEqual(got["sumInverterPowerW"], 335)
        self.assertEqual(got["stationPowerW"], 324)
        self.assertEqual(sorted(x["lifetimeKWh"] for x in got["inverters"]), [10825.4, 24036.6])
        self.assertTrue(all(x["sourcePowerMeasuredAt"] is None for x in got["inverters"]))
        self.assertTrue(all(len(x["deviceKey"]) == 16 for x in got["inverters"]))
        self.assertNotIn("sample-0071", json.dumps(got))

    def test_counter_only_evening_is_not_degraded_or_zero_watts(self):
        payload = {"inverter": [
            {"sn": "sample-0071", "invert_full": {"eday": 6.8, "etotal": 24043.0}},
            {"sn": "sample-0285", "invert_full": {"eday": 3.0, "etotal": 10828.1}},
        ], "powerflow": {"pv": 0}}
        sample = module.goodwe_projection(payload, "2026-10-24T18:45:00Z")
        self.assertEqual(sample["status"], "COUNTER_ONLY_SOURCE_TIME_UNKNOWN")
        self.assertEqual(sample["stationPowerW"], 0)
        self.assertIsNone(sample["sumInverterPowerW"])
        self.assertTrue(all(row["powerW"] is None for row in sample["inverters"]))
        self.assertEqual(
            sorted(row["lifetimeKWh"] for row in sample["inverters"]),
            [10828.1, 24043.0],
        )
        result = module.collect({
            "SEMSPLUS_STATION_ID": "station",
            "SEMSPLUS_ACCOUNT": "account",
            "SEMSPLUS_PASSWORD": "password",
        }, goodwe_fetch=lambda _: sample,
           solaredge_fetch=lambda _: self.fail("SolarEdge disabled"))
        self.assertEqual(result["status"], "OBSERVED_COUNTER_ONLY_UNVERIFIED_FRESHNESS")
        self.assertEqual(result["solaredge"]["status"], "UNCONFIGURED")
        self.assertFalse(result["eligibleForControl"])
        self.assertFalse(result["eligibleForHouseBalance"])

    def test_missing_goodwe_reading_remains_null(self):
        got = module.goodwe_projection({"inverter": [
            {"sn": "sample-0071", "invert_full": {"eday": .4}},
            {"sn": "sample-0285", "invert_full": {"pac": 50}},
        ]}, "2026-10-24T08:00:00Z")
        self.assertEqual(got["status"], "INCOMPLETE")
        self.assertIsNone(got["sumInverterPowerW"])
        self.assertIn(None, [x["powerW"] for x in got["inverters"]])

    def test_solaredge_energy_units_and_site_time_not_sample_time(self):
        got = module.solar_edge_projection({
            "currentPower": {"power": 567.6699}, "lastDayData": {"energy": 479},
            "lifeTimeData": {"energy": 17754130}, "lastUpdateTime": "2026-10-24 10:47:39",
        }, "2026-10-24T08:48:00Z")
        self.assertEqual(got["status"], "RECEIVED_SITE_TIME_ONLY")
        self.assertEqual(got["powerW"], 567.6699)
        self.assertEqual(got["todayKWh"], .479)
        self.assertEqual(got["lifetimeKWh"], 17754.13)
        self.assertIsNone(got["sourcePowerMeasuredAt"])

    def test_error_is_sanitized_and_never_promoted(self):
        config = {key: "secret" for key in (
            "SEMSPLUS_STATION_ID", "SEMSPLUS_ACCOUNT", "SEMSPLUS_PASSWORD",
            "SOLAREDGE_SITE_ID", "SOLAREDGE_API_KEY",
        )}
        def fails(_):
            raise RuntimeError("sensitive secret may appear in errors")
        def succeeds(_):
            return {"status": "RECEIVED_SITE_TIME_ONLY", "powerW": 400}
        got = module.collect(config, goodwe_fetch=fails, solaredge_fetch=succeeds)
        self.assertEqual(got["status"], "DEGRADED")
        self.assertEqual(got["goodwe"], {"status": "FETCH_FAILED", "errorCode": "UPSTREAM_ERROR"})
        self.assertNotIn("secret", json.dumps(got))
        self.assertFalse(got["eligibleForControl"])
        self.assertFalse(got["eligibleForHouseBalance"])

    def test_only_goodwe_configured_is_healthy_and_never_calls_solaredge(self):
        config = {
            "SEMSPLUS_STATION_ID": "station",
            "SEMSPLUS_ACCOUNT": "account",
            "SEMSPLUS_PASSWORD": "password",
        }
        def must_not_call(_):
            raise AssertionError("Disabled SolarEdge was invoked")
        def goodwe(_):
            return {"status": "RECEIVED_SOURCE_TIME_UNKNOWN", "inverters": []}
        got = module.collect(config, goodwe_fetch=goodwe, solaredge_fetch=must_not_call)
        self.assertEqual(got["activeSources"], ["goodwe"])
        self.assertEqual(got["status"], "OBSERVED_UNVERIFIED_FRESHNESS")
        self.assertEqual(got["solaredge"], {"status": "UNCONFIGURED"})
        self.assertFalse(got["eligibleForControl"])
        self.assertFalse(got["eligibleForHouseBalance"])

    def test_only_solaredge_configured_is_healthy(self):
        config = {"SOLAREDGE_SITE_ID": "site", "SOLAREDGE_API_KEY": "secret"}
        def must_not_call(_):
            raise AssertionError("Disabled GoodWe was invoked")
        def solaredge(_):
            return {"status": "RECEIVED_SITE_TIME_ONLY", "powerW": 50}
        got = module.collect(config, goodwe_fetch=must_not_call, solaredge_fetch=solaredge)
        self.assertEqual(got["activeSources"], ["solaredge"])
        self.assertEqual(got["status"], "OBSERVED_UNVERIFIED_FRESHNESS")
        self.assertEqual(got["goodwe"], {"status": "UNCONFIGURED"})

    def test_no_configured_sources_is_not_healthy(self):
        def must_not_call(_):
            raise AssertionError("No source should be invoked")
        got = module.collect({}, goodwe_fetch=must_not_call, solaredge_fetch=must_not_call)
        self.assertEqual(got["activeSources"], [])
        self.assertEqual(got["status"], "NO_ACTIVE_SOURCES")
        self.assertEqual(got["goodwe"]["status"], "UNCONFIGURED")
        self.assertEqual(got["solaredge"]["status"], "UNCONFIGURED")
        self.assertFalse(got["eligibleForControl"])

    def test_rolling_history_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "history.json"
            for n in range(194):
                module.update_history(target, {"seq": n})
            value = json.loads(target.read_text())
            self.assertEqual(len(value["samples"]), 192)
            self.assertEqual(value["samples"][0]["seq"], 2)
            self.assertEqual(value["samples"][-1]["seq"], 193)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_atomic_output_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            module.atomic_write(target, {"schema": module.SCHEMA, "readOnly": True})
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertTrue(json.loads(target.read_text())["readOnly"])
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

if __name__ == "__main__":
    unittest.main()

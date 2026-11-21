"""Standalone tests: no Homey, network, systemd or device access."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/pi/health"))
import push_kuma_forecast as subject

GOOD = {
    "schema": "EMS_PI_HEALTH_V0.1",
    "status": "HEALTHY_WITH_RECENT_INCIDENTS",
    "emsFunctions": {"forecastChain": {"status": "OK"}},
    "emsData": {"dynamicPlan": {"status": "OK"}, "wwPlan": {"status": "OK"}},
}


class Tests(unittest.TestCase):
    def test_success_independent_of_unrelated_global_incident(self):
        self.assertEqual(subject.decide(GOOD), ("up", "FORECAST_CHAIN_OK"))

    def test_forecast_failure(self):
        data = json.loads(json.dumps(GOOD))
        data["emsFunctions"]["forecastChain"]["status"] = "DEGRADED"
        self.assertEqual(subject.decide(data), ("down", "FORECAST_CHAIN_NOT_OK"))

    def test_stale_plan(self):
        data = json.loads(json.dumps(GOOD))
        data["emsData"]["wwPlan"]["status"] = "STALE"
        self.assertEqual(subject.decide(data), ("down", "WW_PLAN_NOT_OK"))

    def test_missing_evidence_and_unknown_schema_fail_closed(self):
        self.assertEqual(subject.decide({}), ("down", "HEALTH_SCHEMA_INVALID"))
        data = json.loads(json.dumps(GOOD))
        del data["emsData"]["dynamicPlan"]
        self.assertEqual(subject.decide(data), ("down", "DYNAMIC_PLAN_NOT_OK"))

    def test_local_endpoint_enforced(self):
        token_url = "http://127.0.0.1:3001/api/push/testtoken"
        actual = subject.build_url(token_url, "down", "WW_PLAN_NOT_OK")
        self.assertEqual(parse_qs(urlsplit(actual).query), {
            "status": ["down"], "msg": ["WW_PLAN_NOT_OK"]
        })
        for url in (
            "https://evil.example/api/push/token",
            "http://127.0.0.1:3001/",
            "http://127.0.0.1:3001/api/push/token?status=up",
            "http://192.168.1.42:3001/api/push/token",
        ):
            with self.assertRaises(ValueError):
                subject.build_url(url, "up", "ok")

    def test_health_command_failed_is_down(self):
        with patch.object(subject.subprocess, "run") as mock:
            mock.return_value.returncode = 1
            self.assertEqual(subject.current_health(), ("down", "HEALTH_COMMAND_FAILED"))


if __name__ == "__main__":
    unittest.main()

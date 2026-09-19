import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "services/pi/api/web-data/server.py"
SPEC = importlib.util.spec_from_file_location("ems_web_data_server", SOURCE)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class SeasonalAdviceResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_allowlisted_projection(self):
        server.WW_SEASONAL_FILE = self.write_source({
            "schema": "INTERNAL_SCHEMA",
            "generatedAt": "2026-09-19T07:30:00Z",
            "status": "OK",
            "advice": "KEEP_CURRENT",
            "currentMode": "CV",
            "confirmation": {"confirmed": True, "streak": 5},
            "internalSecretLikeField": "must-not-leak",
        })
        result = server.seasonal_advice_resource()
        self.assertEqual(set(result), {
            "schema", "generatedAt", "status", "advice", "currentMode", "confirmation"
        })
        self.assertEqual(result["schema"], "EMS_WEB_WW_SEASONAL_ADVICE_V1")
        self.assertEqual(result["confirmation"], {"confirmed": True})
        self.assertNotIn("internalSecretLikeField", result)

    def test_invalid_mode_fails_closed(self):
        server.WW_SEASONAL_FILE = self.write_source({
            "generatedAt": "2026-09-19T07:30:00Z",
            "status": "OK",
            "advice": "KEEP_CURRENT",
            "currentMode": "UNKNOWN",
        })
        with self.assertRaises(ValueError):
            server.seasonal_advice_resource()


class StateCurrentResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_live_projection_is_allowlisted(self):
        server.ENERGY_STATE_FILE = self.write_source({
            "meta": {"generated_at": "2026-09-19T08:30:03Z", "state_age_sec": 1, "secret": "no"},
            "balance": {"control_gate": {"grid_measurement_valid": True}, "internal": "no"},
            "grid": {"power_w": -694, "l1_w": 57},
            "pv": {"total_w": 890, "solaredge_w": 432},
            "quatt": {"power_w": 10, "thermostat_heating_on": False, "cop_1": 0},
            "energy_budget": {"other_house_load_w": None, "discretionary_import_budget_w": 4000},
            "tesla": {"connected": False, "charging": False, "power_w": 0, "requested_a": 0,
                      "deadline_at": "2026-09-19T08:00:00Z", "deadline_active": False,
                      "need": "HOLD", "remaining_kwh": 7.15, "offered_a": 0},
            "hot_water": {"boiler_on": False, "boiler_power_w": 0, "mode": False,
                          "control": {"action": "HOLD", "reason": "internal"}},
            "manager": {"decision": "HOLD", "reason": "reason", "priority": "MAY", "constraints": ["internal"]},
            "internalSecretLikeField": "must-not-leak",
        })
        result = server.state_current_resource()
        self.assertEqual(result["schema"], "EMS_WEB_STATE_CURRENT_V1")
        self.assertEqual(result["grid"], {"power_w": -694})
        self.assertEqual(result["balance"]["control_gate"]["grid_measurement_valid"], True)
        self.assertEqual(result["hot_water"]["control"], {"action": "HOLD"})
        self.assertNotIn("internalSecretLikeField", result)
        self.assertNotIn("l1_w", result["grid"])
        self.assertNotIn("reason", result["hot_water"]["control"])

    def test_invalid_state_timestamp_fails_closed(self):
        server.ENERGY_STATE_FILE = self.write_source({"meta": {"generated_at": "bad"}})
        with self.assertRaises(ValueError):
            server.state_current_resource()


if __name__ == "__main__":
    unittest.main()

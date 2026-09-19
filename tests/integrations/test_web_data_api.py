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


if __name__ == "__main__":
    unittest.main()

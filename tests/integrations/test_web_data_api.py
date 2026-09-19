import importlib.util
import json
import sqlite3
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


class CommandsCurrentResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_command_projection_is_allowlisted(self):
        server.TESLA_COMMAND_FILE = self.write_source({
            "requestId": "tesla-1", "active": True, "currentSoc": 38, "targetSoc": 51,
            "deadline": "2026-09-19T10:00", "maxA": 7, "goalKWh": 7.15, "secret": "no",
        })
        server.EMS_SETTINGS_COMMAND_FILE = self.write_source({
            "requestId": "settings-1", "contractType": "FIXED", "hotWaterSource": "CV",
            "secret": "no",
        })
        result = server.commands_current_resource()
        self.assertEqual(result["schema"], "EMS_WEB_COMMANDS_CURRENT_V1")
        self.assertEqual(result["tesla"], {
            "active": True, "currentSoc": 38, "targetSoc": 51,
            "deadline": "2026-09-19T10:00", "maxA": 7, "requestId": "tesla-1",
        })
        self.assertEqual(result["settings"], {
            "contractType": "FIXED", "hotWaterSource": "CV", "requestId": "settings-1",
        })
        self.assertNotIn("goalKWh", result["tesla"])
        self.assertNotIn("secret", result["settings"])

    def test_invalid_command_state_fails_closed(self):
        server.TESLA_COMMAND_FILE = self.write_source({
            "requestId": "tesla-1", "active": True, "currentSoc": 51, "targetSoc": 38,
            "deadline": "2026-09-19T10:00", "maxA": 7,
        })
        server.EMS_SETTINGS_COMMAND_FILE = self.write_source({
            "requestId": "settings-1", "contractType": "FIXED", "hotWaterSource": "CV",
        })
        with self.assertRaises(ValueError):
            server.commands_current_resource()


class HistoryResourceTest(unittest.TestCase):
    def make_db(self, rows):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        path = handle.name
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        with sqlite3.connect(path) as db:
            db.execute("""
                CREATE TABLE house_energy_intervals (
                    start_ts_utc TEXT NOT NULL,
                    end_ts_utc TEXT NOT NULL PRIMARY KEY,
                    duration_seconds INTEGER NOT NULL,
                    import_kwh REAL, export_kwh REAL,
                    pv_solaredge_kwh REAL, pv_goodwe4200_kwh REAL, pv_goodwe2000_kwh REAL,
                    pv_total_kwh REAL, house_kwh REAL,
                    quality TEXT NOT NULL, discontinuity_reason TEXT,
                    updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.executemany("""
                INSERT INTO house_energy_intervals
                (start_ts_utc,end_ts_utc,duration_seconds,import_kwh,export_kwh,
                 pv_solaredge_kwh,pv_goodwe4200_kwh,pv_goodwe2000_kwh,
                 pv_total_kwh,house_kwh,quality,discontinuity_reason)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, rows)
        return path

    def test_day_splits_coarse_interval_and_preserves_formula_components(self):
        server.HISTORY_DB = self.make_db([
            ("2026-01-01T00:00:00.000Z", "2026-01-01T06:00:00.000Z", 21600,
             6.0, 1.0, 3.0, 1.2, 1.8, 6.0, 11.0, "observed", None),
        ])
        result = server.history_resource("day", "2026-01-01")
        self.assertEqual(result["schema"], "EMS_WEB_HISTORY_V1")
        self.assertEqual(result["period"]["timezone"], "Europe/Amsterdam")
        self.assertEqual(result["period"]["bucket"], "hour")
        self.assertEqual(len(result["series"]), 24)
        self.assertAlmostEqual(result["summary"]["houseKWh"], 11.0)
        self.assertAlmostEqual(result["summary"]["pvKWh"], 6.0)
        self.assertAlmostEqual(result["summary"]["pvSolarEdgeKWh"], 3.0)
        self.assertAlmostEqual(result["summary"]["pvGoodWe4200KWh"], 1.2)
        self.assertAlmostEqual(result["summary"]["pvGoodWe2000KWh"], 1.8)
        populated = [x for x in result["series"] if x["houseKWh"] > 0]
        self.assertEqual(len(populated), 6)

    def test_discontinuity_is_not_counted_as_energy(self):
        server.HISTORY_DB = self.make_db([
            ("2026-01-01T10:00:00.000Z", "2026-01-01T11:00:00.000Z", 3600,
             None, None, None, None, None, None, None, "discontinuity", "counter_decrease"),
        ])
        result = server.history_resource("day", "2026-01-01")
        self.assertEqual(result["summary"]["houseKWh"], 0.0)
        self.assertEqual(result["quality"]["discontinuityCount"], 1)
        self.assertLess(result["quality"]["coverage"], 1.0)

    def test_week_uses_monday_as_local_calendar_start(self):
        server.HISTORY_DB = self.make_db([])
        result = server.history_resource("week", "2026-09-19")
        self.assertTrue(result["period"]["start"].startswith("2026-09-14T00:00:00"))
        self.assertEqual(len(result["series"]), 7)

    def test_day_bucket_count_follows_amsterdam_dst(self):
        server.HISTORY_DB = self.make_db([])
        self.assertEqual(len(server.history_resource("day", "2026-03-29")["series"]), 23)
        self.assertEqual(len(server.history_resource("day", "2026-10-25")["series"]), 25)

    def test_invalid_period_fails_closed(self):
        server.HISTORY_DB = self.make_db([])
        with self.assertRaises(ValueError):
            server.history_resource("day", "2026-02-30")
        with self.assertRaises(ValueError):
            server.history_resource("month", "2026-13")


if __name__ == "__main__":
    unittest.main()

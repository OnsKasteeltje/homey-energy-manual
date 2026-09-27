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


class PvFlexDeviceActualsTest(unittest.TestCase):
    def make_db(self):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        path = handle.name
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE house_energy_intervals (
                    start_ts_utc TEXT NOT NULL,
                    end_ts_utc TEXT NOT NULL PRIMARY KEY,
                    duration_seconds INTEGER NOT NULL,
                    import_kwh REAL, export_kwh REAL,
                    pv_total_kwh REAL, house_kwh REAL,
                    quality TEXT NOT NULL, discontinuity_reason TEXT
                );
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_key TEXT NOT NULL
                );
                CREATE TABLE metrics (
                    id INTEGER PRIMARY KEY,
                    metric_key TEXT NOT NULL
                );
                CREATE TABLE measurements_15m (
                    slot_start_utc TEXT NOT NULL,
                    device_id INTEGER NOT NULL,
                    metric_id INTEGER NOT NULL,
                    value_avg REAL,
                    energy_wh REAL,
                    quality TEXT NOT NULL
                );
                CREATE TABLE pv_forecast_v2_archive (
                    slot_start_utc TEXT NOT NULL,
                    forecast_w REAL NOT NULL,
                    confidence REAL,
                    model_basis TEXT,
                    generated_at TEXT NOT NULL
                );
            """)
            db.execute("INSERT INTO devices(id,device_key) VALUES (1,'tesla')")
            db.execute("INSERT INTO metrics(id,metric_key) VALUES (1,'electrical_power_w')")
            db.executemany(
                """
                INSERT INTO measurements_15m
                (slot_start_utc,device_id,metric_id,value_avg,energy_wh,quality)
                VALUES (?,?,?,?,?,?)
                """,
                [
                    ("2026-09-26T08:00:00Z", 1, 1, 3450.0, 862.5, "complete"),
                    ("2026-09-26T08:15:00Z", 1, 1, 1380.0, 345.0, "partial"),
                    ("2026-09-26T08:30:00Z", 1, 1, 9999.0, 2499.75, "held"),
                ],
            )
        return path

    def test_pv_flex_accepts_canonical_15m_device_quality(self):
        server.HISTORY_DB = self.make_db()
        result = server.pv_flex_analysis_resource("2026-09-26")
        by_start = {item["start"]: item for item in result["series"]}
        self.assertEqual(
            by_start["2026-09-26T10:00:00+02:00"]["devices"]["evPowerW"],
            3450.0,
        )
        self.assertEqual(
            by_start["2026-09-26T10:15:00+02:00"]["devices"]["evPowerW"],
            1380.0,
        )
        self.assertIsNone(
            by_start["2026-09-26T10:30:00+02:00"]["devices"]["evPowerW"]
        )



class HeatingTemperatureHistoryResourceTest(unittest.TestCase):
    def make_db(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        path = handle.name
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_key TEXT NOT NULL
                );
                CREATE TABLE metrics (
                    id INTEGER PRIMARY KEY,
                    metric_key TEXT NOT NULL
                );
                CREATE TABLE measurements_15m (
                    slot_start_utc TEXT NOT NULL,
                    device_id INTEGER NOT NULL,
                    metric_id INTEGER NOT NULL,
                    value_avg REAL,
                    value_min REAL,
                    value_max REAL,
                    sample_count INTEGER,
                    energy_wh REAL,
                    quality TEXT
                );
            """)
            db.executemany(
                "INSERT INTO devices(id,device_key) VALUES (?,?)",
                [
                    (1, "honeywell_woonkamer"),
                    (2, "honeywell_eetkamer"),
                    (3, "honeywell_keuken"),
                    (4, "honeywell_serre"),
                ],
            )
            db.execute(
                "INSERT INTO metrics(id,metric_key) VALUES (1,'room_temperature_c')"
            )
            db.executemany(
                """
                INSERT INTO measurements_15m
                (slot_start_utc,device_id,metric_id,value_avg,value_min,value_max,
                 sample_count,energy_wh,quality)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                [
                    ("2026-09-27T06:00:00Z", 2, 1, 17.8, 17.7, 17.9, 12, None, "complete"),
                    ("2026-09-27T06:15:00Z", 2, 1, 18.0, 17.9, 18.0, 8, None, "partial"),
                    ("2026-09-27T06:30:00Z", 2, 1, 99.0, 99.0, 99.0, 1, None, "held"),
                    ("2026-09-27T00:00:00Z", 1, 1, 16.0, 16.0, 16.0, 4, None, "complete"),
                ],
            )
        return path

    def test_temperature_history_projects_only_recent_measured_slots(self):
        server.HISTORY_DB = self.make_db()
        now = server.datetime.fromisoformat("2026-09-27T07:00:00+00:00")
        result = server.heating_temperature_history_resource(generated_at=now)

        self.assertEqual(result["schema"], "EMS_WEB_HEATING_TEMPERATURE_HISTORY_V1")
        self.assertTrue(result["presentationOnly"])
        self.assertEqual(result["period"]["historyMinutes"], 360)
        self.assertEqual(
            [room["key"] for room in result["rooms"]],
            ["woonkamer", "eetkamer", "keuken", "serre"],
        )

        eetkamer = next(room for room in result["rooms"] if room["key"] == "eetkamer")
        self.assertEqual([item["avg_C"] for item in eetkamer["series"]], [17.8, 18.0])
        self.assertEqual([item["quality"] for item in eetkamer["series"]], ["complete", "partial"])
        self.assertNotIn(99.0, [item["avg_C"] for item in eetkamer["series"]])

        woonkamer = next(room for room in result["rooms"] if room["key"] == "woonkamer")
        self.assertEqual(woonkamer["series"], [])



class HeatingPreheatShadowResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def source(self):
        rooms = []
        for key in ("woonkamer", "eetkamer", "keuken", "serre"):
            rooms.append({
                "key": key,
                "displayName": key.title(),
                "preheatScope": True,
                "group": "living_area" if key in {"woonkamer", "eetkamer"} else None,
                "current": {"temperature_C": 18.0, "baselineDemand": False},
                "baseline": {
                    "currentTargetTemperature_C": 15.5,
                    "changeAt": "2026-09-26T16:00:00+02:00",
                    "targetTemperature_C": 19.0,
                    "direction": "UP",
                },
                "candidate": {
                    "status": "ELIGIBLE_UP_TRANSITION",
                    "reason": "AWAITING_PV_OPPORTUNITY_EVALUATION",
                    "opportunityOpensAt": "2026-09-26T13:00:00+02:00",
                    "opportunityClosesAt": "2026-09-26T16:00:00+02:00",
                    "steps_C": [18.5, 19.0],
                },
                "shadow": {
                    "state": "PREHEAT_READY_FOR_GRANT",
                    "reason": "AWAITING_CENTRAL_PV_PRIORITY",
                    "plannerGrant": "NOT_EVALUATED",
                    "activeStepTarget_C": None,
                    "activeStepReached": None,
                    "nextStepTarget_C": 18.5,
                },
                "secret": "must-not-leak",
            })
        return {
            "schema": "EMS_HEATING_PREHEAT_SHADOW_V0.3",
            "mode": "READ_ONLY",
            "controlMode": "SHADOW",
            "controlWrites": False,
            "generatedAt": "2026-09-26T12:00:00Z",
            "baselineAuthority": "HONEYWELL",
            "allocationAuthority": "DYNAMIC_PI_PLANNER",
            "house": {
                "baselineHeatingDemandPresent": False,
                "baselineDemandRooms": [],
            },
            "cvGuard": {
                "status": "OK",
                "reason": "CURRENT_QUATT_OBSERVER",
                "cvActive": False,
                "ageSeconds": 30,
                "observedAt": "2026-09-26T11:59:30Z",
                "sourceLastUpdated": "2026-09-24T07:15:32Z",
            },
            "policy": {
                "maxStep_C": 0.5,
                "cvCheckedEveryIteration": True,
                "advanceOnlyAfterCurrentStepReached": True,
                "normalBaselineCvIsNotPreheatFault": True,
                "purePreheatCvAssistBlocksFurtherSteps": True,
            },
            "rooms": rooms,
            "internalSecretLikeField": "no",
        }

    def test_allowlisted_preheat_projection(self):
        server.HEATING_PREHEAT_SHADOW_FILE = self.write_source(self.source())
        result = server.heating_preheat_shadow_resource()
        self.assertEqual(result["schema"], "EMS_WEB_HEATING_PREHEAT_SHADOW_V1")
        self.assertIn("cvActive", result["cvGuard"])
        self.assertNotIn("boilerAssistOn", result["cvGuard"])
        self.assertEqual(result["cvGuard"]["observedAt"], "2026-09-26T11:59:30Z")
        self.assertEqual(result["cvGuard"]["sourceLastUpdated"], "2026-09-24T07:15:32Z")
        self.assertEqual(len(result["rooms"]), 4)
        self.assertFalse(result["controlWrites"])
        self.assertEqual(result["baselineAuthority"], "HONEYWELL")
        self.assertEqual(result["rooms"][0]["shadow"]["state"], "PREHEAT_READY_FOR_GRANT")
        self.assertNotIn("secret", result["rooms"][0])
        self.assertNotIn("internalSecretLikeField", result)

    def test_write_capable_source_fails_closed(self):
        payload = self.source()
        payload["controlWrites"] = True
        server.HEATING_PREHEAT_SHADOW_FILE = self.write_source(payload)
        with self.assertRaises(ValueError):
            server.heating_preheat_shadow_resource()


class HeatingPreheatProgressionResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def source(self):
        rooms = []
        for key in ("woonkamer", "eetkamer", "keuken", "serre"):
            rooms.append({
                "key": key,
                "displayName": key.title(),
                "preheatScope": True,
                "group": "living_area" if key in {"woonkamer", "eetkamer"} else None,
                "opportunityId": f"{key}|2026-09-26T16:00:00+02:00|19.000",
                "currentTemperature_C": 18.0,
                "futureHoneywellTarget_C": 19.0,
                "opportunityClosesAt": "2026-09-26T16:00:00+02:00",
                "heatingEligibility": {
                    "state": "PREHEAT_READY_FOR_GRANT",
                    "reason": "AWAITING_CENTRAL_PV_PRIORITY",
                },
                "planner": {
                    "domainGrant": "SHADOW_GRANT",
                    "priorityReason": "HEATING_WINDOW_CLOSES_FIRST",
                },
                "stepHistory": [{
                    "opportunityId": f"{key}|2026-09-26T16:00:00+02:00|19.000",
                    "target_C": 18.0,
                    "startedAt": "2026-09-26T11:00:00Z",
                    "endedAt": "2026-09-26T11:30:00Z",
                    "outcome": "ADVANCED_STEP",
                    "reason": "ADVANCED_AFTER_MEASURED_STEP_COMPLETION",
                }],
                "progression": {
                    "state": "STEP_WAIT",
                    "reason": "WAITING_FOR_MEASURED_TEMPERATURE",
                    "activeStepTarget_C": 18.5,
                    "activeStepReached": False,
                    "activeStepStartedAt": "2026-09-26T12:00:00Z",
                    "nextStepTarget_C": 19.0,
                    "completedSteps_C": [],
                    "lastTransition": "STARTED_STEP",
                    "lastTransitionAt": "2026-09-26T12:00:00Z",
                    "physicalWritePerformed": False,
                },
                "secret": "must-not-leak",
            })
        return {
            "schema": "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4",
            "mode": "READ_ONLY",
            "controlMode": "SHADOW",
            "controlWrites": False,
            "physicalWriteAllowed": False,
            "generatedAt": "2026-09-26T12:00:30Z",
            "baselineAuthority": "HONEYWELL",
            "eligibilityAuthority": "EMS_HEATING_PREHEAT_SHADOW_V0.3",
            "allocationAuthority": "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1",
            "sourceFreshness": {
                "heating": {"status": "OK", "reason": "HEATING_SHADOW_CURRENT", "ageSeconds": 30},
                "priority": {"status": "OK", "reason": "FLEX_PRIORITY_CURRENT", "ageSeconds": 29},
                "priorityConsistentWithHeating": True,
            },
            "policy": {
                "maxStep_C": 0.5,
                "stepReachedTolerance_C": 0.0,
                "advanceOnlyAfterMeasuredStepReached": True,
                "groupAdvanceRequiresAllSelectedRoomsReached": True,
                "plannerGrantRequiredForStartAndAdvance": True,
                "cvGuardInheritedEveryIterationFromV03": True,
                "baselineDemandGuardInheritedFromV03": True,
                "intentionalGridImportAllowed": False,
                "rollbackBehavior": "NOT_DEFINED_SHADOW_ONLY",
                "statePersistence": "LOCAL_SHADOW_ARTIFACT",
                "stepHistoryRetentionHours": 48,
            },
            "rooms": rooms,
            "internalSecretLikeField": "no",
        }

    def test_allowlisted_progression_projection(self):
        server.HEATING_PREHEAT_PROGRESSION_FILE = self.write_source(self.source())
        result = server.heating_preheat_progression_resource()
        self.assertEqual(result["schema"], "EMS_WEB_HEATING_PREHEAT_PROGRESSION_V1")
        self.assertFalse(result["controlWrites"])
        self.assertFalse(result["physicalWriteAllowed"])
        self.assertEqual(result["policy"]["maxStep_C"], 0.5)
        self.assertEqual(result["rooms"][0]["progression"]["state"], "STEP_WAIT")
        self.assertEqual(result["rooms"][0]["progression"]["activeStepTarget_C"], 18.5)
        self.assertEqual(result["policy"]["stepHistoryRetentionHours"], 48)
        self.assertEqual(result["rooms"][0]["stepHistory"][0]["target_C"], 18.0)
        self.assertEqual(result["rooms"][0]["stepHistory"][0]["outcome"], "ADVANCED_STEP")
        self.assertNotIn("secret", result["rooms"][0])
        self.assertNotIn("internalSecretLikeField", result)

    def test_invalid_step_history_fails_closed(self):
        payload = self.source()
        payload["rooms"][0]["stepHistory"][0]["endedAt"] = "not-a-time"
        server.HEATING_PREHEAT_PROGRESSION_FILE = self.write_source(payload)
        with self.assertRaises(ValueError):
            server.heating_preheat_progression_resource()

    def test_write_capable_progression_fails_closed(self):
        payload = self.source()
        payload["rooms"][0]["progression"]["physicalWritePerformed"] = True
        server.HEATING_PREHEAT_PROGRESSION_FILE = self.write_source(payload)
        with self.assertRaises(ValueError):
            server.heating_preheat_progression_resource()

    def test_step_bound_change_fails_closed(self):
        payload = self.source()
        payload["policy"]["maxStep_C"] = 1.0
        server.HEATING_PREHEAT_PROGRESSION_FILE = self.write_source(payload)
        with self.assertRaises(ValueError):
            server.heating_preheat_progression_resource()


class FlexPriorityShadowResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def source(self):
        return {
            "schema": "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1",
            "mode": "READ_ONLY",
            "controlMode": "SHADOW",
            "controlWrites": False,
            "generatedAt": "2026-09-26T12:00:00Z",
            "policy": {
                "strategy": "CONSTRAINT_FIRST_THEN_EARLIEST_CLOSING_FLEX",
                "powerReservationW": 0,
                "realtimeOpportunityAuthority": "P1",
                "evMayUseResidualWhenHeatingFirst": True,
            },
            "heating": {
                "readyRooms": ["woonkamer"],
                "earliestOpportunityClosesAt": "2026-09-26T15:00:00Z",
            },
            "ev": {
                "deadlineActive": True,
                "remainingKWh": 4.0,
                "urgency": "AVAILABLE_LATER",
                "latestSafeStartAt": "2026-09-26T16:00:00Z",
            },
            "decision": {
                "priorityOwner": "HEATING",
                "heatingShadowGrant": "SHADOW_GRANT",
                "evRole": "RESIDUAL_OPPORTUNITY",
                "reason": "HEATING_WINDOW_CLOSES_FIRST",
                "appliesOnlyWhenPvOpportunityExists": True,
                "physicalWriteAllowed": False,
            },
            "internalSecretLikeField": "no",
        }

    def test_allowlisted_priority_projection(self):
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(self.source())
        result = server.flex_priority_shadow_resource()
        self.assertEqual(result["schema"], "EMS_WEB_FLEX_PRIORITY_SHADOW_V1")
        self.assertFalse(result["controlWrites"])
        self.assertEqual(result["policy"]["powerReservationW"], 0)
        self.assertEqual(result["policy"]["realtimeOpportunityAuthority"], "P1")
        self.assertEqual(result["decision"]["priorityOwner"], "HEATING")
        self.assertEqual(result["decision"]["evRole"], "RESIDUAL_OPPORTUNITY")
        self.assertNotIn("internalSecretLikeField", result)

    def test_nonzero_power_reservation_fails_closed(self):
        payload = self.source()
        payload["policy"]["powerReservationW"] = 3000
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(payload)
        with self.assertRaises(ValueError):
            server.flex_priority_shadow_resource()

    def test_physical_write_capability_fails_closed(self):
        payload = self.source()
        payload["decision"]["physicalWriteAllowed"] = True
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(payload)
        with self.assertRaises(ValueError):
            server.flex_priority_shadow_resource()


if __name__ == "__main__":
    unittest.main()

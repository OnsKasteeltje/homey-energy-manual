import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "services/pi/api/web-data/server.py"
SPEC = importlib.util.spec_from_file_location("ems_web_data_server_mobile", SOURCE)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class MobileOverviewResourceTest(unittest.TestCase):
    def write_source(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def live_state(self):
        return {
            "meta": {"generated_at": "2026-10-07T17:55:00Z", "state_age_sec": 2},
            "balance": {
                "control_gate": {"grid_measurement_valid": True},
                "source_timing": {"freshness": {}},
            },
            "grid": {"power_w": -640, "secret": "no"},
            "pv": {"total_w": 4200},
            "quatt": {"power_w": 500, "thermostat_heating_on": False},
            "energy_budget": {"other_house_load_w": 1250},
            "tesla": {
                "connected": True,
                "charging": True,
                "power_w": 3450,
                "requested_a": 15,
                "deadline_at": "2026-10-07T20:00:00Z",
                "deadline_active": True,
                "need": "MAY",
                "remaining_kwh": 4.2,
                "internal": "no",
            },
            "hot_water": {
                "boiler_on": False,
                "boiler_power_w": 0,
                "mode": "CV",
                "control": {"action": "HOLD", "reason": "internal"},
            },
            "manager": {"decision": "HOLD", "reason": "TEST", "priority": "MAY"},
        }

    def seasonal(self):
        return {
            "generatedAt": "2026-10-07T17:50:00Z",
            "status": "OK",
            "advice": "KEEP_CURRENT",
            "currentMode": "CV",
            "confirmation": {"confirmed": True},
        }

    def flex(self):
        return {
            "schema": "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1",
            "mode": "READ_ONLY",
            "controlMode": "SHADOW",
            "controlWrites": False,
            "generatedAt": "2026-10-07T17:50:00Z",
            "policy": {
                "strategy": "CONSTRAINT_FIRST_THEN_EARLIEST_CLOSING_FLEX",
                "powerReservationW": 0,
                "realtimeOpportunityAuthority": "P1",
                "evMayUseResidualWhenHeatingFirst": True,
            },
            "heating": {
                "readyRooms": ["serre"],
                "earliestOpportunityClosesAt": "2026-10-07T19:00:00Z",
            },
            "ev": {
                "deadlineActive": True,
                "remainingKWh": 4.2,
                "urgency": "AVAILABLE_LATER",
                "latestSafeStartAt": "2026-10-07T18:30:00Z",
            },
            "decision": {
                "priorityOwner": "HEATING",
                "heatingShadowGrant": "SHADOW_GRANT",
                "evRole": "RESIDUAL_OPPORTUNITY",
                "reason": "HEATING_WINDOW_CLOSES_FIRST",
                "appliesOnlyWhenPvOpportunityExists": True,
                "physicalWriteAllowed": False,
            },
        }

    def test_mobile_overview_is_read_only_allowlisted_aggregation(self):
        server.ENERGY_STATE_FILE = self.write_source(self.live_state())
        server.WW_SEASONAL_FILE = self.write_source(self.seasonal())
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(self.flex())

        result = server.mobile_overview_resource()

        self.assertEqual(result["schema"], "EMS_MOBILE_OVERVIEW_V1")
        self.assertTrue(result["readOnly"])
        self.assertTrue(result["presentationOnly"])
        self.assertFalse(result["capabilities"]["controlWrites"])
        self.assertFalse(result["capabilities"]["physicalWrites"])

        self.assertEqual(result["energy"]["gridPowerW"], -640)
        self.assertEqual(result["energy"]["gridImportW"], 0)
        self.assertEqual(result["energy"]["gridExportW"], 640)
        self.assertEqual(result["energy"]["pvPowerW"], 4200)

        self.assertTrue(result["ev"]["connected"])
        self.assertTrue(result["ev"]["charging"])
        self.assertEqual(result["ev"]["powerW"], 3450)
        self.assertEqual(result["hotWater"]["seasonalAdvice"]["status"], "OK")
        self.assertEqual(result["heating"]["readyRooms"], ["serre"])
        self.assertEqual(result["heating"]["shadowGrant"], "SHADOW_GRANT")
        self.assertEqual(result["flex"]["status"], "OK")
        self.assertEqual(result["flex"]["priorityOwner"], "HEATING")
        self.assertEqual(result["flex"]["sourceGeneratedAt"], "2026-10-07T17:50:00Z")
        self.assertEqual(result["flex"]["ageSec"], 300)
        self.assertTrue(result["flex"]["consistentWithLiveEvDeadline"])

        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("internal", json.dumps(result))

    def test_inactive_deadline_hides_old_deadline_values_and_normalizes_hot_water_mode(self):
        state = self.live_state()
        state["tesla"]["deadline_active"] = False
        state["tesla"]["deadline_at"] = "2026-09-20T07:00:00Z"
        state["tesla"]["remaining_kwh"] = 3.85
        state["hot_water"]["mode"] = False
        flex = self.flex()
        flex["ev"]["deadlineActive"] = False

        server.ENERGY_STATE_FILE = self.write_source(state)
        server.WW_SEASONAL_FILE = self.write_source(self.seasonal())
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(flex)

        result = server.mobile_overview_resource()

        self.assertFalse(result["ev"]["deadlineActive"])
        self.assertIsNone(result["ev"]["deadlineAt"])
        self.assertIsNone(result["ev"]["remainingKWh"])
        self.assertIsNone(result["hotWater"]["mode"])
        self.assertEqual(result["flex"]["status"], "OK")

    def test_inconsistent_flex_ev_deadline_is_not_presented_as_current_decision(self):
        state = self.live_state()
        state["tesla"]["deadline_active"] = False
        flex = self.flex()
        flex["ev"]["deadlineActive"] = True
        flex["decision"]["priorityOwner"] = "EV"
        flex["decision"]["evRole"] = "MUST"
        flex["decision"]["reason"] = "EV_DEADLINE_MUST"

        server.ENERGY_STATE_FILE = self.write_source(state)
        server.WW_SEASONAL_FILE = self.write_source(self.seasonal())
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(flex)

        result = server.mobile_overview_resource()

        self.assertEqual(result["flex"]["status"], "INCONSISTENT")
        self.assertFalse(result["flex"]["consistentWithLiveEvDeadline"])
        self.assertIsNone(result["flex"]["priorityOwner"])
        self.assertIsNone(result["flex"]["evRole"])
        self.assertIsNone(result["flex"]["reason"])
        self.assertEqual(result["heating"]["readyRooms"], [])
        self.assertIsNone(result["heating"]["shadowGrant"])

    def test_stale_flex_is_not_presented_as_current_decision(self):
        flex = self.flex()
        flex["generatedAt"] = "2026-10-07T16:00:00Z"

        server.ENERGY_STATE_FILE = self.write_source(self.live_state())
        server.WW_SEASONAL_FILE = self.write_source(self.seasonal())
        server.FLEX_PRIORITY_SHADOW_FILE = self.write_source(flex)

        result = server.mobile_overview_resource()

        self.assertEqual(result["flex"]["status"], "STALE")
        self.assertGreater(result["flex"]["ageSec"], 4500)
        self.assertIsNone(result["flex"]["priorityOwner"])
        self.assertIsNone(result["flex"]["evRole"])
        self.assertIsNone(result["flex"]["reason"])

    def test_optional_resources_degrade_without_breaking_live_overview(self):
        server.ENERGY_STATE_FILE = self.write_source(self.live_state())
        server.WW_SEASONAL_FILE = "/definitely/missing/seasonal.json"
        server.FLEX_PRIORITY_SHADOW_FILE = "/definitely/missing/flex.json"

        result = server.mobile_overview_resource()

        self.assertEqual(result["schema"], "EMS_MOBILE_OVERVIEW_V1")
        self.assertEqual(result["hotWater"]["seasonalAdvice"]["status"], "UNAVAILABLE")
        self.assertEqual(result["flex"]["status"], "UNAVAILABLE")
        self.assertEqual(result["heating"]["readyRooms"], [])
        self.assertEqual(result["energy"]["pvPowerW"], 4200)


if __name__ == "__main__":
    unittest.main()

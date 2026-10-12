#!/usr/bin/env python3
"""unittest contracts for local-only, six-room, fail-closed Heating actuator DRY-RUN."""
import copy
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[3] / "services/pi/control/heating/evaluate_honeywell_actuator_dry_run_v0_1.py"
spec = importlib.util.spec_from_file_location("heating_dry_run", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 10, 12, 12, 16, tzinfo=timezone.utc)
T0 = NOW.isoformat().replace("+00:00", "Z")
LATER = (NOW + timedelta(minutes=45)).isoformat().replace("+00:00", "Z")


def documents():
    heating_rooms = []
    gate_rooms = []
    honeywell_zones = []
    for key, device in module.ROOM_IDS.items():
        overridden = key in ("douwe_slaapkamer", "erker_douwe")
        mode = "permanent_override" if overridden else "follow_schedule"
        heating_rooms.append({
            "key": key, "preheatScope": True,
            "effective": {"setpointMode": mode, "systemMode": "Auto",
                          "currentTargetTemperature_C": 15.0,
                          "preheatAdvanceAllowed": not overridden},
        })
        gate_rooms.append({
            "key": key, "preheatScope": True,
            "baseline": {"currentTarget_C": 15.0, "futureTarget_C": 17.0,
                         "direction": "UP", "changeAt": LATER},
            "checks": {"sourcesFresh": True, "plannerGrant": True, "cvSafe": True},
            "command": {"action": "WOULD_SET_TEMP", "target_C": 15.5, "physicalWrite": False},
        })
        honeywell_zones.append({"key": key, "homeyDeviceId": device,
                               "targetTemperature_C": 15.0, "setpointMode": mode})
    return {
        "heating": {"schema": "EMS_HEATING_PREHEAT_SHADOW_V0.3", "mode": "READ_ONLY", "controlMode": "SHADOW",
                    "controlWrites": False, "baselineAuthority": "HONEYWELL", "generatedAt": T0,
                    "rooms": heating_rooms},
        "gate": {"schema": "EMS_HEATING_CONTROL_GATE_SHADOW_V0.5", "mode": "READ_ONLY", "controlMode": "SHADOW",
                 "controlWrites": False, "physicalWriteAllowed": False, "baselineAuthority": "HONEYWELL",
                 "generatedAt": T0,
                 "sourceFreshness": {"heating": {"status": "OK"}, "progression": {"status": "OK"},
                                     "progressionConsistentWithHeating": True, "progressionUpstreamSafe": True},
                 "rooms": gate_rooms},
        "grant": {"schema": "EMS_PI_DYNAMIC_HEATING_GRANT_V0.1", "mode": "PRODUCTION_PLANNER_GRANT",
                  "generatedAt": T0, "validUntil": LATER, "physicalWriteAllowed": False,
                  "baselineAuthority": "HONEYWELL", "allocationAuthority": "DYNAMIC_PI_PLANNER",
                  "heating": {"grant": "PRODUCTION_GRANT", "readyRooms": list(module.ROOM_IDS)}},
        "honeywell": {"schema": "EMS_HONEYWELL_STATE_V0.2", "mode": "READ_ONLY", "generatedAt": T0,
                      "location": {"systemMode": "Auto"}, "zones": honeywell_zones},
        "p1": {"meta": {"source_sample_at": T0}, "grid": {"export_w": 1500, "import_w": 0}},
    }


class TestDryRun(unittest.TestCase):
    def run_eval(self, docs):
        result = module.evaluate(docs, now=NOW)
        self.assertEqual(result["roomCount"], 6)
        self.assertEqual(len({x["key"] for x in result["rooms"]}), 6)
        self.assertFalse(result["liveExecutionAllowed"])
        self.assertFalse(result["physicalWriteAllowed"])
        self.assertEqual(result["physicalWrites"], 0)
        self.assertEqual(result["networkCalls"], 0)
        self.assertTrue(all(x["physicalWrite"] is False for x in result["rooms"]))
        return {r["key"]: r for r in result["rooms"]}

    def test_six_rooms_and_permanent_override_blocks_douwe(self):
        rooms = self.run_eval(documents())
        self.assertEqual(rooms["woonkamer"]["status"], "CANDIDATE_ONLY")
        for room in ("douwe_slaapkamer", "erker_douwe"):
            self.assertEqual(rooms[room]["simulatedAction"], "HOLD")
            self.assertIn("HONEYWELL_OVERRIDE_ACTIVE", rooms[room]["denialReasons"])

    def test_override_trumps_upstream_scope_migration(self):
        d = documents()
        for key in ("douwe_slaapkamer", "erker_douwe"):
            next(r for r in d["heating"]["rooms"] if r["key"] == key)["preheatScope"] = False
            next(r for r in d["gate"]["rooms"] if r["key"] == key)["preheatScope"] = False
        rooms = self.run_eval(d)
        for room in ("douwe_slaapkamer", "erker_douwe"):
            self.assertIn("HONEYWELL_OVERRIDE_ACTIVE", rooms[room]["denialReasons"])
            self.assertIn("UPSTREAM_SIX_ROOM_SCOPE_MIGRATION_REQUIRED", rooms[room]["denialReasons"])

    def test_douwe_headline_is_permanent_override_with_target(self):
        rooms = self.run_eval(documents())
        for key in ("douwe_slaapkamer", "erker_douwe"):
            explanation = rooms[key]["diagnosis"]
            self.assertEqual(explanation["primaryCode"], "HONEYWELL_OVERRIDE_ACTIVE")
            self.assertEqual(explanation["category"], "Honeywell")
            self.assertIn("15 °C", explanation["headline"])
            self.assertIn("programma", explanation["advice"])
            self.assertIn("HONEYWELL_OVERRIDE_ACTIVE", rooms[key]["denialReasons"])
            self.assertIn("UPSTREAM_HONEYWELL_OVERRIDE_OR_MODE", explanation["technicalOnly"])

    def test_no_grant_has_human_explanation_and_preserves_code(self):
        d = documents()
        d["grant"]["heating"]["grant"] = "HOLD"
        d["grant"]["heating"]["readyRooms"].remove("keuken")
        rooms = self.run_eval(d)
        explanation = rooms["keuken"]["diagnosis"]
        self.assertEqual(explanation["primaryCode"], "NO_PRODUCTION_HEATING_GRANT")
        self.assertIn("Planner", explanation["headline"])
        self.assertIn("NO_PRODUCTION_HEATING_GRANT", rooms["keuken"]["denialReasons"])
        self.assertIn("ROOM_NOT_IN_PRODUCTION_GRANT", explanation["technicalOnly"])

    def test_no_scheduled_up_is_clearer_than_secondary_v05_symptom(self):
        d = documents()
        g = d["gate"]["rooms"][0]
        g["baseline"]["direction"] = "DOWN"
        g["command"] = {"action": "HOLD", "target_C": None, "physicalWrite": False}
        explanation = self.run_eval(d)["woonkamer"]["diagnosis"]
        self.assertEqual(explanation["primaryCode"], "NO_SCHEDULED_UP")
        self.assertIn("Honeywell", explanation["headline"] + " " + explanation["category"])
        self.assertIn("TARGET_OUTSIDE_UP_BOUNDS", explanation["technicalOnly"])
        self.assertIn("V05_NO_NEW_SET_CANDIDATE", explanation["technicalOnly"])

    def test_override_has_priority_over_missing_pv_or_grant(self):
        d = documents()
        d["p1"]["grid"].update(export_w=0, import_w=200)
        d["grant"]["heating"]["grant"] = "HOLD"
        explanation = self.run_eval(d)["douwe_slaapkamer"]["diagnosis"]
        self.assertEqual(explanation["primaryCode"], "HONEYWELL_OVERRIDE_ACTIVE")
        self.assertIn("NO_PRODUCTION_HEATING_GRANT",
                      [x["code"] for x in explanation["otherReasons"]])

    def test_stale_source_is_not_hidden_by_normal_blockers(self):
        d = documents()
        d["p1"]["meta"]["source_sample_at"] = (NOW - timedelta(minutes=5)).isoformat()
        d["gate"]["rooms"][0]["baseline"]["direction"] = "DOWN"
        explanation = self.run_eval(d)["woonkamer"]["diagnosis"]
        self.assertEqual(explanation["primaryCode"], "P1_SOURCE_STALE_OR_UNTIMED")
        self.assertEqual(explanation["category"], "Gegevens")

    def test_unknown_code_is_shown_not_suppressed(self):
        detail = module.describe_reason("NEW_SAFETY_REASON", None, None)
        self.assertEqual(detail["code"], "NEW_SAFETY_REASON")
        self.assertIn("veiligheidscontrole", detail["title"].lower())

    def test_human_output_has_shared_blockers_once(self):
        d = documents()
        d["p1"]["grid"].update(export_w=0, import_w=100)
        d["grant"]["heating"]["grant"] = "HOLD"
        result = module.evaluate(d, now=NOW)
        report = module.human_report(result)
        self.assertIn("GEEN FYSIEKE AANSTURING", report)
        self.assertIn("Algemeen:", report)
        self.assertIn("Douwe slaapkamer: Permanente Honeywell-override", report)
        self.assertEqual(report.count("Algemeen:"), 1)
        self.assertEqual(len(result["rooms"]), 6)
        self.assertTrue(all(x["diagnosis"]["headline"] for x in result["rooms"]))
        self.assertEqual(result["physicalWrites"], 0)

    def test_candidate_human_explanation_does_not_claim_live_approval(self):
        result = module.evaluate(documents(), now=NOW)
        explanation = next(x for x in result["rooms"] if x["key"] == "woonkamer")["diagnosis"]
        self.assertIsNone(explanation["primaryCode"])
        self.assertIn("alleen simulatie", explanation["headline"])
        self.assertIn("geen fysieke toestemming", explanation["advice"].lower())

    def test_current_p1_import_fails_closed(self):
        d = documents()
        d["p1"]["grid"].update(export_w=0, import_w=500)
        rooms = self.run_eval(d)
        self.assertIn("P1_NOT_EXPORTING_WITHOUT_IMPORT", rooms["woonkamer"]["denialReasons"])

    def test_missing_p1_sample_timestamp_fails_closed(self):
        d = documents()
        d["p1"]["meta"].pop("source_sample_at")
        rooms = self.run_eval(d)
        self.assertIn("P1_SOURCE_STALE_OR_UNTIMED", rooms["woonkamer"]["denialReasons"])

    def test_stale_honeywell_fails_closed(self):
        d = documents()
        d["honeywell"]["generatedAt"] = (NOW - timedelta(minutes=20)).isoformat()
        rooms = self.run_eval(d)
        self.assertIn("HONEYWELL_SOURCE_STALE_OR_UNTIMED", rooms["woonkamer"]["denialReasons"])

    def test_missing_grant_fails_closed(self):
        d = documents()
        d["grant"]["heating"]["grant"] = "HOLD"
        rooms = self.run_eval(d)
        self.assertIn("NO_PRODUCTION_HEATING_GRANT", rooms["woonkamer"]["denialReasons"])

    def test_wrong_homey_id_fails_closed(self):
        d = documents()
        d["honeywell"]["zones"][0]["homeyDeviceId"] = "wrong"
        rooms = self.run_eval(d)
        self.assertIn("HONEYWELL_DEVICE_ID_MISMATCH", rooms["woonkamer"]["denialReasons"])

    def test_manual_temporary_override_blocks(self):
        d = documents()
        d["honeywell"]["zones"][0]["setpointMode"] = "temporary_override"
        rooms = self.run_eval(d)
        self.assertIn("HONEYWELL_OVERRIDE_ACTIVE", rooms["woonkamer"]["denialReasons"])

    def test_next_change_expired_blocks(self):
        d = documents()
        d["gate"]["rooms"][0]["baseline"]["changeAt"] = (NOW - timedelta(minutes=1)).isoformat()
        rooms = self.run_eval(d)
        self.assertIn("SCHEDULED_UP_EXPIRED", rooms["woonkamer"]["denialReasons"])

    def test_no_scheduled_up_blocks(self):
        d = documents()
        d["gate"]["rooms"][0]["baseline"]["direction"] = "DOWN"
        rooms = self.run_eval(d)
        self.assertIn("NO_SCHEDULED_UP", rooms["woonkamer"]["denialReasons"])

    def test_large_step_blocks(self):
        d = documents()
        d["gate"]["rooms"][0]["command"]["target_C"] = 16
        rooms = self.run_eval(d)
        self.assertIn("INITIAL_STEP_EXCEEDS_0_5C", rooms["woonkamer"]["denialReasons"])

    def test_reset_is_never_a_dry_run_physical_command(self):
        d = documents()
        d["gate"]["rooms"][0]["command"] = {"action": "WOULD_RESET_TO_SCHEDULE", "target_C": None, "physicalWrite": False}
        rooms = self.run_eval(d)
        self.assertEqual(rooms["woonkamer"]["simulatedAction"], "HOLD")

    def test_shadow_keep_requires_unproven_physical_ownership(self):
        d = documents()
        d["gate"]["rooms"][0]["command"]["action"] = "WOULD_KEEP_TEMP"
        rooms = self.run_eval(d)
        self.assertEqual(rooms["woonkamer"]["simulatedAction"], "HOLD")
        self.assertIn("V05_KEEP_HAS_NO_PHYSICAL_OWNERSHIP_PROOF",
                      rooms["woonkamer"]["denialReasons"])

    def test_unexpected_override_until_is_not_normal_schedule(self):
        d = documents()
        d["honeywell"]["zones"][0]["overrideUntil"] = LATER
        rooms = self.run_eval(d)
        self.assertIn("HONEYWELL_OVERRIDE_UNTIL_UNEXPECTED",
                      rooms["woonkamer"]["denialReasons"])

    def test_missing_and_duplicate_rooms_fail_closed(self):
        d = documents()
        d["gate"]["rooms"].append(copy.deepcopy(d["gate"]["rooms"][0]))
        rooms = self.run_eval(d)
        self.assertIn("DUPLICATE_OR_INVALID_ROOM_KEYS", rooms["woonkamer"]["denialReasons"])

    def test_no_implicit_freshness_from_planner_republish(self):
        d = documents()
        d["p1"]["generatedAt"] = T0
        d["p1"]["meta"]["source_sample_at"] = (NOW - timedelta(minutes=4)).isoformat()
        rooms = self.run_eval(d)
        self.assertIn("P1_SOURCE_STALE_OR_UNTIMED", rooms["woonkamer"]["denialReasons"])

    def test_untrusted_gate_checks_block(self):
        d = documents()
        d["gate"]["rooms"][0]["checks"]["cvSafe"] = False
        rooms = self.run_eval(d)
        self.assertIn("V05_ROOM_CHECKS_NOT_ALL_TRUE", rooms["woonkamer"]["denialReasons"])

    def test_observed_target_mismatch_blocks(self):
        d = documents()
        d["honeywell"]["zones"][0]["targetTemperature_C"] = 18
        rooms = self.run_eval(d)
        self.assertIn("HONEYWELL_TARGET_MISMATCH", rooms["woonkamer"]["denialReasons"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

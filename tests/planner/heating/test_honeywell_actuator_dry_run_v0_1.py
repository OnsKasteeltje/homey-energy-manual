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

    def test_permanent_override_is_only_in_room_conditions(self):
        result = module.evaluate(documents(), now=NOW)
        self.assertEqual(result["generalConditions"], [])
        by_room = {room["key"]: room for room in result["rooms"]}
        for key in ("douwe_slaapkamer", "erker_douwe"):
            room = by_room[key]
            conditions = room["roomConditions"]
            titles = [x["title"] for x in conditions]
            self.assertTrue(any("Permanente Honeywell-override op 15 °C" == t
                                for t in titles))
            self.assertIn("HONEYWELL_OVERRIDE_ACTIVE",
                          [x["code"] for x in conditions])
            self.assertIn("UPSTREAM_HONEYWELL_OVERRIDE_OR_MODE",
                          room["technicalOnly"])
            self.assertIn("HONEYWELL_OVERRIDE_ACTIVE", room["denialReasons"])

    def test_no_grant_is_shared_condition_without_six_duplicates(self):
        d = documents()
        d["grant"]["heating"].update(grant="HOLD", reason="NO_HEATING_PREHEAT_CANDIDATE")
        result = module.evaluate(d, now=NOW)
        conditions = [x for x in result["generalConditions"]
                      if x["code"] == "NO_PRODUCTION_HEATING_GRANT"]
        self.assertEqual(len(conditions), 1)
        self.assertIn("geen ruimte", conditions[0]["explanation"])
        self.assertEqual(conditions[0]["plannerReasonCode"],
                         "NO_HEATING_PREHEAT_CANDIDATE")
        for room in result["rooms"]:
            self.assertNotIn("NO_PRODUCTION_HEATING_GRANT",
                             [x["code"] for x in room["roomConditions"]])
            self.assertIn("NO_PRODUCTION_HEATING_GRANT", room["denialReasons"])

    def test_room_selection_is_local_only_with_a_valid_shared_grant(self):
        d = documents()
        d["grant"]["heating"]["readyRooms"].remove("keuken")
        result = module.evaluate(d, now=NOW)
        self.assertEqual(result["generalConditions"], [])
        room = next(x for x in result["rooms"] if x["key"] == "keuken")
        self.assertIn("ROOM_NOT_IN_PRODUCTION_GRANT",
                      [x["code"] for x in room["roomConditions"]])

    def test_no_scheduled_up_is_local_and_derived_v05_hidden(self):
        d = documents()
        g = d["gate"]["rooms"][0]
        g["baseline"]["direction"] = "DOWN"
        g["command"] = {"action": "HOLD", "target_C": None, "physicalWrite": False}
        room = self.run_eval(d)["woonkamer"]
        self.assertIn("NO_SCHEDULED_UP", [x["code"] for x in room["roomConditions"]])
        self.assertIn("TARGET_OUTSIDE_UP_BOUNDS", room["technicalOnly"])
        self.assertIn("V05_NO_NEW_SET_CANDIDATE", room["technicalOnly"])

    def test_override_and_shared_p1_grant_are_separate(self):
        d = documents()
        d["p1"]["grid"].update(export_w=0, import_w=200)
        d["grant"]["heating"].update(grant="HOLD", reason="NO_HEATING_PREHEAT_CANDIDATE")
        result = module.evaluate(d, now=NOW)
        shared_codes = [x["code"] for x in result["generalConditions"]]
        self.assertIn("P1_NOT_EXPORTING_WITHOUT_IMPORT", shared_codes)
        self.assertIn("NO_PRODUCTION_HEATING_GRANT", shared_codes)
        room = next(x for x in result["rooms"] if x["key"] == "douwe_slaapkamer")
        self.assertIn("HONEYWELL_OVERRIDE_ACTIVE",
                      [x["code"] for x in room["roomConditions"]])
        self.assertNotIn("P1_NOT_EXPORTING_WITHOUT_IMPORT",
                         [x["code"] for x in room["roomConditions"]])

    def test_stale_p1_is_shared_not_a_room_priority(self):
        d = documents()
        d["p1"]["meta"]["source_sample_at"] = (NOW - timedelta(minutes=5)).isoformat()
        result = module.evaluate(d, now=NOW)
        codes = [x["code"] for x in result["generalConditions"]]
        self.assertIn("P1_SOURCE_STALE_OR_UNTIMED", codes)
        self.assertTrue(any(x["category"] == "Gegevens"
                            for x in result["generalConditions"]))

    def test_unknown_priority_reason_not_invented(self):
        d = documents()
        d["grant"]["heating"].update(
            grant="HOLD", reason="UNRECOGNIZED_REASON", priorityOwner="EV",
            priorityReason="UNRECOGNIZED_REASON",
        )
        result = module.evaluate(d, now=NOW)
        cond = next(x for x in result["generalConditions"]
                    if x["code"] == "NO_PRODUCTION_HEATING_GRANT")
        self.assertIn("niet vertaald", cond["explanation"])
        self.assertEqual(cond["plannerReasonCode"], "UNRECOGNIZED_REASON")
        self.assertEqual(cond["priorityOwner"], "EV")

    def test_no_heating_candidate_does_not_claim_ev_priority(self):
        d = documents()
        d["grant"]["heating"].update(
            grant="HOLD", reason="NO_HEATING_PREHEAT_CANDIDATE",
            priorityOwner="EV", priorityReason="OTHER_REASON",
        )
        condition = next(x for x in module.evaluate(d, now=NOW)["generalConditions"]
                         if x["code"] == "NO_PRODUCTION_HEATING_GRANT")
        self.assertNotIn("autoladen", condition["explanation"])

    def test_unknown_code_is_kept_in_technical_explanation(self):
        d = module.describe_reason("NEW_SAFETY_REASON", None, None)
        self.assertEqual(d["code"], "NEW_SAFETY_REASON")
        self.assertIn("veiligheidscontrole", d["title"].lower())

    def test_human_output_groups_shared_conditions_once(self):
        d = documents()
        d["p1"]["grid"].update(export_w=0, import_w=100)
        d["grant"]["heating"].update(grant="HOLD", reason="NO_HEATING_PREHEAT_CANDIDATE")
        result = module.evaluate(d, now=NOW)
        report = module.human_report(result)
        self.assertIn("GEEN FYSIEKE AANSTURING", report)
        self.assertIn("ALGEMENE VOORWAARDEN", report)
        self.assertIn("PER KAMER", report)
        self.assertIn("Voorverwarmen momenteel niet ingepland", report)
        self.assertIn("Douwe slaapkamer:", report)
        self.assertIn("Permanente Honeywell-override", report)
        self.assertEqual(report.count("Voorverwarmen momenteel niet ingepland"), 1)
        self.assertEqual(len(result["rooms"]), 6)
        self.assertTrue(all("roomConditions" in x for x in result["rooms"]))
        self.assertEqual(result["physicalWrites"], 0)

    def test_simulated_candidate_has_no_room_or_general_blockers(self):
        result = module.evaluate(documents(), now=NOW)
        room = next(x for x in result["rooms"] if x["key"] == "woonkamer")
        self.assertEqual(result["generalConditions"], [])
        self.assertEqual(room["roomConditions"], [])
        self.assertEqual(room["status"], "CANDIDATE_ONLY")
        self.assertFalse(room["liveExecutionAllowed"])

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

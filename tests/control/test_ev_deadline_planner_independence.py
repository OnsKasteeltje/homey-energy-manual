"""Regressions for EV deadline execution when the PV planner is unavailable.

Run directly: python3 tests/control/test_ev_deadline_planner_independence.py
No Homey calls, timers, writes or physical device actions.
"""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

for name, method in (
    ("state_ingest", "handle_state_ingest"),
    ("ev_control_ingest", "handle_ev_control_ingest"),
    ("quooker_evidence_ingest", "handle_quooker_evidence_ingest"),
):
    stub = types.ModuleType(name)
    setattr(stub, method, lambda *args, **kwargs: None)
    sys.modules[name] = stub

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ems_status_deadline_fallback",
    ROOT / "services/pi/api/status/server.py",
)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)

FIXED = {"mode": "FIXED", "id": "ENGIE_3Y_2026_2029"}
NOW = datetime.now(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def policy():
    return {
        "schema": "EMS_CONTROL_AUTHORITY_V1.0",
        "plannerOwner": "PI",
        "executor": "HOMEY",
        "executionEnabled": True,
        "contractMode": "FIXED",
        "contractId": "ENGIE_3Y_2026_2029",
        "cutoverState": "PRODUCTION",
    }


def deadline(active=True, valid=True, future=True):
    return {
        "schema": "EMS_PI_EV_DEADLINE_EXECUTION_V0.1",
        "authority": "PI",
        "valid": valid,
        "active": active,
        "status": "TRACKING" if active else "INACTIVE",
        "requestId": "req-test",
        "deadlineAt": iso(NOW + timedelta(hours=2) if future else NOW - timedelta(minutes=1)),
        "latestStartAt": iso(NOW + timedelta(minutes=15)),
        "remainingKWh": 6.82,
        "maxA": 10,
    }


def plan(valid=True):
    return {
        "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
        "plannerOwner": "PI",
        "readOnly": True,
        "control_writes": False,
        "contract": {"mode": "FIXED", "id": FIXED["id"], "dynamicPricingUsedForProduction": False},
        "inputFreshness": {"status": "PASS" if valid else "FAIL", "failClosed": True},
        "validUntil": iso(NOW + timedelta(minutes=12)),
        "generated_at": iso(NOW),
        "tesla": {"connectedNow": True},
        "slots": [{
            "slot_start_utc": iso(NOW - timedelta(minutes=2)),
            "slot_end_utc": iso(NOW + timedelta(minutes=10)),
            "evPlanW": 5520, "evPlanA": 8,
            "evAllocationReason": "DYNAMIC_PV_OPPORTUNITY",
            "wwPlanW": 1600, "wwAllocationReason": "WW_PLAN",
            "quookerMode": "OPPORTUNITY",
        }],
    }


class TestDeadlinePlannerIndependence(unittest.TestCase):
    def command(self, p=None, dl=None, load_error=None, pol=None):
        p = p if p is not None else plan()
        dl = dl if dl is not None else deadline()
        pol = pol if pol is not None else policy()

        def load(path):
            if path == server.CONTROL_POLICY_FILE:
                return pol
            if path == server.DYNAMIC_PLAN_FILE:
                if load_error:
                    raise load_error
                return p
            raise AssertionError("Unexpected load path: " + str(path))

        with patch.object(server, "load_json", side_effect=load), patch.object(
            server, "ev_deadline_execution_contract", return_value=dl
        ):
            return server.current_control_command()

    def test_healthy_planner_keeps_existing_ev_ww_and_pv_targets(self):
        result = self.command()
        self.assertEqual(result["executionMode"], "PLANNER")
        self.assertTrue(result["planner"]["valid"])
        self.assertEqual(result["targets"]["ev"]["target_W"], 5520)
        self.assertTrue(result["targets"]["ww"]["target_on"])
        self.assertEqual(result["targets"]["quooker"]["mode"], "OPPORTUNITY")
        self.assertTrue(result["realtime"]["ev"]["allowed"])

    def test_stale_planner_valid_deadline_is_ready_but_only_for_ev(self):
        stale = plan()
        stale["validUntil"] = iso(NOW - timedelta(minutes=3))
        result = self.command(p=stale)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["executionMode"], "DEADLINE_ONLY")
        self.assertEqual(result["planner"]["reason"], "PLAN_STALE")
        self.assertFalse(result["planner"]["valid"])
        self.assertEqual(result["deadline"]["requestId"], "req-test")
        self.assertEqual(result["targets"]["ev"]["target_W"], 0)
        self.assertEqual(result["targets"]["ev"]["target_A"], 0)
        self.assertIsNone(result["targets"]["ww"]["target_on"])
        self.assertEqual(result["targets"]["ww"]["target_W"], 0)
        self.assertEqual(result["targets"]["quooker"]["mode"], "OFF")
        self.assertFalse(result["targets"]["quooker"]["opportunity_allowed"])
        self.assertFalse(result["realtime"]["ev"]["allowed"])
        self.assertFalse(result["realtime"]["ev"]["productionConsumerAllowed"])
        self.assertEqual(result["contract"], FIXED)
        self.assertLessEqual(
            server.parse_utc_timestamp(result["validUntil"]),
            datetime.now(timezone.utc) + timedelta(seconds=91),
        )

    def test_missing_planner_can_not_veto_live_deadline(self):
        result = self.command(load_error=FileNotFoundError("plan missing"))
        self.assertEqual(result["executionMode"], "DEADLINE_ONLY")

    def test_corrupt_planner_schema_falls_back(self):
        bad = plan()
        bad["schema"] = "UNKNOWN"
        result = self.command(p=bad)
        self.assertEqual(result["planner"]["reason"], "PLAN_SCHEMA_MISMATCH")

    def test_invalid_planner_inputs_fall_back(self):
        result = self.command(p=plan(valid=False))
        self.assertEqual(result["planner"]["reason"], "PLAN_INPUT_FRESHNESS")

    def test_stale_planner_without_active_deadline_still_fails_closed(self):
        stale = plan()
        stale["validUntil"] = iso(NOW - timedelta(minutes=3))
        with self.assertRaisesRegex(ValueError, "PLAN_STALE"):
            self.command(p=stale, dl=deadline(active=False))

    def test_stale_planner_with_invalid_deadline_still_fails_closed(self):
        stale = plan()
        stale["validUntil"] = iso(NOW - timedelta(minutes=3))
        with self.assertRaisesRegex(ValueError, "PLAN_STALE"):
            self.command(p=stale, dl=deadline(valid=False))

    def test_expired_deadline_cannot_enable_fallback(self):
        stale = plan()
        stale["validUntil"] = iso(NOW - timedelta(minutes=3))
        with self.assertRaisesRegex(ValueError, "DEADLINE_ONLY_NOT_ELIGIBLE"):
            self.command(p=stale, dl=deadline(future=False))

    def test_global_execution_disabled_still_fails_closed(self):
        denied = policy()
        denied["executionEnabled"] = False
        with self.assertRaisesRegex(ValueError, "CONTROL_EXECUTION_DISABLED"):
            self.command(p=plan(valid=False), pol=denied)

    def test_wrong_fixed_contract_still_fails_closed(self):
        denied = policy()
        denied["contractId"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "CONTROL_POLICY_CONTRACT_MISMATCH"):
            self.command(p=plan(valid=False), pol=denied)


class TestControlHealthObservability(unittest.TestCase):
    def test_healthy_planner_reports_ready(self):
        healthy = {
            "executionMode": "PLANNER",
            "planner": {"valid": True, "reason": None},
            "deadline": {"valid": True, "active": True},
            "validUntil": iso(NOW + timedelta(minutes=5)),
        }
        with patch.object(server, "current_control_command", return_value=healthy):
            snapshot = server.control_health_snapshot()
        self.assertEqual(snapshot["control_endpoint_status"], "ready")
        self.assertEqual(snapshot["control_execution_mode"], "PLANNER")
        self.assertEqual(snapshot["control_planner_status"], "ready")
        self.assertIsNone(snapshot["control_planner_reason"])
        self.assertTrue(snapshot["control_deadline_valid"])
        self.assertTrue(snapshot["control_deadline_active"])

    def test_deadline_only_is_available_while_planner_degraded(self):
        fallback = {
            "executionMode": "DEADLINE_ONLY",
            "planner": {"valid": False, "reason": "PLAN_STALE"},
            "deadline": {"valid": True, "active": True},
            "validUntil": iso(NOW + timedelta(seconds=90)),
        }
        with patch.object(server, "current_control_command", return_value=fallback):
            snapshot = server.control_health_snapshot()
        self.assertEqual(snapshot["control_endpoint_status"], "ready")
        self.assertEqual(snapshot["control_execution_mode"], "DEADLINE_ONLY")
        self.assertEqual(snapshot["control_planner_status"], "degraded")
        self.assertEqual(snapshot["control_planner_reason"], "PLAN_STALE")
        self.assertTrue(snapshot["control_deadline_valid"])
        self.assertTrue(snapshot["control_deadline_active"])

    def test_no_eligible_deadline_still_reports_blocked(self):
        with patch.object(
            server, "current_control_command", side_effect=ValueError("PLAN_STALE")
        ):
            snapshot = server.control_health_snapshot()
        self.assertEqual(snapshot["control_endpoint_status"], "blocked:PLAN_STALE")
        self.assertEqual(snapshot["control_planner_status"], "blocked")
        self.assertIsNone(snapshot["control_execution_mode"])
        self.assertFalse(snapshot["control_deadline_active"])
        self.assertFalse(snapshot["control_deadline_valid"])

    def test_health_supports_old_planner_contract_without_mode(self):
        with patch.object(
            server, "current_control_command",
            return_value={"validUntil": iso(NOW + timedelta(minutes=2))}
        ):
            snapshot = server.control_health_snapshot()
        self.assertEqual(snapshot["control_planner_status"], "ready")
        self.assertEqual(snapshot["control_execution_mode"], "PLANNER")


if __name__ == "__main__":
    unittest.main(verbosity=2)

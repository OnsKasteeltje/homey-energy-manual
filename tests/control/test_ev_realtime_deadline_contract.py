import importlib.util
import sys
import types
import unittest

state_ingest = types.ModuleType("state_ingest")
state_ingest.handle_state_ingest = lambda *args, **kwargs: None
sys.modules["state_ingest"] = state_ingest

SPEC = importlib.util.spec_from_file_location("ems_status_server", "services/pi/api/status/server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class TestEvRealtimeDeadlineContract(unittest.TestCase):
    def test_current_pi_deadline_overrides_stale_planner_deadline_snapshot(self):
        plan = {
            "tesla": {
                "connectedNow": True,
                "deadlinePlan": {"active": False, "maxA": 16},
            }
        }
        current = {
            "evAllocationReason": "NO_QUALIFIED_PV_WINDOW",
            "evDeadlineRequired": False,
            "evPlanA": 0,
        }
        deadline = {
            "valid": True,
            "active": True,
            "maxA": 8,
        }

        result = server.ev_realtime_envelope(plan, current, 0, 1900, deadline)

        self.assertTrue(result["deadlineActive"])
        self.assertEqual(result["deadlineMax_A"], 8)
        self.assertEqual(result["max_A"], 8)

    def test_realtime_envelope_exposes_bounded_phase_policy(self):
        plan = {"tesla": {"connectedNow": True}}
        current = {
            "evAllocationReason": "NO_QUALIFIED_PV_WINDOW",
            "evDeadlineRequired": False,
            "evPlanA": 0,
        }
        deadline = {"valid": True, "active": False, "maxA": None}

        result = server.ev_realtime_envelope(plan, current, 0, 0, deadline)
        policy = result["phasePolicy"]

        self.assertEqual(policy["schema"], "EMS_PI_EV_PHASE_POLICY_V0.1")
        self.assertTrue(policy["shadowOnly"])
        self.assertEqual(policy["allowedModes"], ["OFF", "1P", "3P"])
        self.assertEqual(policy["start1p_W"], 1500)
        self.assertEqual(policy["stop1p_W"], 1100)
        self.assertEqual(policy["enter3p_W"], 4400)
        self.assertEqual(policy["leave3p_W"], 3600)
        self.assertEqual(policy["minModeDwellSec"], 120)
        self.assertEqual(policy["physicalPhaseOwner"], "EASEE_EQUALIZER")
        self.assertIsNone(policy["phaseCommand"])

    def test_realtime_envelope_does_not_gate_on_plan_build_connectivity(self):
        plan = {"tesla": {"connectedNow": False}}
        current = {
            "evAllocationReason": "NOT_CONNECTED",
            "evDeadlineRequired": False,
            "evPlanA": 0,
        }
        deadline = {"valid": True, "active": False, "maxA": None}

        result = server.ev_realtime_envelope(plan, current, 0, 0, deadline)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["mode"], "PV_OPPORTUNITY")
        self.assertFalse(result["planConnectedAtBuild"])
        self.assertEqual(result["liveConnectivityOwner"], "HOMEY_EASEE_CHARGE_STATE")
        self.assertEqual(result["phasePolicy"]["allowedModes"], ["OFF", "1P", "3P"])
        self.assertEqual(result["phasePolicy"]["max_A"], 16)


if __name__ == "__main__":
    unittest.main()

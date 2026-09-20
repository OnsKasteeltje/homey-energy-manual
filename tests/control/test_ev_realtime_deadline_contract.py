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


if __name__ == "__main__":
    unittest.main()

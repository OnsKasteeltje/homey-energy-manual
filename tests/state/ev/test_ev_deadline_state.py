import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parents[3] / "services/pi/state/ev/deadline/build_deadline_state.py"
spec = importlib.util.spec_from_file_location("deadline_shadow", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

NOW = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
CMD = {
    "requestId": "req-1",
    "requestedAt": "2026-09-19T20:53:16Z",
    "active": True,
    "deadline": "2026-09-20T07:00",
    "currentSoc": 66,
    "targetSoc": 90,
    "calibrationKWhPerPercent": 0.55,
    "goalKWh": 13.2,
    "maxA": 8,
}


def state(ts, meter=100.0, power=0, charging=False):
    return {
        "meta": {"generated_at": ts},
        "tesla": {
            "meter_kwh": meter,
            "power_w": power,
            "charging": charging,
        },
    }


class TestEvDeadlineShadowState(unittest.TestCase):
    def test_first_sample_captures_baseline_but_does_not_integrate(self):
        out = m.build(CMD, state("2026-09-20T00:00:00Z", power=5579, charging=True), {}, NOW)
        self.assertEqual(out["baselineMeterKWh"], 100.0)
        self.assertEqual(out["deliveredKWh"], 0.0)

    def test_one_minute_at_5579w_integrates_about_0093kwh(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", power=5579, charging=True), {}, NOW)
        out = m.build(CMD, state("2026-09-20T00:01:00Z", power=5579, charging=True), first, NOW)
        self.assertAlmostEqual(out["deliveredKWh"], 5579 / 60000, places=6)
        self.assertAlmostEqual(out["remainingKWh"], 13.2 - 5579 / 60000, places=6)

    def test_stationary_meter_does_not_block_power_progress(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", meter=100.0, power=5579, charging=True), {}, NOW)
        out = m.build(CMD, state("2026-09-20T00:01:00Z", meter=100.0, power=5579, charging=True), first, NOW)
        self.assertGreater(out["deliveredKWh"], 0)
        self.assertEqual(out["meterDeliveredKWh"], 0.0)

    def test_meter_jump_is_checkpoint_and_not_double_counted(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", meter=100.0, power=5579, charging=True), {}, NOW)
        second = m.build(CMD, state("2026-09-20T00:01:00Z", meter=100.0, power=0, charging=False), first, NOW)
        out = m.build(CMD, state("2026-09-20T00:02:00Z", meter=100.093, power=0, charging=False), second, NOW)
        self.assertAlmostEqual(out["deliveredKWh"], 5579 / 60000, places=6)
        self.assertEqual(out["meterDeliveredKWh"], 0.093)
        self.assertIn("SESSION_END_METER_CHECKPOINT_OBSERVED", out["diagnostics"])

    def test_five_minute_canonical_interval_is_integrated(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", power=5579, charging=True), {}, NOW)
        out = m.build(CMD, state("2026-09-20T00:05:00Z", power=5579, charging=True), first, NOW)
        self.assertAlmostEqual(out["deliveredKWh"], 5579 * 300 / 3_600_000, places=6)
        self.assertNotIn("TELEMETRY_GAP_NOT_INTEGRATED", out["diagnostics"])

    def test_gap_beyond_canonical_margin_is_not_integrated(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", power=5579, charging=True), {}, NOW)
        out = m.build(CMD, state("2026-09-20T00:08:00Z", power=5579, charging=True), first, NOW)
        self.assertEqual(out["deliveredKWh"], 0.0)
        self.assertIn("TELEMETRY_GAP_NOT_INTEGRATED", out["diagnostics"])

    def test_no_integration_when_previous_sample_not_charging(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", power=0, charging=False), {}, NOW)
        out = m.build(CMD, state("2026-09-20T00:01:00Z", power=5579, charging=True), first, NOW)
        self.assertEqual(out["deliveredKWh"], 0.0)

    def test_watchdog_refresh_same_telemetry_does_not_double_integrate(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", power=5579, charging=True), {}, NOW)
        second = m.build(CMD, state("2026-09-20T00:05:00Z", power=5579, charging=True), first, NOW)
        refreshed = m.build(CMD, state("2026-09-20T00:05:00Z", power=5579, charging=True), second, NOW)
        self.assertEqual(refreshed["deliveredKWh"], second["deliveredKWh"])
        self.assertEqual(refreshed["lastTelemetryAt"], second["lastTelemetryAt"])

    def test_same_request_keeps_immutable_baseline(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", meter=100.0), {}, NOW)
        out = m.build(CMD, state("2026-09-20T00:01:00Z", meter=102.5), first, NOW)
        self.assertEqual(out["baselineMeterKWh"], 100.0)

    def test_new_request_gets_new_baseline_and_zero_progress(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", meter=100.0, power=5579, charging=True), {}, NOW)
        cmd2 = dict(CMD, requestId="req-2")
        out = m.build(cmd2, state("2026-09-20T00:01:00Z", meter=104.0, power=5579, charging=True), first, NOW)
        self.assertEqual(out["baselineMeterKWh"], 104.0)
        self.assertEqual(out["deliveredKWh"], 0.0)

    def test_meter_reset_does_not_erase_integrated_progress(self):
        previous = {
            "requestId": "req-1",
            "baselineMeterKWh": 100.0,
            "baselineCapturedAt": "2026-09-20T00:00:00Z",
            "deliveredKWh": 1.25,
            "remainingKWh": 11.95,
            "lastTelemetryAt": "2026-09-20T00:00:00Z",
            "lastPowerW": 0,
            "charging": False,
        }
        out = m.build(CMD, state("2026-09-20T00:01:00Z", meter=99.0), previous, NOW)
        self.assertEqual(out["deliveredKWh"], 1.25)
        self.assertIn("METER_RESET_SUSPECTED_IGNORED_FOR_REALTIME_PROGRESS", out["diagnostics"])

    def test_inactive_command_never_captures_baseline(self):
        cmd = dict(CMD, active=False)
        out = m.build(cmd, state("2026-09-20T00:00:00Z", meter=100.0), {}, NOW)
        self.assertEqual(out["status"], "INACTIVE")
        self.assertIsNone(out["baselineMeterKWh"])

    def test_missing_meter_does_not_block_power_integration(self):
        first = m.build(CMD, state("2026-09-20T00:00:00Z", meter=100.0, power=3600, charging=True), {}, NOW)
        no_meter = state("2026-09-20T00:01:00Z", meter=None, power=3600, charging=True)
        out = m.build(CMD, no_meter, first, NOW)
        self.assertAlmostEqual(out["deliveredKWh"], 0.06, places=6)
        self.assertEqual(out["baselineMeterKWh"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

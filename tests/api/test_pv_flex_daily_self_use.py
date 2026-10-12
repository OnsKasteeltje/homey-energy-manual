#!/usr/bin/env python3
"""Daily PV self-use percentage in Evaluatie; pure, read-only contract tests.

11 October values come from verified EMS cumulative-energy day totals.
No dependency on live Pi data, Homey, planner history or device writes.
"""
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "services/pi/api/web-data/server.py"
spec = importlib.util.spec_from_file_location("web_data_daily_pv", MODULE)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class DailyPvSelfUseTest(unittest.TestCase):
    def calculate(self, pv=19.488001, export=4.677998,
                  paired=86400, elapsed=86400, completed=True):
        return api.daily_pv_self_use_accounting(
            pv, export, paired, elapsed, completed,
        )

    def test_october_11_uses_cumulative_energy_and_is_76_percent(self):
        result = self.calculate()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["pairedCoverage"], 1.0)
        self.assertAlmostEqual(result["selfConsumedKWh"], 14.810003, places=6)
        self.assertEqual(result["rate"], 0.76)
        self.assertTrue(result["readOnly"])
        self.assertIn("P1_export", result["source"])

    def test_95_percent_coverage_passes_just_below_fails_closed(self):
        good = self.calculate(paired=86400*.95)
        self.assertEqual(good["status"], "COMPLETE")
        bad = self.calculate(paired=86400*.949)
        self.assertEqual(bad["status"], "INSUFFICIENT_COVERAGE")
        self.assertIsNone(bad["rate"])
        self.assertIsNone(bad["selfConsumedKWh"])

    def test_in_progress_day_is_never_a_final_percentage(self):
        partial = self.calculate(
            pv=4.0, export=1.0, paired=3600, elapsed=3600, completed=False
        )
        self.assertEqual(partial["status"], "PROVISIONAL")
        self.assertEqual(partial["rate"], 0.75)

    def test_a_few_minutes_of_data_is_not_an_authoritative_day(self):
        result = self.calculate(paired=900, elapsed=900, completed=False)
        self.assertEqual(result["status"], "INSUFFICIENT_COVERAGE")
        self.assertIsNone(result["rate"])

    def test_negative_balance_or_missing_pv_never_yields_a_ratio(self):
        invalid = self.calculate(pv=1.0, export=2.0)
        self.assertEqual(invalid["status"], "INVALID_ENERGY_BALANCE")
        self.assertIsNone(invalid["rate"])
        zero = self.calculate(pv=0.0, export=0.0)
        self.assertEqual(zero["status"], "NO_PV_PRODUCTION")
        self.assertIsNone(zero["rate"])

    def test_disjoint_coverage_does_not_get_promoted(self):
        result = self.calculate(paired=18000, elapsed=86400)
        self.assertEqual(result["status"], "INSUFFICIENT_COVERAGE")
        self.assertIsNone(result["rate"])


if __name__ == "__main__":
    unittest.main()

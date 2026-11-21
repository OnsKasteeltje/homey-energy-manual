#!/usr/bin/env python3
"""Fixed ENGIE contract financial evidence without Pi runtime or network."""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "services/pi/history/ems_performance.py"
spec = importlib.util.spec_from_file_location("ems_performance", SRC)
ems = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ems)


class FinancialAccountingTest(unittest.TestCase):
    def good(self):
        return {"p1Coverage": 1.0, "importKWh": 10.0, "exportKWh": 4.0,
                "available": False, "status": "INSUFFICIENT_PAIRED_COVERAGE"}

    def test_post_saldering_supplier_only_without_pv_quality_dependency(self):
        r = ems.financial_accounting(date(2027, 1, 2), self.good())
        self.assertEqual(r["status"], "SUPPLIER_VARIABLE_SUBTOTAL_ONLY")
        self.assertEqual(r["tariffs"]["netExportCreditEurPerKWh"], 0.00539)
        self.assertEqual(r["supplyCostEur"], 1.48)
        self.assertEqual(r["exportCompensationEur"], 0.49)
        self.assertEqual(r["exportChargesEur"], 0.47)
        self.assertEqual(r["netVariableSupplierCostEur"], 1.46)
        self.assertEqual(r["avoidedCostDirectPvEurPerKWhExGovTax"], 0.14229)
        self.assertFalse(r["fullBillAvailable"])
        self.assertIsNone(r["batterySavingsEur"])

    def test_2026_annual_saldering_fails_closed(self):
        r = ems.financial_accounting(date(2026, 11, 20), self.good())
        self.assertEqual(r["status"], "ANNUAL_SALDERING_NO_DAILY_SETTLEMENT")
        self.assertIsNone(r["netVariableSupplierCostEur"])

    def test_quality_gating_and_missing_not_zero(self):
        r = ems.financial_accounting(date(2027, 2, 1),
                   {"p1Coverage": 0.6, "importKWh": 0, "exportKWh": 2})
        self.assertEqual(r["status"], "INSUFFICIENT_P1_COUNTER_COVERAGE")
        self.assertIsNone(r["importKWh"])
        self.assertIsNone(r["netVariableSupplierCostEur"])

    def test_period_and_partial_day(self):
        self.assertEqual(ems.financial_accounting(date(2029, 10, 10), self.good())["status"],
                         "OUTSIDE_VERIFIED_CONTRACT_TERM")
        r = ems.financial_accounting(date(2027, 7, 10), self.good(), day_in_progress=True)
        self.assertEqual(r["status"], "PROVISIONAL_TODAY")
        self.assertFalse(r["governmentTaxes2027Included"])


if __name__ == "__main__":
    unittest.main()

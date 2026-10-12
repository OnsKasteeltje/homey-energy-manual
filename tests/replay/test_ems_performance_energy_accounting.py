#!/usr/bin/env python3
"""Deterministic 2026-10-11 PV accounting regression; no live Pi data needed.

The thirteen power snapshots are a synthetic fixture modelled on the observed
Oct 11 mismatch (twelve disclosed snapshots plus one small residual). They
do NOT claim to reproduce the original raw history byte-for-byte.
"""
import importlib.util
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "services/pi/history/ems_performance.py"
spec = importlib.util.spec_from_file_location("ems_performance", PATH)
ems = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ems)

DAY = date(2026, 10, 11)
START = datetime(2026, 10, 10, 22, tzinfo=timezone.utc)

# Amsterdam-local time -> (P1 export W, summed inverter PV W).
OBSERVED_EXPORT_MISMATCH = {
    "08:55": (583, 424),
    "09:40": (1642, 1233),
    "10:55": (2500, 1557),
    "12:35": (4880, 3791),
    "13:00": (1514, 876),
    "13:50": (3930, 1451),
    "14:55": (1898, 1498),
    "16:00": (1419, 1323),
    "16:10": (3824, 1550),
    "16:15": (2045, 1658),
    "16:20": (2431, 1191),
    "16:25": (2688, 2179),
    # Synthetic 53 W residual reproduces the rounded 0.890 kWh / 13-window case.
    "10:35": (53, 0),
}

DEVICES = (
    "grid_p1", "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000",
    "tesla", "boiler", "quatt_cic",
)


def fixture(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE devices(id INTEGER PRIMARY KEY, device_key TEXT);
        CREATE TABLE metrics(id INTEGER PRIMARY KEY, metric_key TEXT);
        CREATE TABLE measurements(
            id INTEGER PRIMARY KEY, ts_utc TEXT, device_id INTEGER,
            metric_id INTEGER, value_real REAL, quality TEXT
        );
        CREATE TABLE house_energy_intervals(
            start_ts_utc TEXT, end_ts_utc TEXT, duration_seconds INTEGER,
            import_kwh REAL, export_kwh REAL, pv_total_kwh REAL,
            quality TEXT, p1_quality TEXT, pv_quality TEXT
        );
        INSERT INTO metrics VALUES (1, 'electrical_power_w');
    """)
    for did, key in enumerate(DEVICES, 1):
        con.execute("INSERT INTO devices VALUES (?,?)", (did, key))
    for i in range(288):
        start = START + timedelta(minutes=5 * i)
        end = start + timedelta(minutes=5)
        start_s = start.isoformat().replace("+00:00", "Z")
        end_s = end.isoformat().replace("+00:00", "Z")
        local_time = start.astimezone(ems.TZ).strftime("%H:%M")

        # Cumulative-counter-derived interval fixture: fixed day sums.
        # Import and export occupy disjoint intervals.
        pv_kwh = 19.488001 / 144 if 90 <= i < 234 else 0.0
        export_kwh = 4.677998 / 96 if 110 <= i < 206 else 0.0
        import_kwh = 13.252004 / 192 if not 110 <= i < 206 else 0.0
        con.execute(
            "INSERT INTO house_energy_intervals VALUES (?,?,?,?,?,?,?,?,?)",
            (start_s, end_s, 300, import_kwh, export_kwh, pv_kwh,
             "observed", "observed", "observed"),
        )

        if local_time in OBSERVED_EXPORT_MISMATCH:
            export_w, pv_w = OBSERVED_EXPORT_MISMATCH[local_time]
            grid_w = -export_w
        else:
            pv_w = 1800 if 90 <= i < 234 else 0
            grid_w = 100
        values = (grid_w, pv_w, 0, 0, 0, 0, 100)
        for did, value in enumerate(values, 1):
            con.execute(
                "INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality) "
                "VALUES (?,?,?,?,?)",
                (start_s, did, 1, value, "observed"),
            )
    con.commit()
    con.close()


class EmsPerformanceEnergyAccountingTest(unittest.TestCase):
    def test_oct_11_cumulative_kpi_and_synthetic_anomalies(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ems-history.sqlite"
            fixture(db)
            totals = ems.load_energy_interval_accounting(
                DAY, db, datetime(2026, 10, 12, tzinfo=timezone.utc)
            )
            self.assertTrue(totals["available"])
            self.assertEqual(totals["status"], "GOOD")
            self.assertEqual(totals["pairedCoverage"], 1.0)
            self.assertAlmostEqual(totals["pvKWh"], 19.488001, places=5)
            self.assertAlmostEqual(totals["exportKWh"], 4.677998, places=5)
            self.assertAlmostEqual(totals["importKWh"], 13.252004, places=5)
            self.assertAlmostEqual(totals["pvSelfConsumedKWh"], 14.810003, places=5)
            self.assertAlmostEqual(totals["pvSelfConsumptionRate"], 0.76, places=4)

            # Complete-sample power integral remains diagnostic, not KPI authority.
            rows, _ = ems.load_measurements(DAY, db)
            power, _, _ = ems.integrate(rows)
            self.assertEqual(power["pv_p1_impossible_export_intervals"], 13)
            self.assertAlmostEqual(power["pv_p1_impossible_export_kwh"], 0.890, places=3)

    def test_incomplete_paired_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ems-history.sqlite"
            fixture(db)
            with sqlite3.connect(db) as con:
                # Missing 30 intervals (10.4% of the day) invalidates the daily KPI.
                con.execute(
                    "DELETE FROM house_energy_intervals WHERE rowid <= 30"
                )
            totals = ems.load_energy_interval_accounting(
                DAY, db, datetime(2026, 10, 12, tzinfo=timezone.utc)
            )
            self.assertFalse(totals["available"])
            self.assertEqual(totals["status"], "INSUFFICIENT_PAIRED_COVERAGE")
            self.assertIsNone(totals["pvSelfConsumptionRate"])

    def test_no_interval_history_never_invents_cumulative_day_kpi(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ems-history.sqlite"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE measurements(ts_utc TEXT)")
            totals = ems.load_energy_interval_accounting(
                DAY, db, datetime(2026, 10, 12, tzinfo=timezone.utc)
            )
            self.assertFalse(totals["available"])
            self.assertIsNone(totals["pvSelfConsumedKWh"])


if __name__ == "__main__":
    unittest.main()

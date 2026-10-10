#!/usr/bin/env python3
"""KISS regressions for measured P1 and cumulative PV energy, no pytest."""
import importlib.util
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

builder = load("services/pi/history/build_house_energy_history.py", "kiss_builder")
api = load("services/pi/api/web-data/server.py", "kiss_api")


def fixtures(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT);
        CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT);
        CREATE TABLE measurements (
            ts_utc TEXT, device_id INTEGER, metric_id INTEGER,
            value_real REAL, source_resolution_seconds INTEGER, quality TEXT
        );
    """)
    for i, name in enumerate(("grid_p1", "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000"), 1):
        db.execute("INSERT INTO devices VALUES (?,?)", (i, name))
    for i, name in enumerate(("energy_import_kwh", "energy_export_kwh", "energy_produced_kwh"), 1):
        db.execute("INSERT INTO metrics VALUES (?,?)", (i, name))
    return db


class HistoryKissTest(unittest.TestCase):
    def test_mixed_timestamp_precision_keeps_correct_order(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "counter.sqlite"
            db = fixtures(path)
            samples = (
                ("2026-09-19T20:00:00Z", 100.0),
                ("2026-09-19T20:00:00.481Z", 100.0),
                ("2026-09-19T20:05:00Z", 100.4),
            )
            for ts, imported in samples:
                for device, metric, value in (
                    (1, 1, imported), (1, 2, 50.0),
                    (2, 3, 1000.0), (3, 3, 2000.0), (4, 3, 3000.0),
                ):
                    db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?)",
                               (ts, device, metric, value, 300, "observed"))
            db.commit()
            db.close()
            builder.build(path)
            with sqlite3.connect(path) as db:
                rows = db.execute("SELECT import_kwh,quality FROM house_energy_intervals").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0][0], 0.4)
            self.assertEqual(rows[0][1], "observed")

    def test_oct9_delayed_inverter_does_not_hide_measured_house(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "counter.sqlite"
            db = fixtures(path)
            start = datetime(2026, 10, 9, 6, tzinfo=timezone.utc)
            for i in range(52):
                ts = (start + timedelta(minutes=5*i)).isoformat().replace("+00:00", "Z")
                values = (
                    (1, 1, 100 + .2*i), (1, 2, 50.0),
                    (2, 3, 1000 if i < 50 else 1000.456),
                    (3, 3, 2000 + .01*i), (4, 3, 3000.0),
                )
                for device, metric, value in values:
                    db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?)",
                               (ts, device, metric, value, 300, "observed"))
            db.commit()
            db.close()
            builder.build(path)
            with sqlite3.connect(path) as db:
                rows = db.execute("""
                    SELECT import_kwh,pv_total_kwh,house_kwh,p1_quality,pv_quality
                    FROM house_energy_intervals ORDER BY end_ts_utc
                """).fetchall()
            self.assertEqual(len(rows), 51)
            self.assertTrue(all(r[2] is not None for r in rows))
            self.assertAlmostEqual(sum(r[0] for r in rows), 10.2)
            self.assertAlmostEqual(sum(r[1] for r in rows), .966)
            self.assertAlmostEqual(sum(r[2] for r in rows), 11.166)
            self.assertTrue(all(r[3:] == ("observed", "observed") for r in rows))
            # Late PV increment lands in the observed counter interval.
            self.assertAlmostEqual(rows[48][1], .01)
            self.assertAlmostEqual(rows[49][1], .466)

    def test_hourly_api_restores_simple_house_balance(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.sqlite"
            with sqlite3.connect(path) as db:
                db.execute("""
                    CREATE TABLE house_energy_intervals (
                        start_ts_utc TEXT, end_ts_utc TEXT, duration_seconds INTEGER,
                        import_kwh REAL, export_kwh REAL,
                        pv_solaredge_kwh REAL, pv_goodwe4200_kwh REAL,
                        pv_goodwe2000_kwh REAL, pv_total_kwh REAL, house_kwh REAL,
                        quality TEXT, discontinuity_reason TEXT
                    )
                """)
                db.executemany("INSERT INTO house_energy_intervals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
                    ("2026-10-09T06:00:00Z", "2026-10-09T07:00:00Z", 3600,
                     7.93, 0, 0, 0, 0, 0, 7.93, "observed", None),
                    ("2026-10-09T07:00:00Z", "2026-10-09T08:00:00Z", 3600,
                     3.79, 0, .1, .1, .1, .3, 4.09, "observed", None),
                ])
            api.HISTORY_DB = str(path)
            result = api.history_resource("day", "2026-10-09")
            self.assertAlmostEqual(result["summary"]["importKWh"], 11.72)
            self.assertAlmostEqual(result["summary"]["pvKWh"], .3)
            self.assertAlmostEqual(result["summary"]["houseKWh"], 12.02)
            self.assertEqual(len(result["series"]), 24)
            self.assertNotIn("houseMinimumKWh", result["summary"])
            self.assertNotIn("metricQuality", result["quality"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3

import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "services/pi/history/ems_performance.py"
spec = importlib.util.spec_from_file_location("ems_performance", MODULE_PATH)
ems = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ems)


class EmsPerformanceTest(unittest.TestCase):
    def _init_measurement_db(self, path):
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE devices(id INTEGER PRIMARY KEY, device_key TEXT);
            CREATE TABLE metrics(id INTEGER PRIMARY KEY, metric_key TEXT);
            CREATE TABLE measurements(
                id INTEGER PRIMARY KEY,
                ts_utc TEXT,
                device_id INTEGER,
                metric_id INTEGER,
                value_real REAL,
                quality TEXT
            );
        """)
        devices = ["grid_p1","pv_solaredge","pv_goodwe4200","pv_goodwe2000","tesla","boiler","quatt_cic"]
        for i, key in enumerate(devices, 1):
            con.execute("INSERT INTO devices(id,device_key) VALUES (?,?)", (i, key))
        con.execute("INSERT INTO metrics(id,metric_key) VALUES (1,'electrical_power_w')")
        con.execute("INSERT INTO metrics(id,metric_key) VALUES (2,'energy_delivered_kwh')")
        return con, devices

    def make_measurements(self, path):
        con, devices = self._init_measurement_db(path)
        samples = [
            ("2026-09-15T10:00:00Z", {"grid_p1":-1000,"pv_solaredge":2000,"pv_goodwe4200":1000,"pv_goodwe2000":500,"tesla":0,"boiler":1900,"quatt_cic":100}),
            ("2026-09-15T10:05:00Z", {"grid_p1":-1200,"pv_solaredge":2100,"pv_goodwe4200":1000,"pv_goodwe2000":500,"tesla":0,"boiler":1900,"quatt_cic":100}),
            ("2026-09-15T10:10:00Z", {"grid_p1":-1500,"pv_solaredge":2200,"pv_goodwe4200":1000,"pv_goodwe2000":500,"tesla":0,"boiler":0,"quatt_cic":100}),
        ]
        did = {key:i for i,key in enumerate(devices,1)}
        for ts, values in samples:
            for key, value in values.items():
                con.execute(
                    "INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality) VALUES (?,?,?,?,?)",
                    (ts,did[key],1,value,"observed"),
                )
        # Authoritative Easee cumulative meter counter spanning the local day.
        con.execute(
            "INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality) VALUES (?,?,?,?,?)",
            ("2026-09-14T22:00:00Z", did["tesla"], 2, 1000.000, "observed"),
        )
        con.execute(
            "INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality) VALUES (?,?,?,?,?)",
            ("2026-09-15T21:55:00Z", did["tesla"], 2, 1033.005, "observed"),
        )
        con.commit()
        con.close()

    def make_today_measurements(self, path):
        con, devices = self._init_measurement_db(path)
        did = {key:i for i,key in enumerate(devices,1)}

        # 00:00..09:00 Europe/Amsterdam on 2026-10-04 = 22:00Z..07:00Z.
        ts = datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 4, 7, 0, tzinfo=timezone.utc)
        while ts <= end:
            values = {
                "grid_p1": 300,
                "pv_solaredge": 0,
                "pv_goodwe4200": 0,
                "pv_goodwe2000": 0,
                "tesla": 0,
                "boiler": 0,
                "quatt_cic": 100,
            }
            stamp = ts.isoformat().replace("+00:00", "Z")
            for key, value in values.items():
                con.execute(
                    "INSERT INTO measurements(ts_utc,device_id,metric_id,value_real,quality) VALUES (?,?,?,?,?)",
                    (stamp,did[key],1,value,"observed"),
                )
            ts += timedelta(minutes=5)

        con.commit()
        con.close()

    def make_planner(self, path, ts="2026-09-15T10:00:00Z"):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE planner_snapshots(generated_at_utc TEXT, snapshot_zlib BLOB)")
        snap = {
            "plan": {
                "schema":"EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
                "plannerOwner":"PI",
                "contract":{"id":"ENGIE_3Y_2026_2029"},
            },
            "context":{"contextSource":"PLAN_EMBEDDED_DECISION_OUTPUT"},
        }
        con.execute(
            "INSERT INTO planner_snapshots VALUES (?,?)",
            (ts, sqlite3.Binary(zlib.compress(json.dumps(snap).encode()))),
        )
        con.commit()
        con.close()

    def test_today_separates_calendar_progress_from_elapsed_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            mdb = Path(tmp) / "ems-history.sqlite"
            pdb = Path(tmp) / "planner-history.sqlite"
            self.make_today_measurements(mdb)
            self.make_planner(pdb, "2026-10-04T06:00:00Z")

            report = ems.build_report(
                ems.date(2026, 10, 4),
                mdb,
                pdb,
                now_utc=datetime(2026, 10, 4, 7, 0, tzinfo=timezone.utc),
            )

            quality = report["quality"]
            self.assertEqual(quality["status"], "PARTIAL_TODAY")
            self.assertTrue(quality["dayInProgress"])
            self.assertAlmostEqual(quality["dayProgressPct"], 37.5, places=1)
            self.assertAlmostEqual(quality["coveragePctFullDay"], 37.5, places=1)
            self.assertAlmostEqual(quality["coveragePctElapsed"], 100.0, places=1)
            self.assertEqual(quality["elapsedCoverageStatus"], "GOOD_SO_FAR")
            self.assertIn("must not be interpreted as missing", quality["interpretation"])

    def test_report_separates_upper_bound_from_constrained_optimum(self):
        with tempfile.TemporaryDirectory() as tmp:
            mdb = Path(tmp) / "ems-history.sqlite"
            pdb = Path(tmp) / "planner-history.sqlite"
            self.make_measurements(mdb)
            self.make_planner(pdb)
            report = ems.build_report(ems.date(2026, 9, 15), mdb, pdb)

            self.assertEqual(report["schema"], "EMS_PI_DAY_PERFORMANCE_V0.1")
            self.assertGreater(report["metrics"]["pv_kwh"], 0)
            self.assertGreater(report["metrics"]["boiler_kwh"], 0)
            self.assertEqual(report["metrics"]["tesla_meter_delivered_kwh"], 33.005)
            self.assertEqual(
                report["evEnergySemantics"]["actualChargedEnergy"]["authority"],
                "EASEE_CUMULATIVE_METER_DELTA",
            )
            self.assertTrue(
                report["evEnergySemantics"]["actualChargedEnergy"]["available"]
            )
            self.assertFalse(
                report["evEnergySemantics"]["pvGridAllocation"]["measuredDirectly"]
            )
            self.assertEqual(
                report["evEnergySemantics"]["pvGridAllocation"]["authority"],
                "DERIVED_ALLOCATION_FROM_P1_PV_EV_TIMING",
            )
            self.assertEqual(
                report["evEnergySemantics"]["legacyTeslaKWh"]["semantics"],
                "ALIAS_OF_TESLA_POWER_INTEGRAL_KWH",
            )
            self.assertEqual(
                report["benchmark"]["mode"],
                "SAME_FLEX_ENERGY_UNCONSTRAINED_UPPER_BOUND_V0.1",
            )
            self.assertFalse(report["benchmark"]["constrainedOptimumAvailable"])
            self.assertEqual(
                report["benchmark"]["constrainedOptimumStatus"],
                "REPLAY_CONTEXT_INSUFFICIENT",
            )
            self.assertEqual(report["plannerHistory"]["snapshotCount"], 1)


    def test_missing_precommission_counter_does_not_backfill_actual_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            mdb = Path(tmp) / "ems-history.sqlite"
            pdb = Path(tmp) / "planner-history.sqlite"
            self.make_today_measurements(mdb)
            self.make_planner(pdb, "2026-10-04T06:00:00Z")

            report = ems.build_report(
                ems.date(2026, 10, 4),
                mdb,
                pdb,
                now_utc=datetime(2026, 10, 4, 7, 0, tzinfo=timezone.utc),
            )

            self.assertIsNone(report["metrics"]["tesla_meter_delivered_kwh"])
            actual = report["evEnergySemantics"]["actualChargedEnergy"]
            self.assertFalse(actual["available"])
            self.assertIn(
                actual["reason"],
                {"COUNTER_BASELINE_MISSING", "COUNTER_ENDPOINT_MISSING"},
            )


if __name__ == "__main__":
    unittest.main()

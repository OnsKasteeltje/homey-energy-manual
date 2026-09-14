#!/usr/bin/env python3

import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "services/pi/history/ems_performance.py"
spec = importlib.util.spec_from_file_location("ems_performance", MODULE_PATH)
ems = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ems)


class EmsPerformanceTest(unittest.TestCase):
    def make_measurements(self, path):
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
        con.commit()
        con.close()

    def make_planner(self, path):
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
            ("2026-09-15T10:00:00Z", sqlite3.Binary(zlib.compress(json.dumps(snap).encode()))),
        )
        con.commit()
        con.close()

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


if __name__ == "__main__":
    unittest.main()

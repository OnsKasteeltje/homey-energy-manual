#!/usr/bin/env python3
"""KISS cumulative PV counter timing regressions (no pytest required)."""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "services/pi/history/build_house_energy_history.py"
spec = importlib.util.spec_from_file_location("house", SOURCE)
house = importlib.util.module_from_spec(spec)
spec.loader.exec_module(house)


class HeldPvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "history.sqlite"
        self.db = sqlite3.connect(self.path)
        self.db.executescript("""
          CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT);
          CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT);
          CREATE TABLE measurements (
            ts_utc TEXT, device_id INTEGER, metric_id INTEGER,
            value_real REAL, source_resolution_seconds INTEGER, quality TEXT
          );
        """)
        for n, name in enumerate(("grid_p1","pv_solaredge","pv_goodwe4200","pv_goodwe2000"), 1):
            self.db.execute("INSERT INTO devices VALUES (?,?)", (n,name))
        for n, name in enumerate(("energy_import_kwh","energy_export_kwh","energy_produced_kwh"), 1):
            self.db.execute("INSERT INTO metrics VALUES (?,?)", (n,name))

    def sample(self, hhmm, index, se, se_quality):
        ts=f"2026-10-08T{hhmm}:00Z"
        # Import and GoodWe counters are independently observed every 5m.
        data=((1,1,100 + 0.05*index,"observed"),
              (1,2,50 + 0.01*index,"observed"),
              (2,3,se,se_quality),
              (3,3,200 + 0.1*index,"observed"),
              (4,3,300 + 0.05*index,"observed"))
        for dev, metric, value, quality in data:
            self.db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?)",
                            (ts,dev,metric,value,300,quality))

    def build_rows(self):
        self.db.commit()
        house.build(self.path)
        return self.db.execute("""
          SELECT pv_solaredge_kwh,pv_total_kwh,import_kwh,quality,p1_quality,pv_quality
          FROM house_energy_intervals ORDER BY end_ts_utc
        """).fetchall()

    def test_held_counter_no_synthetic_interpolation(self):
        self.sample("10:00",0,1000.0,"observed")
        self.sample("10:05",1,1000.0,"held")
        self.sample("10:10",2,1000.0,"held")
        self.sample("10:15",3,1000.0,"held")
        self.sample("10:20",4,1000.4,"observed")
        rows=self.build_rows()
        self.assertEqual(len(rows),4)
        self.assertEqual([round(x[0],6) for x in rows],[0,0,0,0.4])
        self.assertEqual([round(x[1],6) for x in rows],[0.15,0.15,0.15,0.55])
        self.assertTrue(all(abs(x[2]-0.05)<1e-7 for x in rows))
        self.assertEqual([r[3] for r in rows],["held","held","held","held"])

    def test_observed_plateau_keeps_counter_increment_timing(self):
        # Regression based on SolarEdge 14:40-15:40: identical 'observed'
        # readings precede multi-interval delayed counter increments.
        self.sample("14:40",0,1000.000,"observed")
        self.sample("14:45",1,1000.000,"observed")
        self.sample("14:50",2,1000.000,"observed")
        self.sample("14:55",3,1000.556,"observed")
        self.sample("15:00",4,1000.556,"observed")
        self.sample("15:05",5,1000.556,"observed")
        self.sample("15:10",6,1001.018,"observed")
        rows=self.build_rows()
        self.assertEqual(len(rows),6)
        self.assertEqual([round(x[0],6) for x in rows],[0,0,0.556,0,0,0.462])
        self.assertAlmostEqual(sum(x[0] for x in rows),1.018,places=6)
        self.assertTrue(all(x[3]=="observed" for x in rows))

    def test_long_plateau_preserves_counter_delta(self):
        self.sample("07:00",0,1000,"observed")
        for i in range(1,49):
            minutes=7*60+5*i
            hhmm=f"{minutes//60:02d}:{minutes%60:02d}"
            self.sample(hhmm,i,1000 if i<48 else 1002,
                        "held" if i<48 else "observed")
        rows=self.build_rows()
        self.assertEqual(rows[-1][4],"observed")
        self.assertEqual(rows[-1][5],"held")
        self.assertAlmostEqual(rows[-1][2],0.05)
        self.assertAlmostEqual(rows[-1][0],2.0)
        self.assertAlmostEqual(rows[-1][1],2.15)

    def test_p1_independent_of_late_pv(self):
        self.sample("07:00",0,1000,"observed")
        for i in range(1,49):
            minutes = 7*60 + 5*i
            hhmm = f"{minutes//60:02d}:{minutes%60:02d}"
            self.sample(hhmm, i, 1000 if i < 48 else 1002,
                        "held" if i < 48 else "observed")
        rows=self.build_rows()
        self.assertEqual(rows[-1][4],"observed")
        self.assertEqual(rows[-1][5],"held")
        self.assertGreater(rows[-1][2],0)
        self.assertAlmostEqual(rows[-1][1],2.15)

    def test_no_spurious_pv_for_held_zero_generation(self):
        self.sample("18:00",0,1000,"observed")
        self.sample("18:05",1,1000,"held")
        self.sample("18:10",2,1000,"held")
        self.sample("18:15",3,1000,"observed")
        rows=self.build_rows()
        self.assertTrue(all(r[0]==0 for r in rows))
        self.assertTrue(all(r[2]>0 for r in rows))


if __name__=="__main__":
    unittest.main()

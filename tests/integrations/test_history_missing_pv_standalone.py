#!/usr/bin/env python3
"""Offline 2026-10-09 PV/P1 history regression; no pytest and no real DB writes."""
import importlib.util
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(path, name):
    spec=importlib.util.spec_from_file_location(name, ROOT/path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
builder=load("services/pi/history/build_house_energy_history.py", "history_builder")
api=load("services/pi/api/web-data/server.py", "web_history_api")

class P1PvRegression(unittest.TestCase):
    def test_oct9_long_solar_edge_delay_does_not_erase_other_sources(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"h.sqlite"
            con=sqlite3.connect(path)
            con.executescript("""
              CREATE TABLE devices (id INTEGER PRIMARY KEY,device_key TEXT);
              CREATE TABLE metrics (id INTEGER PRIMARY KEY,metric_key TEXT);
              CREATE TABLE measurements (ts_utc TEXT,device_id INTEGER,
                  metric_id INTEGER,value_real REAL,source_resolution_seconds INTEGER,quality TEXT);
            """)
            for n,name in enumerate(("grid_p1","pv_solaredge","pv_goodwe4200","pv_goodwe2000"),1):
                con.execute("INSERT INTO devices VALUES (?,?)",(n,name))
            for n,name in enumerate(("energy_import_kwh","energy_export_kwh","energy_produced_kwh"),1):
                con.execute("INSERT INTO metrics VALUES (?,?)",(n,name))
            start=datetime(2026,10,9,6,0,tzinfo=timezone.utc)
            for n in range(52):
                stamp=(start+timedelta(minutes=5*n)).isoformat().replace("+00:00","Z")
                # P1 and one GoodWe advance normally, SolarEdge jumps after >3h.
                se=1000.0 if n<50 else 1000.456
                vals=((1,1,100+n*.20),(1,2,50.0),
                      (2,3,se),(3,3,2000+n*.01),(4,3,3000.0))
                con.executemany("INSERT INTO measurements VALUES (?,?,?,?,?,?)",
                      [(stamp,dev,metric,value,300,"observed") for dev,metric,value in vals])
            con.commit()
            con.close()
            builder.build(path)
            with sqlite3.connect(path) as db:
                row=db.execute("""
                    SELECT import_kwh,pv_solaredge_kwh,pv_goodwe4200_kwh,
                           pv_goodwe2000_kwh,pv_total_kwh,house_kwh,p1_quality,pv_quality
                    FROM house_energy_intervals
                    WHERE end_ts_utc='2026-10-09T09:00:00Z'
                """).fetchone()
            self.assertIsNotNone(row)
            self.assertAlmostEqual(row[0],.20)
            self.assertIsNone(row[1])
            self.assertAlmostEqual(row[2],.01)
            self.assertAlmostEqual(row[3],0.0)
            self.assertIsNone(row[4])
            self.assertIsNone(row[5])
            self.assertEqual(row[6],"observed")
            self.assertEqual(row[7],"gap")
    def test_oct9_p1_wins_even_when_house_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"h.sqlite"
            with sqlite3.connect(path) as db:
                db.execute("""CREATE TABLE house_energy_intervals(
                  start_ts_utc TEXT,end_ts_utc TEXT,duration_seconds INTEGER,
                  import_kwh REAL,export_kwh REAL,pv_solaredge_kwh REAL,
                  pv_goodwe4200_kwh REAL,pv_goodwe2000_kwh REAL,
                  pv_total_kwh REAL,house_kwh REAL,quality TEXT,discontinuity_reason TEXT)""")
                # Local Amsterdam hours 08 and 09: one unknown despite 7.93 kWh P1 import.
                db.executemany("INSERT INTO house_energy_intervals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",[
                  ("2026-10-09T06:00:00Z","2026-10-09T07:00:00Z",3600,7.93,0.0,
                   None,0.0,0.0,None,None,"gap",None),
                  ("2026-10-09T07:00:00Z","2026-10-09T08:00:00Z",3600,3.79,0.0,
                   0.1,0.1,0.1,0.3,4.09,"observed",None)
                ])
            api.HISTORY_DB=str(path)
            data=api.history_resource("day","2026-10-09")
            a=[x for x in data["series"] if x["start"].startswith("2026-10-09T08:00")][0]
            b=[x for x in data["series"] if x["start"].startswith("2026-10-09T09:00")][0]
            self.assertAlmostEqual(a["importKWh"],7.93)
            self.assertEqual(a["knownFraction"]["importKWh"],1.0)
            self.assertEqual(a["knownFraction"]["houseKWh"],0.0)
            self.assertAlmostEqual(b["houseKWh"],4.09)
            self.assertEqual(b["knownFraction"]["houseKWh"],1.0)
            self.assertAlmostEqual(data["summary"]["importKWh"],11.72)
            self.assertAlmostEqual(data["summary"]["houseKWh"],4.09)
            self.assertFalse(data["quality"]["metricQuality"]["houseKWh"]["completeWithinMeasuredIntervals"])
            self.assertTrue(data["quality"]["metricQuality"]["importKWh"]["completeWithinMeasuredIntervals"])
            self.assertAlmostEqual(data["quality"]["metricQuality"]["houseKWh"]["fractionOfMeasuredIntervals"],.5)

if __name__=="__main__":
    unittest.main(verbosity=2)

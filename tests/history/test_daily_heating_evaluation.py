#!/usr/bin/env python3
"""Focused contracts: 8-zone evidence, held-PV pairing, partial data, no-write."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/history/daily_heating_evaluation.py"
spec = importlib.util.spec_from_file_location("heating_daily", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DAY = date(2026, 10, 16)
START, END = mod.bounds(DAY)


def make_db(path, missing=()):
    with closing(sqlite3.connect(path)) as con:
        con.executescript("""
        CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT);
        CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT);
        CREATE TABLE measurements_15m (
          slot_start_utc TEXT, device_id INTEGER, metric_id INTEGER,
          value_avg REAL, energy_wh REAL, quality TEXT);
        CREATE TABLE house_energy_intervals (
          start_ts_utc TEXT,end_ts_utc TEXT,import_kwh REAL,export_kwh REAL,
          pv_total_kwh REAL,quality TEXT,p1_quality TEXT,pv_quality TEXT);
        CREATE TABLE measurements (
          ts_utc TEXT,device_id INTEGER,metric_id INTEGER,
          value_real REAL,quality TEXT);
        """)
        devices = {name:i+1 for i,name in enumerate(["quatt_cic", "grid_p1"] +
                   ["honeywell_"+room for room in mod.ROOMS])}
        metrics = {name:i+1 for i,name in enumerate([
            "electrical_power_w","hp1_thermal_power_w","hp2_thermal_power_w",
            "outside_temperature_c","heating_on","room_temperature_c",
            "room_setpoint_c","supervisory_control_mode","gas_meter_m3"])}
        con.executemany("INSERT INTO devices VALUES (?,?)", [(v,k) for k,v in devices.items()])
        con.executemany("INSERT INTO metrics VALUES (?,?)", [(v,k) for k,v in metrics.items()])

        for n in range(96):
            t = START + timedelta(minutes=15*n)
            u = t + timedelta(minutes=15)
            if n in missing:
                continue
            ts = mod.utc(t)
            def metric(device, key, val, wh=None):
                con.execute("INSERT INTO measurements_15m VALUES (?,?,?,?,?,?)",
                            (ts,devices[device],metrics[key],val,wh,"complete"))
            for key, val, wh in (("electrical_power_w",400,100),
                                 ("hp1_thermal_power_w",1200,300),
                                 ("hp2_thermal_power_w",0,0),
                                 ("outside_temperature_c",10,None),
                                 ("heating_on",1,None)):
                metric("quatt_cic",key,val,wh)
            for room in mod.ROOMS:
                metric("honeywell_"+room,"room_temperature_c",19.5)
                metric("honeywell_"+room,"room_setpoint_c",20.)
            daytime = 36 <= n < 72
            con.execute("INSERT INTO house_energy_intervals VALUES (?,?,?,?,?,?,?,?)",
                        (ts,mod.utc(u),0.05,0.02 if daytime else 0,
                         0.10 if daytime else 0,"estimated" if daytime else "held",
                         "observed","estimated" if daytime else "held"))
            con.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                        (ts,devices["quatt_cic"],metrics["supervisory_control_mode"],
                         2.,"observed"))
        for t, gas in ((START,100.),(END-timedelta(minutes=5),100.25)):
            con.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                        (mod.utc(t),devices["grid_p1"],metrics["gas_meter_m3"],gas,"observed"))
        con.commit()


class HeatingDailyTest(unittest.TestCase):
    def test_complete_day_held_pv_and_eight_rooms(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/"h.sqlite"
            make_db(path)
            with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as con:
                result = mod.analyze(con,DAY)
            self.assertEqual(result["quality"]["status"],"GOOD")
            self.assertEqual(result["energy"]["pairedCoverage"],1)
            self.assertEqual(result["energy"]["heldPvHours"],15)
            self.assertEqual(result["energy"]["estimatedPvHours"],9)
            self.assertEqual(result["quattAndRooms"]["quattElectricKWh"],9.6)
            self.assertEqual(result["quattAndRooms"]["pairedHP1HeatToElectricRatio"],3)
            self.assertEqual(len(result["quattAndRooms"]["rooms"]),8)
            self.assertEqual(result["quattAndRooms"]["rooms"]["master_bedroom"]["belowSetpointBy02CSlots"],96)
            self.assertEqual(result["cicAndGas"]["cicBoilerSelectedSamples"],0)
            self.assertEqual(result["cicAndGas"]["gasObservedSpanDeltaM3"],.25)
            self.assertIs(result["controlWrites"],False)

    def test_gaps_remain_unknown_not_invented(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"h.sqlite"
            make_db(path,missing=set(range(12)))
            with closing(sqlite3.connect(f"file:{path}?mode=ro",uri=True)) as con:
                result=mod.analyze(con,DAY)
            self.assertEqual(result["quality"]["status"],"PARTIAL")
            self.assertAlmostEqual(result["energy"]["pairedCoverage"],.875)
            self.assertEqual(result["quattAndRooms"]["quattElectricCompleteSlots"],84)
            self.assertIsNone(result["energy"]["houseKWh"])
            self.assertIn("P1_PV_PAIRED_COVERAGE_OR_BALANCE",result["quality"]["issues"])

    def test_no_write_and_archive_idempotence(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            db=root/"h.sqlite";latest=root/"latest.json";archive=root/"archive.json"
            make_db(db)
            args=[DAY.isoformat(),"--db",str(db),"--latest",str(latest),
                  "--archive",str(archive)]
            self.assertEqual(mod.main(args+["--no-write-output"]),0)
            self.assertFalse(latest.exists());self.assertFalse(archive.exists())
            self.assertEqual(mod.main(args),0)
            self.assertEqual(mod.main(args),0)
            payload=json.loads(archive.read_text())
            self.assertEqual(len(payload["days"]),1)
            self.assertEqual(payload["schema"],mod.ARCHIVE_SCHEMA)
            self.assertEqual(json.loads(latest.read_text())["dateLocal"],DAY.isoformat())

if __name__ == "__main__":
    unittest.main()

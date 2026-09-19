import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "services/pi/history/build_house_energy_history.py"


def _load():
    spec = importlib.util.spec_from_file_location("house_history_under_test", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT NOT NULL);
    CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT NOT NULL);
    CREATE TABLE measurements (
      ts_utc TEXT NOT NULL, device_id INTEGER NOT NULL, metric_id INTEGER NOT NULL,
      value_real REAL
    );
    """)
    devices = ["grid_p1","pv_solaredge","pv_goodwe4200","pv_goodwe2000"]
    for i, key in enumerate(devices, 1):
        con.execute("INSERT INTO devices VALUES (?,?)", (i,key))
    metrics = ["energy_import_kwh","energy_export_kwh","energy_produced_kwh"]
    for i, key in enumerate(metrics, 1):
        con.execute("INSERT INTO metrics VALUES (?,?)", (i,key))
    con.commit()
    return con


def _snapshot(con, ts, imp, exp, se, gw42, gw20):
    rows = [
      (ts,1,1,imp),(ts,1,2,exp),(ts,2,3,se),(ts,3,3,gw42),(ts,4,3,gw20)
    ]
    con.executemany("INSERT INTO measurements VALUES (?,?,?,?)", rows)
    con.commit()


def test_house_formula_and_pv_breakdown(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con,"2026-09-19T20:00:00Z",100,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T20:05:00Z",100.4,50.1,1000.2,2000.3,3000.1)
    con.close()
    _load().build(db)
    con = sqlite3.connect(db)
    row = con.execute("""SELECT import_kwh,export_kwh,pv_solaredge_kwh,
      pv_goodwe4200_kwh,pv_goodwe2000_kwh,pv_total_kwh,house_kwh,quality
      FROM house_energy_intervals""").fetchone()
    con.close()
    expected = (0.4,0.1,0.2,0.3,0.1,0.6,0.9)
    for actual, wanted in zip(row[:7], expected):
        assert abs(actual-wanted) < 1e-9
    assert row[7] == "observed"


def test_counter_decrease_is_discontinuity_not_negative_energy(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con,"2026-09-19T20:00:00Z",100,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T20:05:00Z",99,50.1,1000.2,2000.3,3000.1)
    con.close()
    _load().build(db)
    con = sqlite3.connect(db)
    row = con.execute("""SELECT import_kwh,pv_total_kwh,house_kwh,quality,
      discontinuity_reason FROM house_energy_intervals""").fetchone()
    con.close()
    assert row == (None,None,None,"discontinuity","COUNTER_DECREASE")

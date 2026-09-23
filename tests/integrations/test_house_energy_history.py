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
      value_real REAL, source_resolution_seconds INTEGER,
      quality TEXT NOT NULL DEFAULT 'observed'
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
      (ts,1,1,imp,300,"observed"),(ts,1,2,exp,300,"observed"),
      (ts,2,3,se,300,"observed"),(ts,3,3,gw42,300,"observed"),
      (ts,4,3,gw20,300,"observed")
    ]
    con.executemany("INSERT INTO measurements VALUES (?,?,?,?,?,?)", rows)
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


def test_incomplete_snapshot_bridges_from_last_complete_snapshot(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con,"2026-09-19T20:00:00Z",100,50,1000,2000,3000)
    con.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?)",
                ("2026-09-19T20:10:00Z",1,1,100.2,300,"observed"))
    con.commit()
    _snapshot(con,"2026-09-19T20:25:00Z",100.4,50.1,1000.2,2000.3,3000.1)
    con.close()
    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""SELECT start_ts_utc,end_ts_utc,import_kwh,pv_total_kwh,
      house_kwh,quality,discontinuity_reason FROM house_energy_intervals
      ORDER BY end_ts_utc""").fetchall()
    con.close()
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "2026-09-19T20:00:00Z"
    assert row[1] == "2026-09-19T20:25:00Z"
    assert abs(row[2]-0.4) < 1e-9
    assert abs(row[3]-0.6) < 1e-9
    assert abs(row[4]-0.9) < 1e-9
    assert row[5:] == ("gap",None)


def test_subsecond_duplicate_is_coalesced_without_discontinuity(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con,"2026-09-19T20:00:00.000Z",100,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T20:00:00.481Z",100,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T20:05:00.000Z",100.4,50.1,1000.2,2000.3,3000.1)
    con.close()
    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""SELECT end_ts_utc,import_kwh,house_kwh,quality,
      discontinuity_reason FROM house_energy_intervals ORDER BY end_ts_utc""").fetchall()
    con.close()
    assert len(rows) == 1
    assert rows[0][0] == "2026-09-19T20:05:00.000Z"
    assert abs(rows[0][1] - 0.4) < 1e-9
    assert abs(rows[0][2] - 0.9) < 1e-9
    assert rows[0][3:] == ("observed", None)


def test_subsecond_counter_change_is_preserved_in_next_interval(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con,"2026-09-19T21:30:00.066Z",100,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T21:30:01.048Z",100.007,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T21:35:00.000Z",100.4,50.1,1000.2,2000.3,3000.1)
    con.close()
    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""SELECT start_ts_utc,end_ts_utc,import_kwh,house_kwh,
      quality,discontinuity_reason FROM house_energy_intervals ORDER BY end_ts_utc""").fetchall()
    con.close()
    assert len(rows) == 1
    assert rows[0][0] == "2026-09-19T21:30:00.066Z"
    assert rows[0][1] == "2026-09-19T21:35:00.000Z"
    assert abs(rows[0][2] - 0.4) < 1e-9
    assert abs(rows[0][3] - 0.9) < 1e-9
    assert rows[0][4:] == ("observed", None)


def test_rebuild_removes_obsolete_derived_rows(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con,"2026-09-19T20:00:00Z",100,50,1000,2000,3000)
    _snapshot(con,"2026-09-19T20:05:00Z",100.4,50.1,1000.2,2000.3,3000.1)
    con.close()
    builder = _load()
    builder.build(db)
    con = sqlite3.connect(db)
    con.execute("""INSERT INTO house_energy_intervals
      (start_ts_utc,end_ts_utc,duration_seconds,quality,discontinuity_reason)
      VALUES ('2026-09-19T20:01:00Z','2026-09-19T20:01:00.5Z',0,
              'discontinuity','NON_FORWARD_TIME')""")
    con.commit()
    con.close()
    builder.build(db)
    con = sqlite3.connect(db)
    count = con.execute("""SELECT COUNT(*) FROM house_energy_intervals
      WHERE discontinuity_reason='NON_FORWARD_TIME'""").fetchone()[0]
    con.close()
    assert count == 0


def test_held_counter_snapshot_is_not_used_for_derived_energy(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con, "2026-09-23T10:00:00Z", 100, 50, 1000, 2000, 3000)
    _snapshot(con, "2026-09-23T10:05:00Z", 100.1, 50.2, 1000.1, 2000, 3000)
    con.execute("""
        UPDATE measurements
        SET quality='held'
        WHERE ts_utc='2026-09-23T10:05:00Z' AND device_id IN (3,4)
    """)
    _snapshot(con, "2026-09-23T10:10:00Z", 100.2, 50.3, 1000.2, 2000.2, 3000.1)
    con.close()

    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT start_ts_utc,end_ts_utc,pv_total_kwh,quality
        FROM house_energy_intervals ORDER BY end_ts_utc
    """).fetchall()
    con.close()

    assert len(rows) == 1
    assert rows[0][0] == "2026-09-23T10:00:00Z"
    assert rows[0][1] == "2026-09-23T10:10:00Z"
    assert abs(rows[0][2] - 0.5) < 1e-9
    assert rows[0][3] == "observed"

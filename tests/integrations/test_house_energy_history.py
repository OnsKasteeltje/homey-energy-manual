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


def test_held_counter_snapshot_redistributes_catchup_with_estimated_quality(tmp_path):
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

    result = _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT start_ts_utc,end_ts_utc,pv_solaredge_kwh,
               pv_goodwe4200_kwh,pv_goodwe2000_kwh,
               pv_total_kwh,house_kwh,quality,pv_quality
        FROM house_energy_intervals ORDER BY end_ts_utc
    """).fetchall()
    con.close()

    assert len(rows) == 2
    assert result["pv_estimated_intervals"] == 2

    # SolarEdge was observed at both endpoints, so its native 0.1 kWh
    # interval deltas stay untouched. Both GoodWe catch-up deltas are spread
    # evenly over the two five-minute intervals.
    for row in rows:
        assert abs(row[2] - 0.1) < 1e-9
        assert abs(row[3] - 0.1) < 1e-9
        assert abs(row[4] - 0.05) < 1e-9
        assert abs(row[5] - 0.25) < 1e-9
        assert row[7:] == ("estimated", "estimated")

    assert abs(rows[0][6] - 0.15) < 1e-9
    assert abs(rows[1][6] - 0.25) < 1e-9
    assert abs(sum(row[5] for row in rows) - 0.50) < 1e-9
    assert abs(sum(row[6] for row in rows) - 0.40) < 1e-9


def test_all_three_pv_inverters_use_same_held_catchup_rule(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con, "2026-10-12T11:30:00Z", 100.0, 50.0, 1000.0, 2000.0, 3000.0)

    for minute, imp in ((35, 100.1), (40, 100.2)):
        ts = f"2026-10-12T11:{minute:02d}:00Z"
        _snapshot(con, ts, imp, 50.0, 1000.0, 2000.0, 3000.0)
        con.execute(
            """
            UPDATE measurements
            SET quality='held'
            WHERE ts_utc=? AND device_id IN (2,3,4)
            """,
            (ts,),
        )

    _snapshot(con, "2026-10-12T11:45:00Z", 100.3, 50.0, 1000.3, 2000.6, 3000.9)
    con.close()

    result = _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT pv_solaredge_kwh,pv_goodwe4200_kwh,pv_goodwe2000_kwh,
               pv_total_kwh,quality,pv_quality
        FROM house_energy_intervals
        ORDER BY end_ts_utc
    """).fetchall()
    con.close()

    assert len(rows) == 3
    assert result["pv_estimated_intervals"] == 3

    for row in rows:
        assert abs(row[0] - 0.1) < 1e-9
        assert abs(row[1] - 0.2) < 1e-9
        assert abs(row[2] - 0.3) < 1e-9
        assert abs(row[3] - 0.6) < 1e-9
        assert row[4:] == ("estimated", "estimated")

    assert abs(sum(row[0] for row in rows) - 0.3) < 1e-9
    assert abs(sum(row[1] for row in rows) - 0.6) < 1e-9
    assert abs(sum(row[2] for row in rows) - 0.9) < 1e-9


def test_solaredge_resume_regression_does_not_create_single_interval_spike(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con, "2026-10-12T11:30:00Z", 100.0, 50.0, 17646.18, 23980.9, 10803.7)

    # SolarEdge remains stale/held for seven samples while P1 and GoodWe
    # continue to move. The next observed SolarEdge value contains all energy
    # produced since the 11:30 baseline.
    for index, minute in enumerate((35, 40, 45, 50, 55), start=1):
        ts = f"2026-10-12T11:{minute:02d}:00Z"
        _snapshot(
            con, ts,
            100.0 + index * 0.01,
            50.0,
            17646.18,
            23980.9 + index * 0.1,
            10803.7 + index * 0.1,
        )
        con.execute(
            "UPDATE measurements SET quality='held' WHERE ts_utc=? AND device_id=2",
            (ts,),
        )

    for index, minute in enumerate((0, 5), start=6):
        ts = f"2026-10-12T12:{minute:02d}:00Z"
        _snapshot(
            con, ts,
            100.0 + index * 0.01,
            50.0,
            17646.18,
            23980.9 + index * 0.1,
            10803.7 + index * 0.1,
        )
        con.execute(
            "UPDATE measurements SET quality='held' WHERE ts_utc=? AND device_id=2",
            (ts,),
        )

    _snapshot(
        con, "2026-10-12T12:10:00Z",
        100.08, 50.0,
        17650.016, 23981.7, 10804.5,
    )
    con.close()

    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT pv_solaredge_kwh,quality,pv_quality
        FROM house_energy_intervals
        WHERE start_ts_utc >= '2026-10-12T11:30:00Z'
          AND end_ts_utc <= '2026-10-12T12:10:00Z'
        ORDER BY end_ts_utc
    """).fetchall()
    con.close()

    assert len(rows) == 8
    expected = 3.836 / 8.0
    for se, quality, pv_quality in rows:
        assert abs(se - expected) < 1e-9
        assert quality == "estimated"
        assert pv_quality == "estimated"

    assert abs(sum(row[0] for row in rows) - 3.836) < 1e-9


def test_observed_solaredge_plateaus_are_redistributed(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)

    samples = [
        ("2026-10-12T12:10:00Z", 100.00, 50.00, 17650.016, 23982.3, 10804.3),
        ("2026-10-12T12:15:00Z", 100.01, 50.00, 17650.016, 23982.6, 10804.4),
        ("2026-10-12T12:20:00Z", 100.02, 50.00, 17650.016, 23982.8, 10804.5),
        ("2026-10-12T12:25:00Z", 100.03, 50.00, 17650.810, 23982.9, 10804.5),
        ("2026-10-12T12:30:00Z", 100.04, 50.00, 17650.810, 23983.3, 10804.6),
        ("2026-10-12T12:35:00Z", 100.05, 50.00, 17650.810, 23983.4, 10804.7),
        ("2026-10-12T12:40:00Z", 100.06, 50.00, 17651.598, 23983.5, 10804.7),
    ]
    for row in samples:
        _snapshot(con, *row)
    con.close()

    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT end_ts_utc,pv_solaredge_kwh,quality,pv_quality
        FROM house_energy_intervals
        ORDER BY end_ts_utc
    """).fetchall()
    con.close()

    assert len(rows) == 6
    expected = [0.794 / 3.0] * 3 + [0.788 / 3.0] * 3
    for row, wanted in zip(rows, expected):
        assert abs(row[1] - wanted) < 1e-9
        assert row[2:] == ("estimated", "estimated")

    assert abs(sum(row[1] for row in rows) - (0.794 + 0.788)) < 1e-9


def test_sleeping_pv_counters_do_not_truncate_night_history(tmp_path):
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con, "2026-10-02T17:00:00Z", 100.0, 50.0, 1000.0, 2000.0, 3000.0)
    _snapshot(con, "2026-10-02T17:05:00Z", 100.2, 50.0, 1000.0, 2000.0, 3000.0)
    con.execute("""
        UPDATE measurements
        SET quality='held'
        WHERE ts_utc='2026-10-02T17:05:00Z' AND device_id IN (2,3,4)
    """)
    _snapshot(con, "2026-10-02T17:10:00Z", 100.5, 50.0, 1000.0, 2000.0, 3000.0)
    con.execute("""
        UPDATE measurements
        SET quality='held'
        WHERE ts_utc='2026-10-02T17:10:00Z' AND device_id IN (2,3,4)
    """)
    con.close()

    _load().build(db)
    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT start_ts_utc,end_ts_utc,import_kwh,export_kwh,pv_total_kwh,
               house_kwh,quality
        FROM house_energy_intervals ORDER BY end_ts_utc
    """).fetchall()
    con.close()

    assert len(rows) == 2
    assert rows[0][0:2] == ("2026-10-02T17:00:00Z", "2026-10-02T17:05:00Z")
    assert abs(rows[0][2] - 0.2) < 1e-9
    assert abs(rows[0][4]) < 1e-9
    assert abs(rows[0][5] - 0.2) < 1e-9
    assert rows[0][6] == "held"

    assert rows[1][0:2] == ("2026-10-02T17:05:00Z", "2026-10-02T17:10:00Z")
    assert abs(rows[1][2] - 0.3) < 1e-9
    assert abs(rows[1][4]) < 1e-9
    assert abs(rows[1][5] - 0.3) < 1e-9
    assert rows[1][6] == "held"


def test_sems_cutover_replaces_frozen_homey_goodwe_without_double_count(tmp_path):
    """Risk: held Homey counters must never leak into the new PV total."""
    db = tmp_path / "h.sqlite"
    con = _db(db)
    for index, minute in enumerate((0, 5, 10, 15)):
        ts = f"2026-10-25T08:{minute:02d}:00Z"
        _snapshot(con, ts, 100 + index * .1, 50 + index * .02,
                  1000 + index * .01, 2000, 3000)
        con.execute("""
            UPDATE measurements SET quality='held'
            WHERE ts_utc=? AND device_id IN (3,4)
        """, (ts,))
    con.execute("""
        CREATE TABLE goodwe_sems_curve_15m (
            slot_start_utc TEXT PRIMARY KEY, source_day_local TEXT NOT NULL,
            energy_kwh REAL NOT NULL, coverage_seconds INTEGER NOT NULL,
            fetched_at_utc TEXT NOT NULL
        )
    """)
    con.execute("""
        INSERT INTO goodwe_sems_curve_15m VALUES
        ('2026-10-25T08:00:00+00:00','2026-10-25',0.45,900,
         '2026-10-25T09:00:00+00:00')
    """)
    con.commit()
    con.close()

    result = _load().build(db)
    assert result["rows"] == 3
    with sqlite3.connect(db) as con:
        rows = con.execute("""
            SELECT import_kwh,export_kwh,pv_solaredge_kwh,
                   pv_goodwe4200_kwh,pv_goodwe2000_kwh,
                   pv_goodwe_sems_kwh,pv_total_kwh,house_kwh,pv_quality
            FROM house_energy_intervals ORDER BY start_ts_utc
        """).fetchall()
    for imp, exp, solar, gw42, gw20, sems, pv, house, quality in rows:
        assert gw42 is None and gw20 is None
        assert abs(imp - .1) < 1e-8
        assert abs(exp - .02) < 1e-8
        assert abs(solar - .01) < 1e-8
        assert abs(sems - .15) < 1e-8
        assert abs(pv - .16) < 1e-8
        assert abs(house - .24) < 1e-8
        assert quality == "estimated"


def test_sems_cutover_missing_or_partial_quarter_never_falls_back(tmp_path):
    """Risk: cloud gaps and missing Homey values cannot fabricate PV or house."""
    db = tmp_path / "h.sqlite"
    con = _db(db)
    for index, minute in enumerate((0, 5, 10, 15)):
        ts = f"2026-10-25T08:{minute:02d}:00Z"
        _snapshot(con, ts, 100 + index * .1, 50, 1000, 2000, 3000)
        con.execute("DELETE FROM measurements WHERE ts_utc=? AND device_id IN (3,4)", (ts,))
    con.execute("""
        CREATE TABLE goodwe_sems_curve_15m (
            slot_start_utc TEXT PRIMARY KEY, source_day_local TEXT NOT NULL,
            energy_kwh REAL NOT NULL, coverage_seconds INTEGER NOT NULL,
            fetched_at_utc TEXT NOT NULL
        )
    """)
    con.execute("""
        INSERT INTO goodwe_sems_curve_15m VALUES
        ('2026-10-25T08:00:00+00:00','2026-10-25',0.45,720,
         '2026-10-25T09:00:00+00:00')
    """)
    con.commit()
    con.close()

    assert _load().build(db)["rows"] == 3
    with sqlite3.connect(db) as con:
        rows = con.execute("""
            SELECT import_kwh, pv_goodwe4200_kwh, pv_goodwe2000_kwh,
                   pv_goodwe_sems_kwh, pv_total_kwh, house_kwh,
                   p1_quality, pv_quality
            FROM house_energy_intervals
        """).fetchall()
    for imp, gw42, gw20, sems, pv, house, p1q, pvq in rows:
        assert abs(imp - .1) < 1e-8
        assert gw42 is None and gw20 is None and sems is None
        assert pv is None and house is None
        assert p1q == "observed" and pvq == "gap"


def test_complete_quarter_survives_next_cloud_quarter_missing_at_p1_boundary(tmp_path):
    """Risk: cross-quarter P1 sample hides a complete earlier SEMS+ quarter."""
    db = tmp_path / "h.sqlite"
    con = _db(db)
    _snapshot(con, "2026-10-25T11:44:00.068Z",
              100.0, 50.0, 1000.0, 2000.0, 3000.0)
    _snapshot(con, "2026-10-25T11:46:00.072Z",
              100.2, 50.04, 1000.02, 2000.0, 3000.0)
    con.executescript("""
        CREATE TABLE goodwe_sems_curve_15m (
            slot_start_utc TEXT PRIMARY KEY, source_day_local TEXT NOT NULL,
            energy_kwh REAL NOT NULL, coverage_seconds INTEGER NOT NULL,
            fetched_at_utc TEXT NOT NULL
        );
        INSERT INTO goodwe_sems_curve_15m VALUES
          ('2026-10-25T11:30:00+00:00','2026-10-25',0.18,900,
           '2026-10-25T12:00:00+00:00');
    """)
    con.commit()
    con.close()

    def read():
        with sqlite3.connect(db) as conn:
            return conn.execute("""
                SELECT start_ts_utc,end_ts_utc,import_kwh,export_kwh,
                       pv_solaredge_kwh,pv_goodwe_sems_kwh,pv_total_kwh,
                       house_kwh,p1_quality,pv_quality
                FROM house_energy_intervals ORDER BY julianday(start_ts_utc)
            """).fetchall()

    assert _load().build(db)["rows"] == 2
    first, last = read()
    assert first[0] == "2026-10-25T11:44:00.068Z"
    assert first[1] == last[0] == "2026-10-25T11:45:00.000Z"
    assert last[1] == "2026-10-25T11:46:00.072Z"

    # The first half only depends on its OWN fully observed quarter.
    duration = 120.004
    first_seconds = 59.932
    second_seconds = duration - first_seconds
    assert abs(first[5] - .18 * first_seconds / 900) < 1e-10
    assert abs(first[2] - .2 * first_seconds / duration) < 1e-10
    assert abs(first[4] - .02 * first_seconds / duration) < 1e-10
    assert abs(first[6] - (first[4] + first[5])) < 1e-10
    assert abs(first[7] - (first[2] + first[6] - first[3])) < 1e-10
    assert first[8:] == ("observed", "estimated")
    assert last[5] is None and last[6] is None and last[7] is None
    assert last[8:] == ("observed", "gap")
    assert abs(sum(row[2] for row in (first, last)) - .2) < 1e-10
    assert abs(sum(row[3] for row in (first, last)) - .04) < 1e-10
    assert abs(sum(row[4] for row in (first, last)) - .02) < 1e-10

    # Once the next cloud quarter becomes complete, only that half fills in.
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO goodwe_sems_curve_15m VALUES
            ('2026-10-25T11:45:00+00:00','2026-10-25',0.36,900,
             '2026-10-25T12:15:00+00:00')
        """)
    assert _load().build(db)["rows"] == 2
    first_updated, last_updated = read()
    assert first_updated[5] == first[5]
    assert abs(last_updated[5] - .36 * second_seconds / 900) < 1e-10
    assert last_updated[6] is not None and last_updated[7] is not None
    assert last_updated[8:] == ("observed", "estimated")
    assert abs(sum(row[2] for row in (first_updated, last_updated)) - .2) < 1e-10

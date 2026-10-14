#!/usr/bin/env python3
"""No pytest: dishwasher history is P1-only; no inverter/EV completeness gate."""
import ast
import importlib.util
import math
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

api_path = Path("services/pi/api/web-data/server.py")
archive_path = Path("services/pi/api/status/history_archive.py")
source = api_path.read_text(encoding="utf-8")
helper = next(x for x in ast.parse(source).body
              if isinstance(x, ast.FunctionDef) and x.name == "_live_l1_history")
fn_code = compile(ast.Module(body=[helper], type_ignores=[]), "<web-data>", "exec")
helper_text = ast.get_source_segment(source, helper)
assert "pv_solaredge" not in helper_text, "PV in P1 diagnostic path"
assert "solaredge_w" not in helper_text, "PV in P1 diagnostic output"
assert '"l1_net_w" in item' in helper_text

with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / "history.sqlite"
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT);
            CREATE TABLE measurements (
                ts_utc TEXT, device_id INTEGER, metric_id INTEGER,
                value_real REAL, quality TEXT);
            INSERT INTO devices VALUES
                (1,'grid_p1'),(2,'pv_solaredge'),(3,'tesla');
            INSERT INTO metrics VALUES
                (1,'grid_l1_power_w'),(2,'electrical_power_w');
        """)
        now = datetime.now(timezone.utc)
        def add(age_min, l1, pv=None, ev=None, quality="observed"):
            at = (now - timedelta(minutes=age_min)).isoformat()
            con.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                        (at, 1, 1, l1, quality))
            if pv is not None:
                con.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                            (at, 2, 2, pv, "held"))
            if ev is not None:
                con.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                            (at, 3, 2, ev, "observed"))
        add(40, 1900, pv=90)
        add(30, 300)        # no inverter, no Tesla at all
        add(20, 2100, ev=0)
        add(10, 1750, pv=100, ev=2500)
        add(5, 9999, quality="held")
        con.commit()

    ctx = {"HISTORY_DB": str(path), "sqlite3": sqlite3, "math": math,
           "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    exec(fn_code, ctx)
    rows = ctx["_live_l1_history"]()
    assert len(rows) == 4, rows
    assert all("at" in r and "l1_net_w" in r for r in rows)
    assert all("solaredge_w" not in r for r in rows)
    assert rows[0]["l1_net_w"] == 1900
    assert rows[1]["l1_net_w"] == 300
    assert rows[2]["tesla_w"] == 0
    assert rows[3]["tesla_w"] == 2500
    assert not any(r["l1_net_w"] == 9999 for r in rows)

    ctx["HISTORY_DB"] = str(Path(temp) / "missing.sqlite")
    assert ctx["_live_l1_history"]() == []

    # Full SQLite archive smoke test: legacy p1Fresh=false does not override
    # the canonical grid validity gate for per-phase diagnostic measurements.
    live_db = Path(temp) / "archive.sqlite"
    with sqlite3.connect(live_db) as con:
        con.executescript("""
            CREATE TABLE devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL, source_device_id TEXT NOT NULL UNIQUE,
                device_key TEXT NOT NULL UNIQUE, name TEXT, device_type TEXT
            );
            CREATE TABLE metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_key TEXT NOT NULL UNIQUE, unit TEXT,
                value_type TEXT, description TEXT
            );
            CREATE TABLE measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL, device_id INTEGER NOT NULL,
                metric_id INTEGER NOT NULL,
                value_real REAL, value_text TEXT,
                quality TEXT, source_resolution_seconds INTEGER,
                UNIQUE(ts_utc, device_id, metric_id)
            );
            INSERT INTO metrics(metric_key, unit, value_type, description)
              VALUES ('electrical_power_w','W','number','power');
        """)
    spec = importlib.util.spec_from_file_location("archive_test", archive_path)
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)

    payload = {
        "meta": {"source_sample_at": now.isoformat()},
        "grid": {"power_w": 2009, "l1_w": 2009, "l2_w": 2136,
                 "l3_w": -183},
        "balance": {"control_gate": {"grid_measurement_valid": True},
                    "source_timing": {"p1Fresh": False}},
    }
    result = archive.archive_state_history(payload, live_db)
    assert result["archived"] is True
    with sqlite3.connect(live_db) as con:
        measurements = con.execute("""
            SELECT m.metric_key, x.value_real, x.quality
            FROM measurements x
            JOIN devices d ON d.id=x.device_id
            JOIN metrics m ON m.id=x.metric_id
            WHERE d.device_key='grid_p1'
              AND m.metric_key IN
                  ('grid_l1_power_w','grid_l2_power_w','grid_l3_power_w')
            ORDER BY m.metric_key
        """).fetchall()
    assert measurements == [
        ("grid_l1_power_w", 2009.0, "observed"),
        ("grid_l2_power_w", 2136.0, "observed"),
        ("grid_l3_power_w", -183.0, "observed"),
    ], measurements

    payload["meta"]["source_sample_at"] = (now + timedelta(minutes=5)).isoformat()
    payload["balance"]["control_gate"]["grid_measurement_valid"] = False
    archive.archive_state_history(payload, live_db)
    with sqlite3.connect(live_db) as con:
        assert con.execute("""
            SELECT COUNT(*) FROM measurements x
            JOIN metrics m ON m.id=x.metric_id
            WHERE m.metric_key LIKE 'grid_l%_power_w'
        """).fetchone()[0] == 3

print("PASS: P1-only L1 history, independent of all inverters, canonical validity gate")

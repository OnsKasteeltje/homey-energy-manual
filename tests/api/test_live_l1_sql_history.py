#!/usr/bin/env python3
"""No pytest: Pi-backed Live L1 evidence is bounded, fresh and diagnostic only."""
import ast
import math
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

source = Path("services/pi/api/web-data/server.py").read_text(encoding="utf-8")
helper = next(x for x in ast.parse(source).body
              if isinstance(x, ast.FunctionDef) and x.name == "_live_l1_history")
fn_code = compile(ast.Module(body=[helper], type_ignores=[]), "<web-data>", "exec")
archive = Path("services/pi/api/status/history_archive.py").read_text(encoding="utf-8")
assert '"grid_l1_power_w":' in archive
assert '_quality_for_power(payload, "grid_p1") == "observed"' in archive
assert "INSERT OR IGNORE INTO measurements" in archive

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
        def add(age_min, l1, pv, ev, pv_quality="observed"):
            at = (now - timedelta(minutes=age_min)).isoformat()
            con.execute("INSERT INTO measurements VALUES (?,?,?,?,'observed')",
                        (at, 1, 1, l1))
            con.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                        (at, 2, 2, pv, pv_quality))
            con.execute("INSERT INTO measurements VALUES (?,?,?,?,'observed')",
                        (at, 3, 2, ev))
        add(30, 1900, 90, 0)
        add(20, 300, 80, 0)
        add(10, 2100, 30, 0, pv_quality="held")
        add(5, 1750, 100, 2500)
        con.commit()

    ctx = {
        "HISTORY_DB": str(path), "sqlite3": sqlite3, "math": math,
        "datetime": datetime, "timedelta": timedelta, "timezone": timezone
    }
    exec(fn_code, ctx)
    result = ctx["_live_l1_history"]()
    assert len(result) == 3, result
    assert all(set(x) == {"at", "l1_net_w", "solaredge_w", "tesla_w"}
               for x in result)
    assert result[0]["l1_net_w"] == 1900
    assert result[-1]["tesla_w"] == 2500
    assert not any(x["l1_net_w"] == 2100 for x in result), "held PV must be excluded"

    ctx["HISTORY_DB"] = str(Path(temp) / "missing.sqlite")
    assert ctx["_live_l1_history"]() == [], "missing DB must fail closed"

print("PASS: bounded read-only Pi L1 history, reject stale PV and tolerate missing DB")

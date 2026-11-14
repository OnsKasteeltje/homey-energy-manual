#!/usr/bin/env python3
"""Read-only Live battery API: no stale/partial/foreign metrics represented as current."""
import ast
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import sqlite3
import tempfile

text = Path("services/pi/api/web-data/server.py").read_text(encoding="utf-8")
tree = ast.parse(text)
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ("live_battery_resource", "parse_timestamp")]
constants = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in
                     ("BATTERY_LIVE_METRICS", "LIVE_BATTERY_API_SCHEMA")
                     for t in n.targets)]
ctx = {"datetime": datetime, "timezone": timezone, "sqlite3": sqlite3, "math": math}
exec(compile(ast.Module(body=constants + functions, type_ignores=[]), "<battery>", "exec"), ctx)
assert ctx["LIVE_BATTERY_API_SCHEMA"] == "EMS_WEB_LIVE_BATTERY_V1"
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "history.sqlite"
    now = datetime(2026, 11, 14, 21, 0, tzinfo=timezone.utc)
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT UNIQUE);
        CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT UNIQUE);
        CREATE TABLE measurements (
            ts_utc TEXT, device_id INTEGER, metric_id INTEGER,
            value_real REAL, quality TEXT);
        INSERT INTO devices VALUES (1, 'battery_alphaess');
        INSERT INTO devices VALUES (2, 'grid_p1');
        """)
        for i, key in enumerate(ctx["BATTERY_LIVE_METRICS"], start=1):
            db.execute("INSERT INTO metrics VALUES (?, ?)", (i, key))
        values = {
            "soc_pct": 10.8, "module_count": 2,
            "nominal_capacity_kwh": 8, "soh_pct": 100,
            "battery_dc_power_w": 0, "battery_ac_power_w": -13,
            "battery_charge_total_kwh": 44.6,
            "battery_discharge_total_kwh": 41.5,
        }
        at = (now - timedelta(seconds=80)).isoformat()
        for i, key in enumerate(ctx["BATTERY_LIVE_METRICS"], start=1):
            db.execute("INSERT INTO measurements VALUES (?, 1, ?, ?, 'observed')",
                       (at, i, values[key]))
        db.execute("INSERT INTO measurements VALUES (?, 2, 1, 9999, 'observed')", (at,))
    ctx["HISTORY_DB"] = str(path)
    resource = ctx["live_battery_resource"]
    current = resource(now=now)
    assert current["status"] == "FRESH", current
    assert current["measurements"]["socPct"] == 10.8
    assert current["measurements"]["acPowerW"] == -13
    assert current["measurements"]["chargeTotalKWh"] == 44.6
    assert current["ageSec"] == 80
    assert current["eligibleForControl"] is False
    assert current["eligibleForHouseBalance"] is False
    assert set(current["measurements"]) == set(ctx["BATTERY_LIVE_METRICS"].values())
    assert "gridChargeReportedKWh" not in current["measurements"]
    stale = resource(now=now + timedelta(seconds=260))
    assert stale["status"] == "STALE"
    assert all(v is None for v in stale["measurements"].values())
    with sqlite3.connect(path) as db:
        db.execute("UPDATE measurements SET quality='partial' WHERE device_id=1 AND metric_id=1")
    partial = resource(now=now)
    assert partial["status"] == "PARTIAL"
    assert all(v is None for v in partial["measurements"].values())
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM measurements WHERE device_id=1")
    missing = resource(now=now)
    assert missing["status"] == "UNAVAILABLE"
    assert all(v is None for v in missing["measurements"].values())
assert 'path.path == "/web/live/battery"' in text
assert "def do_POST(self):" in text
assert "method_not_allowed" in text
print("PASS: AlphaESS V0.3 isolated battery Web Data resource")

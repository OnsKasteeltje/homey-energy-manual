#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
WW_PLAN = Path("/home/jeroen/ems/data/ww-plan.json")

plan = json.loads(WW_PLAN.read_text())

generated_at = plan.get("generated_at")
mode = plan.get("mode")

if not generated_at:
    raise SystemExit("FAIL: ww-plan generated_at missing")

rows = []

for day in plan.get("dailyPlans", []):
    target_date = day.get("date")
    expected = day.get("expectedDailyEnergyShadowKWh")
    source = day.get("expectedDailyEnergyShadowSource")
    required = day.get("requiredEnergyKWh")

    if not target_date or expected is None or not source:
        continue

    rows.append((
        generated_at,
        target_date,
        float(expected),
        source,
        float(required) if required is not None else None,
        mode,
    ))

con = sqlite3.connect(DB)

con.execute("""
CREATE TABLE IF NOT EXISTS forecast_ww_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at_utc TEXT NOT NULL,
    target_date_local TEXT NOT NULL,
    expected_energy_kwh REAL NOT NULL,
    source TEXT NOT NULL,
    required_energy_kwh REAL,
    planner_mode TEXT,
    UNIQUE(generated_at_utc, target_date_local, source)
)
""")

con.execute("""
CREATE INDEX IF NOT EXISTS idx_forecast_ww_daily_target
ON forecast_ww_daily(target_date_local)
""")

con.execute("""
CREATE INDEX IF NOT EXISTS idx_forecast_ww_daily_generated
ON forecast_ww_daily(generated_at_utc)
""")

con.executemany("""
INSERT OR IGNORE INTO forecast_ww_daily (
    generated_at_utc,
    target_date_local,
    expected_energy_kwh,
    source,
    required_energy_kwh,
    planner_mode
)
VALUES (?, ?, ?, ?, ?, ?)
""", rows)

con.commit()
con.close()

print(f"PASS: stored {len(rows)} WW daily forecast rows")

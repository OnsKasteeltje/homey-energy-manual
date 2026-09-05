#!/usr/bin/env python3

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DAY_HISTORY = Path("/home/jeroen/ems/data/homey-day-history.json")
DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
OUTPUT = Path("/home/jeroen/ems/data/clean-base-history.json")

def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()

history = json.loads(DAY_HISTORY.read_text())
samples = history.get("samples", [])

con = sqlite3.connect(DB)
cur = con.cursor()

row = cur.execute("""
    SELECT d.id, m.id
    FROM devices d
    JOIN metrics m
    WHERE d.device_key='quatt_cic'
      AND m.metric_key='electrical_power_w'
""").fetchone()

if not row:
    raise SystemExit("FAIL: Quatt metric not found in SQLite")

device_id, metric_id = row

quatt_rows = cur.execute("""
    SELECT ts_utc, value_real
    FROM measurements
    WHERE device_id=?
      AND metric_id=?
      AND value_real IS NOT NULL
    ORDER BY ts_utc
""", (device_id, metric_id)).fetchall()

con.close()

quatt = [(parse_ts(ts), float(v)) for ts, v in quatt_rows]

out = []
matched = 0
unmatched = 0

for s in samples:
    if s.get("p1Valid") is not True or s.get("p1W") is None or not s.get("ts"):
        continue

    t = parse_ts(s["ts"])

    nearest = None
    nearest_dt = None

    for qt, qv in quatt:
        dt = abs(qt - t)
        if nearest_dt is None or dt < nearest_dt:
            nearest_dt = dt
            nearest = qv

    # maximaal 7,5 minuut verschil accepteren
    if nearest is None or nearest_dt > 450:
        quatt_w = None
        unmatched += 1
    else:
        quatt_w = max(0.0, nearest)
        matched += 1

    pv_w = (
        max(0.0, float(s.get("solarEdgeW") or 0))
        + max(0.0, float(s.get("goodWe4200W") or 0))
        + max(0.0, float(s.get("goodWe2000W") or 0))
    )

    house_w = float(s["p1W"]) + pv_w
    tesla_w = max(0.0, float(s.get("teslaW") or 0))
    boiler_w = max(0.0, float(s.get("boilerW") or 0))

    clean_base = None
    if quatt_w is not None:
        clean_base = max(
            0.0,
            house_w - tesla_w - boiler_w - quatt_w
        )

    out.append({
        "ts": s["ts"],
        "p1W": round(float(s["p1W"])),
        "pvW": round(pv_w),
        "teslaW": round(tesla_w),
        "boilerW": round(boiler_w),
        "quattActualW": None if quatt_w is None else round(quatt_w),
        "houseActualW": round(house_w),
        "cleanBaseW": None if clean_base is None else round(clean_base),
        "washerActive": s.get("washerActive") is True,
        "dryerActive": s.get("dryerActive") is True,
    })

payload = {
    "schema": "EMS_PI_CLEAN_BASE_HISTORY_V0.1",
    "source": "EM2_Day_History + local Quatt SQLite",
    "control_writes": False,
    "sample_count": len(out),
    "quatt_matched": matched,
    "quatt_unmatched": unmatched,
    "samples": out,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
tmp.replace(OUTPUT)

print("PASS: clean base history built")
print("samples        :", len(out))
print("Quatt matched  :", matched)
print("Quatt unmatched:", unmatched)

vals = [x["cleanBaseW"] for x in out if x["cleanBaseW"] is not None]
if vals:
    print("clean base min :", min(vals))
    print("clean base avg :", round(sum(vals) / len(vals), 1))
    print("clean base max :", max(vals))

print("output         :", OUTPUT)

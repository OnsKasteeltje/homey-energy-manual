#!/usr/bin/env python3

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "/home/jeroen/ems/data/ems-history.sqlite"
TZ = ZoneInfo("Europe/Amsterdam")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== TABLE SCHEMA: measurements ===")
for r in con.execute("PRAGMA table_info(measurements)"):
    print(dict(r))

print("\n=== TESLA DEVICE ===")
tesla = con.execute("SELECT id, device_key FROM devices WHERE device_key='tesla'").fetchone()
print(dict(tesla) if tesla else "NO TESLA DEVICE")
if not tesla:
    raise SystemExit(1)

device_id = tesla["id"]

print("\n=== TESLA METRICS PRESENT ===")
rows = con.execute("""
SELECT m.id AS metric_id, m.metric_key,
       COUNT(x.rowid) AS samples,
       MIN(x.ts_utc) AS first_ts,
       MAX(x.ts_utc) AS last_ts
FROM measurements x
JOIN metrics m ON m.id=x.metric_id
WHERE x.device_id=?
GROUP BY m.id, m.metric_key
ORDER BY m.metric_key
""", (device_id,)).fetchall()
for r in rows:
    print(dict(r))

cols = [r[1] for r in con.execute("PRAGMA table_info(measurements)")]
value_cols = [c for c in cols if c.startswith("value_")]
print("\nVALUE_COLUMNS=", value_cols)

candidate_keys = []
for r in rows:
    k = (r["metric_key"] or "").lower()
    if any(token in k for token in ("connect", "plug", "status", "state", "active", "charging", "present")):
        candidate_keys.append(r["metric_key"])

print("\n=== CONNECTION/STATE CANDIDATES ===")
print(candidate_keys if candidate_keys else "NONE")

for key in candidate_keys:
    print(f"\n--- RECENT VALUES {key} ---")
    metric_id = con.execute("SELECT id FROM metrics WHERE metric_key=?", (key,)).fetchone()[0]
    sel_values = ", ".join(value_cols) if value_cols else "NULL AS no_value"
    q = f"""
    SELECT ts_utc, {sel_values}
    FROM measurements
    WHERE device_id=? AND metric_id=?
    ORDER BY ts_utc DESC
    LIMIT 40
    """
    for r in con.execute(q, (device_id, metric_id)):
        print(tuple(r))

print("\n=== MONDAY TESLA POWER ACTIVITY (fallback signal, not disconnect proof) ===")
metric = con.execute("SELECT id FROM metrics WHERE metric_key='electrical_power_w'").fetchone()
if metric:
    metric_id = metric[0]
    power_rows = con.execute("""
    SELECT ts_utc, value_real
    FROM measurements
    WHERE device_id=? AND metric_id=? AND value_real IS NOT NULL
    ORDER BY ts_utc
    """, (device_id, metric_id)).fetchall()

    grouped = {}
    for r in power_rows:
        try:
            dt = datetime.fromisoformat(str(r["ts_utc"]).replace("Z", "+00:00")).astimezone(TZ)
        except Exception:
            continue
        if dt.weekday() != 0:
            continue
        d = dt.date().isoformat()
        grouped.setdefault(d, []).append((dt, float(r["value_real"] or 0)))

    for d in sorted(grouped):
        vals = grouped[d]
        active = [(dt, w) for dt, w in vals if w > 100]
        first = active[0][0].isoformat() if active else None
        last = active[-1][0].isoformat() if active else None
        print({"date": d, "samples": len(vals), "first_power_gt_100W": first, "last_power_gt_100W": last})
else:
    print("NO electrical_power_w metric")

print("\n=== RESULT ===")
if candidate_keys:
    print("STATE_SIGNAL_AVAILABLE=1")
    print("NEXT: inspect transitions to infer plug-out/disconnect times safely")
else:
    print("STATE_SIGNAL_AVAILABLE=0")
    print("No explicit connection/state metric is stored in SQLite; power data alone cannot prove departure time.")

con.close()

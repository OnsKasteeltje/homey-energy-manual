#!/usr/bin/env python3

import bisect
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
OUTPUT = Path("/home/jeroen/ems/data/clean-base-history.json")
MAX_MATCH_SECONDS = 450


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def load_series(cur, device_key, metric_key):
    row = cur.execute(
        """
        SELECT d.id, m.id
        FROM devices d
        JOIN metrics m
        WHERE d.device_key=?
          AND m.metric_key=?
        """,
        (device_key, metric_key),
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing SQLite series: {device_key}/{metric_key}")

    device_id, metric_id = row
    rows = cur.execute(
        """
        SELECT ts_utc, value_real
        FROM measurements
        WHERE device_id=?
          AND metric_id=?
          AND value_real IS NOT NULL
        ORDER BY ts_utc
        """,
        (device_id, metric_id),
    ).fetchall()

    parsed = [(parse_ts(ts), ts, float(value)) for ts, value in rows]
    return {
        "rows": parsed,
        "times": [x[0] for x in parsed],
    }


def nearest(series, target_ts):
    times = series["times"]
    rows = series["rows"]
    if not times:
        return None

    pos = bisect.bisect_left(times, target_ts)
    candidates = []
    if pos < len(rows):
        candidates.append(rows[pos])
    if pos > 0:
        candidates.append(rows[pos - 1])

    best = min(candidates, key=lambda row: abs(row[0] - target_ts))
    if abs(best[0] - target_ts) > MAX_MATCH_SECONDS:
        return None
    return best[2]


def main():
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()

        series = {
            "p1": load_series(cur, "grid_p1", "electrical_power_w"),
            "solaredge": load_series(cur, "pv_solaredge", "electrical_power_w"),
            "goodwe4200": load_series(cur, "pv_goodwe4200", "electrical_power_w"),
            "goodwe2000": load_series(cur, "pv_goodwe2000", "electrical_power_w"),
            "tesla": load_series(cur, "tesla", "electrical_power_w"),
            "boiler": load_series(cur, "boiler", "electrical_power_w"),
            "quatt": load_series(cur, "quatt_cic", "electrical_power_w"),
            "washer": load_series(cur, "washer", "active"),
            "dryer": load_series(cur, "dryer", "active"),
        }
    finally:
        con.close()

    out = []
    skipped = {
        "pv": 0,
        "tesla": 0,
        "boiler": 0,
        "quatt": 0,
        "washer": 0,
        "dryer": 0,
    }

    for t, ts, p1_w in series["p1"]["rows"]:
        solar_edge_w = nearest(series["solaredge"], t)
        goodwe4200_w = nearest(series["goodwe4200"], t)
        goodwe2000_w = nearest(series["goodwe2000"], t)
        tesla_w = nearest(series["tesla"], t)
        boiler_w = nearest(series["boiler"], t)
        quatt_w = nearest(series["quatt"], t)
        washer_active = nearest(series["washer"], t)
        dryer_active = nearest(series["dryer"], t)

        if solar_edge_w is None or goodwe4200_w is None or goodwe2000_w is None:
            skipped["pv"] += 1
            continue
        if tesla_w is None:
            skipped["tesla"] += 1
            continue
        if boiler_w is None:
            skipped["boiler"] += 1
            continue
        if quatt_w is None:
            skipped["quatt"] += 1
            continue
        if washer_active is None:
            skipped["washer"] += 1
            continue
        if dryer_active is None:
            skipped["dryer"] += 1
            continue

        pv_w = (
            max(0.0, solar_edge_w)
            + max(0.0, goodwe4200_w)
            + max(0.0, goodwe2000_w)
        )
        house_w = p1_w + pv_w
        tesla_w = max(0.0, tesla_w)
        boiler_w = max(0.0, boiler_w)
        quatt_w = max(0.0, quatt_w)

        clean_base = max(
            0.0,
            house_w - tesla_w - boiler_w - quatt_w,
        )

        out.append({
            "ts": ts,
            "p1W": round(p1_w),
            "pvW": round(pv_w),
            "teslaW": round(tesla_w),
            "boilerW": round(boiler_w),
            "quattActualW": round(quatt_w),
            "houseActualW": round(house_w),
            "cleanBaseW": round(clean_base),
            "washerActive": washer_active >= 0.5,
            "dryerActive": dryer_active >= 0.5,
        })

    if not out:
        raise SystemExit("FAIL: no fully matched SQLite clean-base samples")

    payload = {
        "schema": "EMS_PI_CLEAN_BASE_HISTORY_V0.2",
        "source": "local SQLite only",
        "control_writes": False,
        "match_tolerance_seconds": MAX_MATCH_SECONDS,
        "p1_samples": len(series["p1"]["rows"]),
        "sample_count": len(out),
        "skipped": skipped,
        "samples": out,
    }

    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    tmp.replace(OUTPUT)

    print("PASS: clean base history built from SQLite")
    print("P1 samples     :", payload["p1_samples"])
    print("clean samples  :", len(out))
    print("skipped        :", skipped)

    vals = [x["cleanBaseW"] for x in out]
    print("clean base min :", min(vals))
    print("clean base avg :", round(sum(vals) / len(vals), 1))
    print("clean base max :", max(vals))
    print("output         :", OUTPUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
OUTPUT = Path("/home/jeroen/ems/data/pv-history-profile.json")
TZ = ZoneInfo("Europe/Amsterdam")
LOOKBACK_DAYS = 30
MIN_DAY_PEAK_W = 2500
MIN_SAMPLES_PER_QUARTER = 3
UPPER_QUANTILE = 0.80

PV_KEYS = ("pv_solaredge", "pv_goodwe4200", "pv_goodwe2000")


def percentile(values, q):
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def main():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat().replace("+00:00", "Z")
    con = sqlite3.connect(DB)

    try:
        rows = con.execute(
            """
            SELECT
                x.slot_start_utc,
                d.device_key,
                x.value_avg,
                x.sample_count,
                x.quality
            FROM measurements_15m x
            JOIN devices d ON d.id=x.device_id
            JOIN metrics m ON m.id=x.metric_id
            WHERE m.metric_key='electrical_power_w'
              AND d.device_key IN ('pv_solaredge','pv_goodwe4200','pv_goodwe2000')
              AND x.slot_start_utc >= ?
              AND x.value_avg IS NOT NULL
            ORDER BY x.slot_start_utc
            """,
            (cutoff,),
        ).fetchall()
    finally:
        con.close()

    by_slot = defaultdict(dict)
    for ts, device_key, value_avg, sample_count, quality in rows:
        by_slot[ts][device_key] = max(0.0, float(value_avg))

    totals = []
    for ts, devices in by_slot.items():
        if all(k in devices for k in PV_KEYS):
            total = sum(devices[k] for k in PV_KEYS)
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TZ)
            totals.append((ts, dt.date().isoformat(), dt.hour * 4 + dt.minute // 15, total))

    day_peaks = defaultdict(float)
    for _, day, _, total in totals:
        day_peaks[day] = max(day_peaks[day], total)

    usable_days = {day for day, peak in day_peaks.items() if peak >= MIN_DAY_PEAK_W}

    bins = defaultdict(list)
    for _, day, quarter, total in totals:
        if day in usable_days:
            bins[quarter].append(total)

    profile = {}
    observed_bins = 0
    for q in range(96):
        vals = bins.get(q, [])
        if len(vals) >= MIN_SAMPLES_PER_QUARTER:
            envelope = percentile(vals, UPPER_QUANTILE)
            observed_bins += 1
            quality = "HISTORICAL_P80"
        elif vals:
            envelope = max(vals)
            quality = "HISTORICAL_MAX_LOW_SAMPLE"
        else:
            envelope = None
            quality = "NO_HISTORY"

        profile[str(q)] = {
            "clearEnvelopeW": None if envelope is None else round(envelope),
            "sampleCount": len(vals),
            "quality": quality,
        }

    payload = {
        "schema": "EMS_PI_PV_HISTORY_PROFILE_V0.1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "shadow",
        "control_writes": False,
        "method": "rolling historical clear-sky envelope by local quarter",
        "lookback_days": LOOKBACK_DAYS,
        "upper_quantile": UPPER_QUANTILE,
        "min_day_peak_w": MIN_DAY_PEAK_W,
        "min_samples_per_quarter": MIN_SAMPLES_PER_QUARTER,
        "usable_days": sorted(usable_days),
        "usable_day_count": len(usable_days),
        "observed_quarter_bins": observed_bins,
        "profile": profile,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    tmp.replace(OUTPUT)

    print("PASS: PV history profile built")
    print("usable days          :", len(usable_days))
    print("observed quarter bins:", observed_bins)
    print("output               :", OUTPUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import json
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HISTORY = Path("/home/jeroen/ems/data/clean-base-history.json")
OUTPUT = Path("/home/jeroen/ems/data/base-load-forecast-backtest.json")
TZ = ZoneInfo("Europe/Amsterdam")
CUTOFF = date(2025, 4, 1)
SEASON_WINDOW_DAYS = 28
MIN_DAYS = 2
MIN_SAMPLES = 2


def parse_local(ts):
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(TZ)


def circular_day_distance(a, b):
    anchor = 2000
    da = date(anchor, a.month, a.day).timetuple().tm_yday
    db = date(anchor, b.month, b.day).timetuple().tm_yday
    diff = abs(da - db)
    return min(diff, 366 - diff)


def weekend(dt):
    return dt.weekday() >= 5


def median(rows):
    if len(rows) < MIN_SAMPLES:
        return None
    return statistics.median(x["value"] for x in rows)


def days(rows):
    return len({x["dt"].date() for x in rows})


raw = json.loads(HISTORY.read_text())
rows = []
for s in raw.get("samples", []):
    b = s.get("cleanBaseW")
    if s.get("quattActualW") is None or b is None:
        continue
    if s.get("washerActive") is True or s.get("dryerActive") is True:
        continue
    if b >= 1500 or not s.get("ts"):
        continue
    dt = parse_local(s["ts"])
    if dt.date() < CUTOFF:
        continue
    rows.append({"dt": dt, "quarter": dt.hour * 4 + dt.minute // 15, "value": float(b)})

by_day = defaultdict(list)
for x in rows:
    by_day[x["dt"].date()].append(x)

results = []
for target_day in sorted(by_day):
    actual_rows = by_day[target_day]
    # Strict walk-forward: only data before the held-out day may train either model.
    train = [x for x in rows if x["dt"].date() < target_day]
    if not train:
        continue
    bins = defaultdict(list)
    for x in train:
        bins[x["quarter"]].append(x)
    global_med = statistics.median(x["value"] for x in train)

    errors_old = []
    errors_new = []
    signed_old = []
    signed_new = []
    actual_wh = old_wh = new_wh = 0.0
    quality = defaultdict(int)
    compared = 0

    # Evaluate only quarters for which this day has a usable observation.
    for actual in actual_rows:
        q = actual["quarter"]
        target = actual["dt"]
        same_q = bins.get(q, [])

        old = median(same_q)
        if old is None:
            old = global_med

        seasonal = [x for x in same_q if circular_day_distance(x["dt"].date(), target_day) <= SEASON_WINDOW_DAYS]
        same_weekday = [x for x in seasonal if x["dt"].weekday() == target.weekday()]
        same_daytype = [x for x in seasonal if weekend(x["dt"]) == weekend(target)]

        new = None
        qual = None
        if days(same_weekday) >= MIN_DAYS:
            new = median(same_weekday)
            if new is not None:
                qual = "SAME_WEEKDAY_SEASON_MEDIAN"
        if new is None and days(same_daytype) >= MIN_DAYS:
            new = median(same_daytype)
            if new is not None:
                qual = "DAYTYPE_SEASON_MEDIAN"
        if new is None and days(seasonal) >= MIN_DAYS:
            new = median(seasonal)
            if new is not None:
                qual = "SEASON_MEDIAN"
        if new is None:
            new = median(same_q)
            if new is not None:
                qual = "QUARTER_MEDIAN_FALLBACK"
        if new is None:
            new = global_med
            qual = "GLOBAL_MEDIAN_FALLBACK"

        a = actual["value"]
        errors_old.append(abs(old - a))
        errors_new.append(abs(new - a))
        signed_old.append(old - a)
        signed_new.append(new - a)
        actual_wh += a * 0.25
        old_wh += old * 0.25
        new_wh += new * 0.25
        quality[qual] += 1
        compared += 1

    if compared:
        results.append({
            "date": target_day.isoformat(),
            "samples": compared,
            "old_mae_w": round(statistics.mean(errors_old), 1),
            "new_mae_w": round(statistics.mean(errors_new), 1),
            "old_bias_w": round(statistics.mean(signed_old), 1),
            "new_bias_w": round(statistics.mean(signed_new), 1),
            "actual_kwh": round(actual_wh / 1000, 3),
            "old_kwh": round(old_wh / 1000, 3),
            "new_kwh": round(new_wh / 1000, 3),
            "old_kwh_error": round((old_wh - actual_wh) / 1000, 3),
            "new_kwh_error": round((new_wh - actual_wh) / 1000, 3),
            "quality_counts": dict(quality),
        })

if not results:
    raise SystemExit("FAIL: insufficient history for backtest")

weighted_n = sum(r["samples"] for r in results)
old_mae = sum(r["old_mae_w"] * r["samples"] for r in results) / weighted_n
new_mae = sum(r["new_mae_w"] * r["samples"] for r in results) / weighted_n
old_abs_kwh = statistics.mean(abs(r["old_kwh_error"]) for r in results)
new_abs_kwh = statistics.mean(abs(r["new_kwh_error"]) for r in results)
wins = sum(r["new_mae_w"] < r["old_mae_w"] for r in results)
ties = sum(r["new_mae_w"] == r["old_mae_w"] for r in results)

summary = {
    "schema": "EMS_PI_BASE_LOAD_BACKTEST_V0.1",
    "mode": "diagnostic",
    "walk_forward": True,
    "days_tested": len(results),
    "samples_tested": weighted_n,
    "old_weighted_mae_w": round(old_mae, 1),
    "new_weighted_mae_w": round(new_mae, 1),
    "mae_improvement_w": round(old_mae - new_mae, 1),
    "mae_improvement_pct": round((old_mae - new_mae) / old_mae * 100, 1) if old_mae else 0,
    "old_mean_abs_daily_kwh_error": round(old_abs_kwh, 3),
    "new_mean_abs_daily_kwh_error": round(new_abs_kwh, 3),
    "new_model_wins": wins,
    "ties": ties,
    "old_model_wins": len(results) - wins - ties,
    "days": results,
}

OUTPUT.write_text(json.dumps(summary, indent=2) + "\n")
print("PASS: base-load walk-forward backtest built")
print("days tested                    :", summary["days_tested"])
print("samples tested                 :", summary["samples_tested"])
print("old weighted MAE W             :", summary["old_weighted_mae_w"])
print("new weighted MAE W             :", summary["new_weighted_mae_w"])
print("MAE improvement W              :", summary["mae_improvement_w"])
print("MAE improvement %              :", summary["mae_improvement_pct"])
print("old mean abs daily kWh error   :", summary["old_mean_abs_daily_kwh_error"])
print("new mean abs daily kWh error   :", summary["new_mean_abs_daily_kwh_error"])
print("new / ties / old wins          :", summary["new_model_wins"], "/", summary["ties"], "/", summary["old_model_wins"])
print()
print("per day:")
for r in results:
    print(r["date"], f'n={r["samples"]:3d}', f'old={r["old_mae_w"]:6.1f}W', f'new={r["new_mae_w"]:6.1f}W', f'delta={r["new_mae_w"]-r["old_mae_w"]:+6.1f}W', r["quality_counts"])
print("output                         :", OUTPUT)

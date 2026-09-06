#!/usr/bin/env python3

import json
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HISTORY = Path("/home/jeroen/ems/data/clean-base-history.json")
PV_FORECAST = Path("/home/jeroen/ems/data/pv-forecast.json")
OUTPUT = Path("/home/jeroen/ems/data/base-load-forecast.json")

TZ = ZoneInfo("Europe/Amsterdam")
HISTORY_CUTOFF_LOCAL = date(2025, 4, 1)
SEASON_WINDOW_DAYS = 28
MIN_SAME_WEEKDAY_DAYS = 2
MIN_DAYTYPE_DAYS = 2
MIN_SEASON_DAYS = 2
MIN_QUARTER_SAMPLES = 2


def parse_local(ts):
    return datetime.fromisoformat(
        str(ts).replace("Z", "+00:00")
    ).astimezone(TZ)


def circular_day_distance(a, b):
    # Compare calendar position independent of year. Leap day differences are
    # immaterial for the deliberately broad +/- 4 week seasonal window.
    anchor_year = 2000
    da = date(anchor_year, a.month, a.day).timetuple().tm_yday
    db = date(anchor_year, b.month, b.day).timetuple().tm_yday
    diff = abs(da - db)
    return min(diff, 366 - diff)


def is_weekend(dt):
    return dt.weekday() >= 5


def median_candidate(rows):
    if len(rows) < MIN_QUARTER_SAMPLES:
        return None
    return statistics.median(x["value"] for x in rows)


def distinct_days(rows):
    return len({x["dt"].date() for x in rows})


hist = json.loads(HISTORY.read_text())
pv = json.loads(PV_FORECAST.read_text())

usable = []
for s in hist.get("samples", []):
    b = s.get("cleanBaseW")

    if s.get("quattActualW") is None:
        continue
    if b is None:
        continue
    if s.get("washerActive") is True:
        continue
    if s.get("dryerActive") is True:
        continue
    if b >= 1500:
        continue
    if not s.get("ts"):
        continue

    dt = parse_local(s["ts"])
    if dt.date() < HISTORY_CUTOFF_LOCAL:
        continue

    usable.append({
        "dt": dt,
        "quarter": dt.hour * 4 + dt.minute // 15,
        "value": float(b),
    })

if not usable:
    raise SystemExit("FAIL: no usable clean-base samples")

global_median = statistics.median(x["value"] for x in usable)

quarter_bins = defaultdict(list)
for x in usable:
    quarter_bins[x["quarter"]].append(x)

quarter_medians = {
    q: statistics.median(x["value"] for x in rows)
    for q, rows in quarter_bins.items()
    if len(rows) >= MIN_QUARTER_SAMPLES
}

pv_slots = pv.get("slots", [])
if len(pv_slots) != 96:
    raise SystemExit(
        f"FAIL: expected 96 PV slots, got {len(pv_slots)}"
    )

out = []
quality_counts = defaultdict(int)

for slot in pv_slots:
    ts = (
        slot.get("slot_start_utc")
        or slot.get("start")
        or slot.get("startAt")
    )

    if not ts:
        raise SystemExit("FAIL: PV slot timestamp missing")

    target = parse_local(ts)
    quarter = target.hour * 4 + target.minute // 15

    # Never train a future slot with samples at/after the slot itself.
    same_quarter = [
        x for x in quarter_bins.get(quarter, [])
        if x["dt"] < target
    ]

    seasonal = [
        x for x in same_quarter
        if circular_day_distance(x["dt"].date(), target.date())
        <= SEASON_WINDOW_DAYS
    ]

    same_weekday = [
        x for x in seasonal
        if x["dt"].weekday() == target.weekday()
    ]

    same_daytype = [
        x for x in seasonal
        if is_weekend(x["dt"]) == is_weekend(target)
    ]

    value = None
    quality = None
    chosen = []

    if distinct_days(same_weekday) >= MIN_SAME_WEEKDAY_DAYS:
        value = median_candidate(same_weekday)
        if value is not None:
            quality = "SAME_WEEKDAY_SEASON_MEDIAN"
            chosen = same_weekday

    if value is None and distinct_days(same_daytype) >= MIN_DAYTYPE_DAYS:
        value = median_candidate(same_daytype)
        if value is not None:
            quality = "DAYTYPE_SEASON_MEDIAN"
            chosen = same_daytype

    if value is None and distinct_days(seasonal) >= MIN_SEASON_DAYS:
        value = median_candidate(seasonal)
        if value is not None:
            quality = "SEASON_MEDIAN"
            chosen = seasonal

    if value is None:
        historical_quarter = [x for x in same_quarter]
        value = median_candidate(historical_quarter)
        if value is not None:
            quality = "QUARTER_MEDIAN_FALLBACK"
            chosen = historical_quarter

    if value is None:
        value = global_median
        quality = "GLOBAL_MEDIAN_FALLBACK"
        chosen = []

    quality_counts[quality] += 1

    out.append({
        "slot_start_utc": ts,
        "localQuarter": quarter,
        "baseLoadForecastW": round(value),
        "forecastQuality": quality,
        "historicalSampleCount": len(chosen),
        "historicalDayCount": distinct_days(chosen),
        "seasonWindowDays": SEASON_WINDOW_DAYS,
    })

payload = {
    "schema": "EMS_PI_BASE_LOAD_FORECAST_V0.2",
    "mode": "shadow",
    "control_writes": False,
    "quatt_removed_from_baseline": True,
    "source": "clean-base-history",
    "history_cutoff_local": HISTORY_CUTOFF_LOCAL.isoformat(),
    "season_window_days": SEASON_WINDOW_DAYS,
    "usable_history_samples": len(usable),
    "observed_quarter_bins": len(quarter_medians),
    "global_median_w": round(global_median, 1),
    "slot_count": len(out),
    "quality_counts": dict(quality_counts),
    "slots": out,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(
    json.dumps(payload, separators=(",", ":")) + "\n"
)
tmp.replace(OUTPUT)

print("PASS: seasonal base-load forecast built")
print("slots               :", len(out))
print("usable history      :", len(usable))
print("observed quarter bins:", len(quarter_medians))
print("global median W     :", round(global_median, 1))
print("season window days  :", SEASON_WINDOW_DAYS)
print("quality counts      :", dict(quality_counts))
print("output              :", OUTPUT)

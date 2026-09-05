#!/usr/bin/env python3

import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HISTORY = Path("/home/jeroen/ems/data/clean-base-history.json")
PV_FORECAST = Path("/home/jeroen/ems/data/pv-forecast.json")
OUTPUT = Path("/home/jeroen/ems/data/base-load-forecast.json")

TZ = ZoneInfo("Europe/Amsterdam")

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

    usable.append(s)

if not usable:
    raise SystemExit("FAIL: no usable clean-base samples")

global_median = statistics.median(
    float(s["cleanBaseW"]) for s in usable
)

bins = defaultdict(list)

for s in usable:
    dt = datetime.fromisoformat(
        s["ts"].replace("Z", "+00:00")
    ).astimezone(TZ)

    quarter = dt.hour * 4 + dt.minute // 15
    bins[quarter].append(float(s["cleanBaseW"]))

quarter_medians = {
    q: statistics.median(vals)
    for q, vals in bins.items()
    if len(vals) >= 2
}

pv_slots = pv.get("slots", [])
if len(pv_slots) != 96:
    raise SystemExit(
        f"FAIL: expected 96 PV slots, got {len(pv_slots)}"
    )

out = []

for slot in pv_slots:
    ts = (
        slot.get("slot_start_utc")
        or slot.get("start")
        or slot.get("startAt")
    )

    if not ts:
        raise SystemExit("FAIL: PV slot timestamp missing")

    dt = datetime.fromisoformat(
        ts.replace("Z", "+00:00")
    ).astimezone(TZ)

    quarter = dt.hour * 4 + dt.minute // 15

    if quarter in quarter_medians:
        value = quarter_medians[quarter]
        quality = "OBSERVED_QUARTER_MEDIAN"
        sample_count = len(bins[quarter])
    else:
        value = global_median
        quality = "GLOBAL_MEDIAN_FALLBACK"
        sample_count = 0

    out.append({
        "slot_start_utc": ts,
        "localQuarter": quarter,
        "baseLoadForecastW": round(value),
        "forecastQuality": quality,
        "historicalSampleCount": sample_count,
    })

payload = {
    "schema": "EMS_PI_BASE_LOAD_FORECAST_V0.1",
    "mode": "shadow",
    "control_writes": False,
    "quatt_removed_from_baseline": True,
    "source": "clean-base-history",
    "usable_history_samples": len(usable),
    "observed_quarter_bins": len(quarter_medians),
    "global_median_w": round(global_median, 1),
    "slot_count": len(out),
    "slots": out,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(
    json.dumps(payload, separators=(",", ":")) + "\n"
)
tmp.replace(OUTPUT)

observed = sum(
    x["forecastQuality"] == "OBSERVED_QUARTER_MEDIAN"
    for x in out
)

print("PASS: base-load forecast built")
print("slots               :", len(out))
print("usable history      :", len(usable))
print("observed quarter bins:", len(quarter_medians))
print("global median W     :", round(global_median, 1))
print("forecast observed   :", observed)
print("forecast fallback   :", len(out) - observed)
print("output              :", OUTPUT)

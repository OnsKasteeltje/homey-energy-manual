#!/usr/bin/env python3

import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HISTORY = Path("/home/jeroen/ems/data/clean-base-history.json")
CURRENT = Path("/home/jeroen/ems/data/base-load-forecast.json")
OUTPUT = Path("/home/jeroen/ems/data/base-load-forecast-ab.json")
TZ = ZoneInfo("Europe/Amsterdam")


def parse_local(ts):
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(TZ)


hist = json.loads(HISTORY.read_text())
cur = json.loads(CURRENT.read_text())

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
    usable.append({
        "dt": dt,
        "quarter": dt.hour * 4 + dt.minute // 15,
        "value": float(b),
    })

if not usable:
    raise SystemExit("FAIL: no usable clean-base samples")

bins = defaultdict(list)
for x in usable:
    bins[x["quarter"]].append(x)

global_median = statistics.median(x["value"] for x in usable)

rows = []
for slot in cur.get("slots", []):
    ts = slot["slot_start_utc"]
    target = parse_local(ts)
    q = target.hour * 4 + target.minute // 15

    # Reproduce the original V0.1 method, but avoid using samples from the
    # future relative to the forecast slot.
    old_rows = [x for x in bins.get(q, []) if x["dt"] < target]
    if len(old_rows) >= 2:
        old_value = statistics.median(x["value"] for x in old_rows)
        old_quality = "OBSERVED_QUARTER_MEDIAN"
        old_count = len(old_rows)
    else:
        old_value = global_median
        old_quality = "GLOBAL_MEDIAN_FALLBACK"
        old_count = 0

    new_value = float(slot["baseLoadForecastW"])
    delta = new_value - old_value

    rows.append({
        "slot_start_utc": ts,
        "local": target.strftime("%Y-%m-%d %H:%M"),
        "oldV01W": round(old_value),
        "newV02W": round(new_value),
        "deltaW": round(delta),
        "absDeltaW": round(abs(delta)),
        "oldQuality": old_quality,
        "oldHistoricalSampleCount": old_count,
        "newQuality": slot.get("forecastQuality"),
        "newHistoricalSampleCount": slot.get("historicalSampleCount", 0),
        "newHistoricalDayCount": slot.get("historicalDayCount", 0),
    })

if not rows:
    raise SystemExit("FAIL: no forecast slots")

abs_diffs = [r["absDeltaW"] for r in rows]
deltas = [r["deltaW"] for r in rows]
old_energy_kwh = sum(r["oldV01W"] for r in rows) * 0.25 / 1000.0
new_energy_kwh = sum(r["newV02W"] for r in rows) * 0.25 / 1000.0

summary = {
    "slots": len(rows),
    "mean_abs_delta_w": round(statistics.mean(abs_diffs), 1),
    "median_abs_delta_w": round(statistics.median(abs_diffs), 1),
    "max_abs_delta_w": max(abs_diffs),
    "mean_signed_delta_w": round(statistics.mean(deltas), 1),
    "old_24h_energy_kwh": round(old_energy_kwh, 3),
    "new_24h_energy_kwh": round(new_energy_kwh, 3),
    "energy_delta_kwh": round(new_energy_kwh - old_energy_kwh, 3),
}

payload = {
    "schema": "EMS_PI_BASE_LOAD_FORECAST_AB_V0.1",
    "old": "generic quarter median (V0.1 method)",
    "new": cur.get("schema"),
    "summary": summary,
    "slots": rows,
}

OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")

print("PASS: base-load A/B comparison built")
for k, v in summary.items():
    print(f"{k:24}: {v}")

print("\nlargest differences:")
for r in sorted(rows, key=lambda x: x["absDeltaW"], reverse=True)[:12]:
    print(
        r["local"],
        f'old={r["oldV01W"]:4d}W',
        f'new={r["newV02W"]:4d}W',
        f'delta={r["deltaW"]:+4d}W',
        r["newQuality"],
    )

print("\noutput                  :", OUTPUT)

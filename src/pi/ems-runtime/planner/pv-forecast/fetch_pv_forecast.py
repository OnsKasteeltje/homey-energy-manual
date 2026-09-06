#!/usr/bin/env python3

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LAT = 52.70808
LON = 5.10003

PV_NOMINAL_W = 8000
PV_SCALE_W_PER_WM2 = PV_NOMINAL_W / 1000

OUTPUT = Path("/home/jeroen/ems/data/pv-forecast.json")
AXIS = Path("/home/jeroen/ems/data/planner-axis.json")

params = {
    "latitude": LAT,
    "longitude": LON,
    "minutely_15": "shortwave_radiation",
    "past_minutely_15": 96,
    "forecast_minutely_15": 104,
    "timezone": "UTC",
}

url = (
    "https://api.open-meteo.com/v1/forecast?"
    + urllib.parse.urlencode(params)
)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "ems-pi-pv-forecast/0.1"},
)

with urllib.request.urlopen(request, timeout=20) as response:
    weather = json.load(response)

quarter = weather.get("minutely_15", {})
times = quarter.get("time", [])
radiation = quarter.get("shortwave_radiation", [])

if not times or len(times) != len(radiation):
    raise RuntimeError("Invalid Open-Meteo 15-minute response")

with AXIS.open() as f:
    axis = json.load(f)

axis_slots = axis.get("slots", [])
if len(axis_slots) != 96:
    raise RuntimeError(
        f"Invalid planner axis: expected 96 slots, got {len(axis_slots)}"
    )

axis_set = set(axis_slots)

slots = []

for ts, irr in zip(times, radiation):
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    start = dt.isoformat().replace("+00:00", "Z")

    if start not in axis_set:
        continue

    if len(slots) >= 96:
        break

    irr = max(0.0, float(irr))
    pv_w = min(
        PV_NOMINAL_W,
        irr * PV_SCALE_W_PER_WM2
    )

    slots.append({
        "start": dt.isoformat().replace("+00:00", "Z"),
        "shortwave_radiation_w_m2": round(irr, 2),
        "pv_forecast_w": round(pv_w)
    })

if len(slots) < 96:
    raise RuntimeError(
        f"Insufficient future slots: {len(slots)}"
    )

document = {
    "schema": "EMS_PI_PV_FORECAST_V0.1",
    "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    "mode": "shadow",
    "control_writes": False,
    "source": "open-meteo",
    "location": {
        "name": "Hauwert",
        "latitude": LAT,
        "longitude": LON
    },
    "model": {
        "pv_nominal_w": PV_NOMINAL_W,
        "scale_w_per_wm2": PV_SCALE_W_PER_WM2,
        "calibration": "NONE_THEORETICAL_SCALE"
    },
    "slot_count": len(slots),
    "slots": slots
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

tmp = OUTPUT.with_suffix(".tmp")

with tmp.open("w") as f:
    json.dump(document, f, indent=2)

tmp.replace(OUTPUT)

print(
    f"PASS: wrote {len(slots)} slots to {OUTPUT}"
)

#!/usr/bin/env python3

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LAT = 52.70808
LON = 5.10003
TZ = ZoneInfo("Europe/Amsterdam")

PV_NOMINAL_W = 8000
PV_SCALE_W_PER_WM2 = PV_NOMINAL_W / 1000
MIN_PROFILE_DAYS = 3
MIN_PROFILE_SAMPLES = 3
HISTORICAL_WEIGHT = 0.85

OUTPUT = Path("/home/jeroen/ems/data/pv-forecast.json")
AXIS = Path("/home/jeroen/ems/data/planner-axis.json")
PROFILE = Path("/home/jeroen/ems/data/pv-history-profile.json")

params = {
    "latitude": LAT,
    "longitude": LON,
    "minutely_15": "shortwave_radiation,shortwave_radiation_clear_sky",
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
    headers={"User-Agent": "ems-pi-pv-forecast/0.2"},
)

with urllib.request.urlopen(request, timeout=20) as response:
    weather = json.load(response)

quarter = weather.get("minutely_15", {})
times = quarter.get("time", [])
radiation = quarter.get("shortwave_radiation", [])
clear_sky = quarter.get("shortwave_radiation_clear_sky", [])

if (
    not times
    or len(times) != len(radiation)
    or len(times) != len(clear_sky)
):
    raise RuntimeError("Invalid Open-Meteo 15-minute response")

with AXIS.open() as f:
    axis = json.load(f)

axis_slots = axis.get("slots", [])
if len(axis_slots) != 96:
    raise RuntimeError(
        f"Invalid planner axis: expected 96 slots, got {len(axis_slots)}"
    )

axis_set = set(axis_slots)

profile = None
if PROFILE.exists():
    try:
        candidate = json.loads(PROFILE.read_text())
        if candidate.get("schema") == "EMS_PI_PV_HISTORY_PROFILE_V0.1":
            profile = candidate
    except Exception:
        profile = None

usable_days = int((profile or {}).get("usable_day_count") or 0)
profile_bins = (profile or {}).get("profile") or {}

slots = []
historical_slots = 0
fallback_slots = 0

for ts, irr, clear in zip(times, radiation, clear_sky):
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    start = dt.isoformat().replace("+00:00", "Z")

    if start not in axis_set:
        continue

    if len(slots) >= 96:
        break

    irr = max(0.0, float(irr or 0))
    clear = max(0.0, float(clear or 0))

    theoretical_w = min(PV_NOMINAL_W, irr * PV_SCALE_W_PER_WM2)

    local = dt.astimezone(TZ)
    local_quarter = local.hour * 4 + local.minute // 15
    hist = profile_bins.get(str(local_quarter)) or {}
    envelope = hist.get("clearEnvelopeW")
    sample_count = int(hist.get("sampleCount") or 0)

    use_history = (
        usable_days >= MIN_PROFILE_DAYS
        and sample_count >= MIN_PROFILE_SAMPLES
        and envelope is not None
        and clear >= 25
    )

    if use_history:
        cloud_factor = min(1.10, max(0.0, irr / clear))
        historical_w = max(0.0, float(envelope) * cloud_factor)
        pv_w = (
            HISTORICAL_WEIGHT * historical_w
            + (1.0 - HISTORICAL_WEIGHT) * theoretical_w
        )
        pv_w = min(PV_NOMINAL_W, pv_w)
        model = "HISTORICAL_ENVELOPE_CLOUD_ADJUSTED"
        historical_slots += 1
    else:
        cloud_factor = None
        historical_w = None
        pv_w = theoretical_w
        model = "THEORETICAL_FALLBACK"
        fallback_slots += 1

    slots.append({
        "start": start,
        "shortwave_radiation_w_m2": round(irr, 2),
        "shortwave_radiation_clear_sky_w_m2": round(clear, 2),
        "local_quarter": local_quarter,
        "pv_forecast_w": round(pv_w),
        "forecast_model": model,
        "historical_clear_envelope_w": (
            None if envelope is None else round(float(envelope))
        ),
        "historical_sample_count": sample_count,
        "cloud_factor": (
            None if cloud_factor is None else round(cloud_factor, 3)
        ),
    })

if len(slots) < 96:
    raise RuntimeError(
        f"Insufficient future slots: {len(slots)}"
    )

document = {
    "schema": "EMS_PI_PV_FORECAST_V0.2",
    "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    "mode": "shadow",
    "control_writes": False,
    "source": "open-meteo+ems-history",
    "location": {
        "name": "Hauwert",
        "latitude": LAT,
        "longitude": LON
    },
    "model": {
        "pv_nominal_w": PV_NOMINAL_W,
        "fallback_scale_w_per_wm2": PV_SCALE_W_PER_WM2,
        "calibration": "ROLLING_HISTORICAL_CLEAR_ENVELOPE",
        "historical_weight": HISTORICAL_WEIGHT,
        "min_profile_days": MIN_PROFILE_DAYS,
        "profile_usable_days": usable_days,
        "historical_slots": historical_slots,
        "fallback_slots": fallback_slots,
    },
    "slot_count": len(slots),
    "slots": slots
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

tmp = OUTPUT.with_suffix(".tmp")

with tmp.open("w") as f:
    json.dump(document, f, indent=2)

tmp.replace(OUTPUT)

print(f"PASS: wrote {len(slots)} slots to {OUTPUT}")
print("profile usable days :", usable_days)
print("historical slots    :", historical_slots)
print("fallback slots      :", fallback_slots)

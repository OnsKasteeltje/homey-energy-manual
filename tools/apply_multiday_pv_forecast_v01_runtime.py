#!/usr/bin/env python3
from pathlib import Path
import shutil

TARGET_DIR = Path('/home/jeroen/ems/runtime/planner/pv-forecast')
TARGET = TARGET_DIR / 'fetch_multiday_pv_forecast.py'
SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
BACKUP = Path('/etc/systemd/system/ems-pv-forecast.service.pre-multiday-v01')

SCRIPT = r'''#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from collections import defaultdict
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
FORECAST_DAYS = 7

OUTPUT = Path("/home/jeroen/ems/data/pv-forecast-multiday.json")
PROFILE = Path("/home/jeroen/ems/data/pv-history-profile.json")

params = {
    "latitude": LAT,
    "longitude": LON,
    "minutely_15": "shortwave_radiation,shortwave_radiation_clear_sky",
    "forecast_days": FORECAST_DAYS,
    "timezone": "UTC",
}
url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
request = urllib.request.Request(url, headers={"User-Agent": "ems-pi-pv-multiday/0.1"})
with urllib.request.urlopen(request, timeout=20) as response:
    weather = json.load(response)

quarter = weather.get("minutely_15", {})
times = quarter.get("time", [])
radiation = quarter.get("shortwave_radiation", [])
clear_sky = quarter.get("shortwave_radiation_clear_sky", [])
if not times or len(times) != len(radiation) or len(times) != len(clear_sky):
    raise RuntimeError("Invalid Open-Meteo 15-minute response")

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

now = datetime.now(timezone.utc)
slots = []
historical_slots = 0
fallback_slots = 0

for ts, irr, clear in zip(times, radiation, clear_sky):
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    if dt < now.replace(second=0, microsecond=0):
        continue
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
        pv_w = HISTORICAL_WEIGHT * historical_w + (1.0 - HISTORICAL_WEIGHT) * theoretical_w
        pv_w = min(PV_NOMINAL_W, pv_w)
        model = "HISTORICAL_ENVELOPE_CLOUD_ADJUSTED"
        historical_slots += 1
    else:
        cloud_factor = None
        pv_w = theoretical_w
        model = "THEORETICAL_FALLBACK"
        fallback_slots += 1

    horizon_hours = max(0.0, (dt - now).total_seconds() / 3600.0)
    if horizon_hours <= 24:
        horizon_class = "NEAR_0_24H"
    elif horizon_hours <= 72:
        horizon_class = "MID_24_72H"
    else:
        horizon_class = "LONG_72H_PLUS"

    slots.append({
        "start": dt.isoformat().replace("+00:00", "Z"),
        "localDate": local.date().isoformat(),
        "localQuarter": local_quarter,
        "horizonHours": round(horizon_hours, 2),
        "horizonClass": horizon_class,
        "shortwaveRadiationWm2": round(irr, 2),
        "shortwaveRadiationClearSkyWm2": round(clear, 2),
        "pvForecastW": round(pv_w),
        "forecastModel": model,
        "historicalClearEnvelopeW": None if envelope is None else round(float(envelope)),
        "historicalSampleCount": sample_count,
        "cloudFactor": None if cloud_factor is None else round(cloud_factor, 3),
    })

if len(slots) < 96:
    raise RuntimeError(f"Insufficient multi-day future slots: {len(slots)}")

by_day = defaultdict(list)
for slot in slots:
    by_day[slot["localDate"]].append(slot)

daily = []
for local_date in sorted(by_day):
    ds = by_day[local_date]
    pv_kwh = sum(float(s["pvForecastW"]) * 0.25 / 1000.0 for s in ds)
    daylight = [s for s in ds if float(s["pvForecastW"]) > 0]
    classes = sorted(set(s["horizonClass"] for s in ds))
    daily.append({
        "localDate": local_date,
        "slotCount": len(ds),
        "pvForecastKWh": round(pv_kwh, 3),
        "daylightSlotCount": len(daylight),
        "peakPvForecastW": max((int(s["pvForecastW"]) for s in ds), default=0),
        "horizonClasses": classes,
        "historicalModelShare": round(sum(1 for s in ds if s["forecastModel"] == "HISTORICAL_ENVELOPE_CLOUD_ADJUSTED") / len(ds), 3),
    })

document = {
    "schema": "EMS_PI_PV_FORECAST_MULTIDAY_V0.1",
    "generatedAt": now.isoformat().replace("+00:00", "Z"),
    "mode": "shadow",
    "readOnly": True,
    "controlWrites": False,
    "source": "open-meteo+ems-history",
    "purpose": "GENERIC_MULTI_DAY_PV_FORECAST",
    "location": {"name": "Hauwert", "latitude": LAT, "longitude": LON},
    "model": {
        "pvNominalW": PV_NOMINAL_W,
        "fallbackScaleWPerWm2": PV_SCALE_W_PER_WM2,
        "calibration": "ROLLING_HISTORICAL_CLEAR_ENVELOPE",
        "historicalWeight": HISTORICAL_WEIGHT,
        "profileUsableDays": usable_days,
        "forecastDaysRequested": FORECAST_DAYS,
        "historicalSlots": historical_slots,
        "fallbackSlots": fallback_slots,
        "uncertaintyPolicy": "HORIZON_CLASS_ONLY_NO_NUMERIC_CONFIDENCE_YET"
    },
    "slotCount": len(slots),
    "daily": daily,
    "slots": slots,
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUTPUT.with_suffix('.tmp')
with tmp.open('w') as f:
    json.dump(document, f, indent=2)
tmp.replace(OUTPUT)
print(f"PASS: generic multi-day PV forecast built: {len(slots)} slots / {len(daily)} local days")
for d in daily:
    print(f"{d['localDate']} pv={d['pvForecastKWh']:.3f} kWh peak={d['peakPvForecastW']} W classes={','.join(d['horizonClasses'])}")
print("output:", OUTPUT)
'''

TARGET_DIR.mkdir(parents=True, exist_ok=True)
TARGET.write_text(SCRIPT)
TARGET.chmod(0o755)

if not SERVICE.exists():
    raise SystemExit(f"FAIL: missing service file {SERVICE}")
service = SERVICE.read_text()
needle = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/pv-forecast/fetch_pv_forecast.py\n'
line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/pv-forecast/fetch_multiday_pv_forecast.py\n'
if line not in service:
    if needle not in service:
        raise SystemExit('FAIL: could not find 24h PV forecast ExecStart anchor in service')
    if not BACKUP.exists():
        shutil.copy2(SERVICE, BACKUP)
    service = service.replace(needle, needle + line, 1)
    Path('/tmp/ems-pv-forecast.service.multiday-v01').write_text(service)
    print('STAGED_SERVICE=/tmp/ems-pv-forecast.service.multiday-v01')
else:
    print('SERVICE_ALREADY_CONTAINS_MULTIDAY=1')

print('PASS: generic multi-day PV runtime source installed')
print('target :', TARGET)
print('output : /home/jeroen/ems/data/pv-forecast-multiday.json')
print('NOTE: if STAGED_SERVICE is shown, install it with sudo cp + daemon-reload')

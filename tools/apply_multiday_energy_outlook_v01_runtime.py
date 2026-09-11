#!/usr/bin/env python3
from pathlib import Path
import json

PV_SCRIPT = Path('/home/jeroen/ems/runtime/planner/pv-forecast/fetch_multiday_pv_forecast.py')
OUTLOOK_DIR = Path('/home/jeroen/ems/runtime/planner/energy-outlook')
OUTLOOK_SCRIPT = OUTLOOK_DIR / 'build_multiday_energy_outlook.py'
SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED_SERVICE = Path('/tmp/ems-pv-forecast.service.energy-outlook-v01')

if not PV_SCRIPT.exists():
    raise SystemExit(f'FAIL: missing {PV_SCRIPT}')

pv_text = PV_SCRIPT.read_text()
old = '''    daily.append({\n        "localDate": local_date,\n        "slotCount": len(ds),\n        "pvForecastKWh": round(pv_kwh, 3),\n        "daylightSlotCount": len(daylight),\n        "peakPvForecastW": max((int(s["pvForecastW"]) for s in ds), default=0),\n        "horizonClasses": classes,\n        "historicalModelShare": round(sum(1 for s in ds if s["forecastModel"] == "HISTORICAL_ENVELOPE_CLOUD_ADJUSTED") / len(ds), 3),\n    })\n'''
new = '''    first_local = datetime.fromisoformat(ds[0]["start"].replace("Z", "+00:00")).astimezone(TZ)\n    last_local = datetime.fromisoformat(ds[-1]["start"].replace("Z", "+00:00")).astimezone(TZ)\n    coverage_minutes = len(ds) * 15\n    full_day_minutes = 24 * 60\n    coverage_fraction = min(1.0, coverage_minutes / full_day_minutes)\n    # A complete local day has all 96 quarter-hours represented. DST edge-cases are\n    # intentionally not normalized here; the explicit coverage metadata remains authoritative.\n    is_complete_day = len(ds) == 96 and first_local.hour == 0 and first_local.minute == 0\n    is_partial_day = not is_complete_day\n    daily.append({\n        "localDate": local_date,\n        "slotCount": len(ds),\n        "coverageMinutes": coverage_minutes,\n        "coverageFraction": round(coverage_fraction, 4),\n        "isCompleteDay": is_complete_day,\n        "isPartialDay": is_partial_day,\n        "firstCoveredLocal": first_local.isoformat(),\n        "lastCoveredLocal": last_local.isoformat(),\n        "pvForecastKWh": round(pv_kwh, 3),\n        "daylightSlotCount": len(daylight),\n        "peakPvForecastW": max((int(s["pvForecastW"]) for s in ds), default=0),\n        "horizonClasses": classes,\n        "historicalModelShare": round(sum(1 for s in ds if s["forecastModel"] == "HISTORICAL_ENVELOPE_CLOUD_ADJUSTED") / len(ds), 3),\n    })\n'''
if old in pv_text:
    pv_text = pv_text.replace(old, new, 1)
    pv_text = pv_text.replace('"schema": "EMS_PI_PV_FORECAST_MULTIDAY_V0.1"', '"schema": "EMS_PI_PV_FORECAST_MULTIDAY_V0.2"')
    PV_SCRIPT.write_text(pv_text)
    print('PATCHED_MULTI_DAY_PV=1')
elif '"coverageMinutes"' in pv_text and 'EMS_PI_PV_FORECAST_MULTIDAY_V0.2' in pv_text:
    print('MULTI_DAY_PV_ALREADY_PATCHED=1')
else:
    raise SystemExit('FAIL: expected multi-day PV daily block not found; refusing unsafe patch')

OUTLOOK_DIR.mkdir(parents=True, exist_ok=True)
outlook = r'''#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PV = Path('/home/jeroen/ems/data/pv-forecast-multiday.json')
BASE = Path('/home/jeroen/ems/data/base-load-forecast.json')
WW = Path('/home/jeroen/ems/data/ww-plan.json')
OUTPUT = Path('/home/jeroen/ems/data/multiday-energy-outlook.json')

if not PV.exists():
    raise SystemExit(f'FAIL: missing {PV}')
pv = json.loads(PV.read_text())
base = json.loads(BASE.read_text()) if BASE.exists() else {}
ww = json.loads(WW.read_text()) if WW.exists() else {}

# Build timestamp keyed maps only from data that actually exists. We do not extrapolate
# the 24h base-load or WW plans beyond their published horizon.
def first_list(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, list):
            return v
    return []

base_slots = first_list(base, ['slots', 'forecast', 'quarterHours'])
ww_slots = first_list(ww, ['slots', 'plan', 'quarterHours'])

def ts_of(s):
    return s.get('start') or s.get('timestamp') or s.get('startUtc')

def num(s, keys):
    for k in keys:
        if k in s and s[k] is not None:
            try:
                return float(s[k])
            except Exception:
                pass
    return None

base_by_ts = {}
for s in base_slots:
    t = ts_of(s)
    if t:
        w = num(s, ['baseLoadForecastW', 'forecastW', 'powerW', 'base_load_w'])
        if w is not None:
            base_by_ts[t] = max(0.0, w)

ww_by_ts = {}
for s in ww_slots:
    t = ts_of(s)
    if t:
        w = num(s, ['wwPlannedW', 'plannedPowerW', 'powerW', 'ww_w'])
        if w is None:
            action = str(s.get('action') or '').upper()
            w = 1900.0 if action in ('RUN','ON','HEAT') else 0.0
        ww_by_ts[t] = max(0.0, w)

pv_slots = pv.get('slots') or []
by_day = defaultdict(list)
for s in pv_slots:
    day = s.get('localDate')
    if day:
        by_day[day].append(s)

pv_daily = {d.get('localDate'): d for d in (pv.get('daily') or []) if d.get('localDate')}
daily = []
for day in sorted(by_day):
    ds = by_day[day]
    pd = pv_daily.get(day, {})
    residual_kwh = 0.0
    computable_slots = 0
    missing_base_slots = 0
    committed_ww_kwh = 0.0
    for s in ds:
        t = s.get('start')
        pv_w = max(0.0, float(s.get('pvForecastW') or 0))
        if t not in base_by_ts:
            missing_base_slots += 1
            continue
        base_w = base_by_ts[t]
        ww_w = ww_by_ts.get(t, 0.0)
        residual_w = max(0.0, pv_w - base_w - ww_w)
        residual_kwh += residual_w * 0.25 / 1000.0
        committed_ww_kwh += ww_w * 0.25 / 1000.0
        computable_slots += 1

    slot_count = len(ds)
    flex_coverage_fraction = (computable_slots / slot_count) if slot_count else 0.0
    full_flex_day = bool(slot_count and computable_slots == slot_count and not pd.get('isPartialDay', True))
    # Do not present an incomplete daily residual as a complete 'charge potential'.
    flex_kwh = round(residual_kwh, 3) if full_flex_day else None
    if full_flex_day:
        status = 'AVAILABLE_FULL_DAY'
    elif computable_slots:
        status = 'PARTIAL_HORIZON_NOT_PUBLISHED_AS_DAILY_POTENTIAL'
    else:
        status = 'PENDING_MULTI_DAY_BASE_LOAD'

    daily.append({
        'localDate': day,
        'pvForecastKWh': pd.get('pvForecastKWh'),
        'pvCoverageMinutes': pd.get('coverageMinutes'),
        'pvCoverageFraction': pd.get('coverageFraction'),
        'isPartialPvDay': pd.get('isPartialDay'),
        'peakPvForecastW': pd.get('peakPvForecastW'),
        'horizonClasses': pd.get('horizonClasses') or [],
        'flexPotentialKWh': flex_kwh,
        'flexPotentialStatus': status,
        'flexComputableSlots': computable_slots,
        'flexCoverageFraction': round(flex_coverage_fraction, 4),
        'committedWwKWhWithinKnownHorizon': round(committed_ww_kwh, 3),
    })

document = {
    'schema': 'EMS_PI_MULTI_DAY_ENERGY_OUTLOOK_V0.1',
    'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    'mode': 'shadow',
    'readOnly': True,
    'controlWrites': False,
    'purpose': 'GENERIC_MULTI_DAY_ENERGY_OUTLOOK',
    'source': {
        'pv': str(PV),
        'baseLoad': str(BASE),
        'warmWater': str(WW),
    },
    'semantics': {
        'pvForecastKWh': 'Forecast PV production within covered slots for the local day.',
        'flexPotentialKWh': 'Residual PV after known base load and committed WW; published only when the whole local day is covered by both PV and base-load inputs.',
        'pendingPolicy': 'Never extrapolate missing base-load/committed-load horizons.'
    },
    'daily': daily,
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUTPUT.with_suffix('.tmp')
tmp.write_text(json.dumps(document, indent=2))
tmp.replace(OUTPUT)
print(f'PASS: multi-day energy outlook built: {len(daily)} local days')
for d in daily:
    flex = 'PENDING' if d['flexPotentialKWh'] is None else f"{d['flexPotentialKWh']:.3f} kWh"
    print(f"{d['localDate']} pv={d['pvForecastKWh']} kWh pvCoverage={d['pvCoverageFraction']} flex={flex} status={d['flexPotentialStatus']}")
print('output:', OUTPUT)
'''
OUTLOOK_SCRIPT.write_text(outlook)
OUTLOOK_SCRIPT.chmod(0o755)
print('INSTALLED_OUTLOOK_SCRIPT=1')

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')
service = SERVICE.read_text()
anchor = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/base-load/build_base_load_forecast.py\n'
line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/energy-outlook/build_multiday_energy_outlook.py\n'
if line not in service:
    if anchor not in service:
        raise SystemExit('FAIL: base-load ExecStart anchor not found in service')
    service = service.replace(anchor, anchor + line, 1)
    STAGED_SERVICE.write_text(service)
    print(f'STAGED_SERVICE={STAGED_SERVICE}')
else:
    print('SERVICE_ALREADY_CONTAINS_OUTLOOK=1')

print('PASS: multi-day outlook v0.1 runtime patch staged')
print('NOTE: install STAGED_SERVICE with sudo cp, then daemon-reload and restart service')

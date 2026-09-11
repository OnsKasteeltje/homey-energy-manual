#!/usr/bin/env python3
from pathlib import Path

BASE_SRC = Path('/home/jeroen/ems/runtime/planner/base-load/build_base_load_forecast.py')
BASE_MULTI = Path('/home/jeroen/ems/runtime/planner/base-load/build_multiday_base_load_forecast.py')
OUTLOOK = Path('/home/jeroen/ems/runtime/planner/energy-outlook/build_multiday_energy_outlook.py')
SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.multiday-base-outlook-v02')

if not BASE_SRC.exists():
    raise SystemExit(f'FAIL: missing {BASE_SRC}')
if not OUTLOOK.exists():
    raise SystemExit(f'FAIL: missing {OUTLOOK}')

# Build a multi-day base-load forecaster by reusing the validated seasonal algorithm,
# changing only its forecast axis/input/output and removing the hard 96-slot requirement.
text = BASE_SRC.read_text()
text = text.replace(
    'PV_FORECAST = Path("/home/jeroen/ems/data/pv-forecast.json")',
    'PV_FORECAST = Path("/home/jeroen/ems/data/pv-forecast-multiday.json")'
)
text = text.replace(
    'OUTPUT = Path("/home/jeroen/ems/data/base-load-forecast.json")',
    'OUTPUT = Path("/home/jeroen/ems/data/base-load-forecast-multiday.json")'
)
text = text.replace(
    'if len(pv_slots) != 96:\n    raise SystemExit(\n        f"FAIL: expected 96 PV slots, got {len(pv_slots)}"\n    )\n',
    'if len(pv_slots) < 96:\n    raise SystemExit(\n        f"FAIL: expected at least 96 multi-day PV slots, got {len(pv_slots)}"\n    )\n'
)
text = text.replace(
    '        slot.get("slot_start_utc")\n        or slot.get("start")',
    '        slot.get("slot_start_utc")\n        or slot.get("start")'
)
text = text.replace(
    '"schema": "EMS_PI_BASE_LOAD_FORECAST_V0.2"',
    '"schema": "EMS_PI_BASE_LOAD_FORECAST_MULTIDAY_V0.1"'
)
text = text.replace(
    'print("PASS: seasonal base-load forecast built")',
    'print("PASS: seasonal multi-day base-load forecast built")'
)
BASE_MULTI.write_text(text)
BASE_MULTI.chmod(0o755)
print('INSTALLED_MULTI_DAY_BASE_LOAD=1')

outlook = r'''#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PV = Path('/home/jeroen/ems/data/pv-forecast-multiday.json')
BASE = Path('/home/jeroen/ems/data/base-load-forecast-multiday.json')
WW = Path('/home/jeroen/ems/data/ww-plan.json')
OUTPUT = Path('/home/jeroen/ems/data/multiday-energy-outlook.json')

if not PV.exists():
    raise SystemExit(f'FAIL: missing {PV}')
if not BASE.exists():
    raise SystemExit(f'FAIL: missing {BASE}')

pv = json.loads(PV.read_text())
base = json.loads(BASE.read_text())
ww = json.loads(WW.read_text()) if WW.exists() else {}

def first_list(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, list):
            return v
    return []

def ts_of(s):
    return (
        s.get('slot_start_utc')
        or s.get('start')
        or s.get('timestamp')
        or s.get('startUtc')
        or s.get('startAt')
    )

def num(s, keys):
    for k in keys:
        if k in s and s[k] is not None:
            try:
                return float(s[k])
            except Exception:
                pass
    return None

base_slots = first_list(base, ['slots', 'forecast', 'quarterHours'])
ww_slots = first_list(ww, ['slots', 'plan', 'quarterHours'])

base_by_ts = {}
for s in base_slots:
    t = ts_of(s)
    w = num(s, ['baseLoadForecastW', 'forecastW', 'powerW', 'base_load_w'])
    if t and w is not None:
        base_by_ts[t] = max(0.0, w)

ww_by_ts = {}
ww_known_ts = set()
for s in ww_slots:
    t = ts_of(s)
    if not t:
        continue
    ww_known_ts.add(t)
    w = num(s, ['wwPlannedW', 'plannedPowerW', 'powerW', 'ww_w'])
    if w is None:
        action = str(s.get('action') or '').upper()
        w = 1900.0 if action in ('RUN','ON','HEAT') else 0.0
    ww_by_ts[t] = max(0.0, w)

pv_slots = pv.get('slots') or []
by_day = defaultdict(list)
for s in pv_slots:
    d = s.get('localDate')
    if d:
        by_day[d].append(s)

pv_daily = {d.get('localDate'): d for d in (pv.get('daily') or []) if d.get('localDate')}

daily = []
for day in sorted(by_day):
    ds = by_day[day]
    pd = pv_daily.get(day, {})
    total_slots = len(ds)
    base_covered = 0
    ww_covered = 0
    base_residual_kwh = 0.0
    flex_known_kwh = 0.0
    ww_kwh_known = 0.0

    for s in ds:
        t = s.get('start')
        pv_w = max(0.0, float(s.get('pvForecastW') or 0))

        if t in base_by_ts:
            base_covered += 1
            base_w = base_by_ts[t]
            base_residual_w = max(0.0, pv_w - base_w)
            base_residual_kwh += base_residual_w * 0.25 / 1000.0

            if t in ww_known_ts:
                ww_covered += 1
                ww_w = ww_by_ts.get(t, 0.0)
                flex_known_kwh += max(0.0, pv_w - base_w - ww_w) * 0.25 / 1000.0
                ww_kwh_known += ww_w * 0.25 / 1000.0

    base_cov = (base_covered / total_slots) if total_slots else 0.0
    flex_cov = (ww_covered / total_slots) if total_slots else 0.0
    pv_complete = bool(pd.get('isCompleteDay'))
    base_complete = bool(total_slots and base_covered == total_slots)
    flex_complete = bool(pv_complete and base_complete and ww_covered == total_slots)

    if flex_complete:
        status = 'COMPLETE'
    elif ww_covered:
        status = 'PARTIAL_COMMITTED_LOAD_HORIZON'
    elif base_covered:
        status = 'BASE_RESIDUAL_AVAILABLE_COMMITTED_LOADS_PENDING'
    else:
        status = 'NO_BASE_LOAD_COVERAGE'

    daily.append({
        'localDate': day,
        'pvForecastKWh': pd.get('pvForecastKWh'),
        'pvCoverageMinutes': pd.get('coverageMinutes'),
        'pvCoverageFraction': pd.get('coverageFraction'),
        'isPartialPvDay': pd.get('isPartialDay'),
        'peakPvForecastW': pd.get('peakPvForecastW'),
        'horizonClasses': pd.get('horizonClasses') or [],

        # Always publish what is actually known over covered PV+base slots.
        'knownBaseResidualPvKWh': round(base_residual_kwh, 3),
        'baseCoveredSlots': base_covered,
        'baseUncoveredSlots': max(0, total_slots - base_covered),
        'baseCoverageFraction': round(base_cov, 4),
        'baseCoveredHours': round(base_covered * 0.25, 2),
        'baseUncoveredHours': round(max(0, total_slots - base_covered) * 0.25, 2),
        'fullDayBaseResidualPvKWh': round(base_residual_kwh, 3) if pv_complete and base_complete else None,

        # Flex after committed WW is only known where WW-plan coverage also exists.
        'knownFlexPotentialKWh': round(flex_known_kwh, 3),
        'flexCoveredSlots': ww_covered,
        'flexUncoveredSlots': max(0, total_slots - ww_covered),
        'flexCoverageFraction': round(flex_cov, 4),
        'flexCoveredHours': round(ww_covered * 0.25, 2),
        'flexUncoveredHours': round(max(0, total_slots - ww_covered) * 0.25, 2),
        'fullDayFlexPotentialKWh': round(flex_known_kwh, 3) if flex_complete else None,
        'committedWwKWhWithinKnownHorizon': round(ww_kwh_known, 3),
        'status': status,
    })

document = {
    'schema': 'EMS_PI_MULTI_DAY_ENERGY_OUTLOOK_V0.2',
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
        'knownBaseResidualPvKWh': 'Residual PV after base load over slots where both PV and multi-day base-load forecast exist.',
        'fullDayBaseResidualPvKWh': 'Only populated for a complete local PV day with complete base-load coverage.',
        'knownFlexPotentialKWh': 'Residual PV after base load and committed WW, only over slots explicitly covered by the WW plan.',
        'fullDayFlexPotentialKWh': 'Only populated when the complete local day is covered by PV, base load and committed WW inputs.',
        'partialDayPolicy': 'Partial coverage remains usable and is reported explicitly; incomplete days are never discarded or promoted to full-day values.'
    },
    'daily': daily,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUTPUT.with_suffix('.tmp')
tmp.write_text(json.dumps(document, indent=2))
tmp.replace(OUTPUT)

print(f'PASS: multi-day energy outlook v0.2 built: {len(daily)} local days')
for d in daily:
    print(
        f"{d['localDate']} pv={d['pvForecastKWh']} "
        f"baseResidualKnown={d['knownBaseResidualPvKWh']}kWh "
        f"baseCov={d['baseCoverageFraction']} "
        f"flexKnown={d['knownFlexPotentialKWh']}kWh "
        f"flexCov={d['flexCoverageFraction']} status={d['status']}"
    )
print('output:', OUTPUT)
'''

OUTLOOK.write_text(outlook)
OUTLOOK.chmod(0o755)
print('PATCHED_OUTLOOK_V02=1')

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')
service = SERVICE.read_text()
base_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/base-load/build_base_load_forecast.py\n'
multi_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/base-load/build_multiday_base_load_forecast.py\n'
outlook_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/energy-outlook/build_multiday_energy_outlook.py\n'

if multi_line not in service:
    if outlook_line in service:
        service = service.replace(outlook_line, multi_line + outlook_line, 1)
    elif base_line in service:
        service = service.replace(base_line, base_line + multi_line + outlook_line, 1)
    else:
        raise SystemExit('FAIL: could not find safe base/outlook ExecStart anchor')

STAGED.write_text(service)
print(f'STAGED_SERVICE={STAGED}')
print('PASS: multi-day base-load + outlook v0.2 runtime patch staged')
print('NOTE: install STAGED_SERVICE with sudo cp, daemon-reload and start service')

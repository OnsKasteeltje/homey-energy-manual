#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Amsterdam')
OUTLOOK = Path('/home/jeroen/ems/data/multiday-energy-outlook.json')
STATE = Path('/home/jeroen/ems/data/energy-state-v2.json')
ENERGY_NEED = Path('/home/jeroen/ems/data/tesla-energy-need.json')
CONFIG = Path('/home/jeroen/ems/data/tesla-strategy-config.json')
OUTPUT = Path('/home/jeroen/ems/data/tesla-multiday-strategy.json')

if not OUTLOOK.exists():
    raise SystemExit(f'FAIL: missing {OUTLOOK}')
if not STATE.exists():
    raise SystemExit(f'FAIL: missing {STATE}')

outlook = json.loads(OUTLOOK.read_text())
state = json.loads(STATE.read_text())
energy_need = json.loads(ENERGY_NEED.read_text()) if ENERGY_NEED.exists() else {}
config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
tesla = state.get('tesla') or {}

now = datetime.now(timezone.utc)
now_local = now.astimezone(TZ)
weekday = now_local.weekday()

weekend_active = bool(tesla.get('connected') is True and weekday in (3, 4, 5, 6, 0))

departure_local = config.get('departureLocal')
departure_at = None
if departure_local:
    try:
        departure_at = datetime.fromisoformat(departure_local)
        if departure_at.tzinfo is None:
            departure_at = departure_at.replace(tzinfo=TZ)
    except Exception:
        departure_at = None

remaining_need_kwh = None
need_source = 'UNAVAILABLE'
need_trusted_for_control = False

explicit_need = config.get('remainingNeedKWh')
if explicit_need is not None:
    try:
        remaining_need_kwh = max(0.0, float(explicit_need))
        need_source = 'EXPLICIT_STRATEGY_CONFIG'
        need_trusted_for_control = True
    except Exception:
        remaining_need_kwh = None

if remaining_need_kwh is None:
    status = energy_need.get('status')
    estimate = energy_need.get('remainingNeedKWh')
    if status == 'ESTIMATE_AVAILABLE_NOT_YET_TRUSTED' and estimate is not None:
        try:
            remaining_need_kwh = max(0.0, float(estimate))
            need_source = 'TESLA_ENERGY_NEED_SHADOW_ESTIMATE'
            need_trusted_for_control = False
        except Exception:
            remaining_need_kwh = None

days = []
known_flex_total = 0.0
base_residual_total = 0.0
for d in outlook.get('daily') or []:
    known_flex = float(d.get('knownFlexPotentialKWh') or 0.0)
    base_residual = float(d.get('knownBaseResidualPvKWh') or 0.0)
    known_flex_total += known_flex
    base_residual_total += base_residual
    days.append({
        'localDate': d.get('localDate'),
        'pvForecastKWh': d.get('pvForecastKWh'),
        'knownFlexPotentialKWh': d.get('knownFlexPotentialKWh'),
        'knownBaseResidualPvKWh': d.get('knownBaseResidualPvKWh'),
        'flexCoverageFraction': d.get('flexCoverageFraction'),
        'baseCoverageFraction': d.get('baseCoverageFraction'),
        'committedWwKWhWithinKnownHorizon': d.get('committedWwKWhWithinKnownHorizon'),
        'status': d.get('status'),
    })

latest_guaranteed_start = None
energy_deficit_kwh = None
mode = 'WAITING_FOR_TRUSTED_INPUTS'
reason = []

if not weekend_active:
    mode = 'OUTSIDE_ACTIVE_WEEKEND_SESSION'
    reason.append('TESLA_NOT_IN_ACTIVE_WEEKEND_SESSION')
else:
    if remaining_need_kwh is None:
        reason.append('REMAINING_ENERGY_NEED_UNAVAILABLE')
    elif not need_trusted_for_control:
        reason.append('ENERGY_NEED_IS_SHADOW_ESTIMATE_NOT_TRUSTED_FOR_CONTROL')

    if departure_at is None:
        reason.append('EXPLICIT_MONDAY_DEPARTURE_REQUIRED')

    if remaining_need_kwh is not None:
        energy_deficit_kwh = round(max(0.0, remaining_need_kwh - known_flex_total), 3)
        if remaining_need_kwh <= 0.001:
            mode = 'GOAL_REACHED_SHADOW' if not need_trusted_for_control else 'GOAL_REACHED'
        elif departure_at is None:
            mode = 'WAITING_FOR_DEPARTURE_TIME'
        elif not need_trusted_for_control:
            mode = 'SHADOW_ENERGY_BUDGET_AVAILABLE'
        else:
            mode = 'WEEKEND_OPPORTUNITY' if energy_deficit_kwh <= 0.001 else 'WEEKEND_CONSTRAINED'

payload = {
    'schema': 'EMS_PI_TESLA_MULTI_DAY_STRATEGY_V0.2',
    'generatedAt': now.isoformat().replace('+00:00', 'Z'),
    'mode': 'shadow',
    'readOnly': True,
    'controlWrites': False,
    'purpose': 'TESLA_WEEKEND_STRATEGIC_ENERGY_BUDGET',
    'strategyMode': mode,
    'strategyReason': reason,
    'tesla': {
        'connected': tesla.get('connected'),
        'charging': tesla.get('charging'),
        'currentPowerW': tesla.get('power_w'),
        'deadlineActiveFromHomey': tesla.get('deadline_active'),
        'homeyRemainingKWhIgnoredWhenInactive': tesla.get('remaining_kwh') if not tesla.get('deadline_active') else None,
    },
    'inputs': {
        'remainingNeedKWh': remaining_need_kwh,
        'remainingNeedSource': need_source,
        'remainingNeedTrustedForControl': need_trusted_for_control,
        'energyNeedEstimatorStatus': energy_need.get('status') if energy_need else None,
        'energyNeedSessionStartUtc': energy_need.get('sessionStartUtc') if energy_need else None,
        'departureLocal': departure_at.astimezone(TZ).isoformat() if departure_at else None,
        'departureSource': 'EXPLICIT_STRATEGY_CONFIG' if departure_at else 'UNAVAILABLE',
    },
    'energyBudget': {
        'knownCommittedLoadAwarePvKWh': round(known_flex_total, 3),
        'knownBaseResidualPvKWh': round(base_residual_total, 3),
        'energyDeficitAgainstKnownFlexKWh': energy_deficit_kwh,
        'latestGuaranteedStart': latest_guaranteed_start,
    },
    'daily': days,
    'semantics': {
        'shadowEstimatorUse': 'Tesla energy-need estimator may populate the strategy energy budget while remaining explicitly untrusted for control.',
        'controlAuthority': 'No control authority is granted by this input. Strategy and estimator remain shadow/read-only.',
        'knownCommittedLoadAwarePvKWh': 'Sum of Outlook knownFlexPotentialKWh only; this is the safe PV floor where committed-load coverage exists.',
        'knownBaseResidualPvKWh': 'PV residual after base load across the multi-day horizon. Not automatically treated as EV-chargeable where committed WW/load coverage is missing.',
        'energyDeficitAgainstKnownFlexKWh': 'Remaining need minus currently known committed-load-aware PV. Conservative and may shrink as future committed-load coverage becomes known.',
        'latestGuaranteedStart': 'Intentionally null until an explicit departure time and validated max-charge feasibility model are available.',
        'noStaleDeadlineReuse': 'Homey remaining_kwh/deadline are not reused when deadline_active=false.'
    }
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUTPUT.with_suffix('.tmp')
tmp.write_text(json.dumps(payload, indent=2))
tmp.replace(OUTPUT)

print('PASS: Tesla multi-day strategy shadow v0.2 built')
print('strategyMode       :', mode)
print('weekendActive      :', weekend_active)
print('remainingNeedKWh   :', remaining_need_kwh, 'source=', need_source)
print('trustedForControl  :', need_trusted_for_control)
print('departureLocal     :', payload['inputs']['departureLocal'])
print('knownFlexKWh       :', payload['energyBudget']['knownCommittedLoadAwarePvKWh'])
print('baseResidualKWh    :', payload['energyBudget']['knownBaseResidualPvKWh'])
print('energyDeficitKWh   :', energy_deficit_kwh)
print('latestStart        :', latest_guaranteed_start)
print('output             :', OUTPUT)

#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Amsterdam')
OUTLOOK = Path('/home/jeroen/ems/data/multiday-energy-outlook.json')
STATE = Path('/home/jeroen/ems/data/energy-state-v2.json')
ENERGY_NEED = Path('/home/jeroen/ems/data/tesla-energy-need.json')
CONFIG = Path('/home/jeroen/ems/data/tesla-strategy-config.json')
PV = Path('/home/jeroen/ems/data/pv-forecast-multiday.json')
BASE = Path('/home/jeroen/ems/data/base-load-forecast-multiday.json')
WW = Path('/home/jeroen/ems/data/ww-plan.json')
OUTPUT = Path('/home/jeroen/ems/data/tesla-multiday-strategy.json')

SLOT_SECONDS = 15 * 60


def load_json(path, required=False):
    if not path.exists():
        if required:
            raise SystemExit(f'FAIL: missing {path}')
        return {}
    return json.loads(path.read_text())


def parse_ts(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def ts_of(slot):
    return (
        slot.get('slot_start_utc')
        or slot.get('start')
        or slot.get('timestamp')
        or slot.get('startUtc')
        or slot.get('startAt')
    )


def num(slot, keys):
    for key in keys:
        if key in slot and slot[key] is not None:
            try:
                return float(slot[key])
            except Exception:
                pass
    return None


def first_list(doc, keys):
    for key in keys:
        value = doc.get(key)
        if isinstance(value, list):
            return value
    return []


def normalized_ts(value):
    try:
        return parse_ts(value).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except Exception:
        return None


def build_horizon_budget(now_utc, departure_at, pv_doc, base_doc, ww_doc):
    if departure_at is None:
        return None

    departure_utc = departure_at.astimezone(timezone.utc)
    if departure_utc <= now_utc:
        return {
            'status': 'DEPARTURE_NOT_IN_FUTURE',
            'fromUtc': now_utc.isoformat().replace('+00:00', 'Z'),
            'untilUtc': departure_utc.isoformat().replace('+00:00', 'Z'),
            'coveredPvSlotsEquivalent': 0.0,
            'baseCoveredSlotsEquivalent': 0.0,
            'flexCoveredSlotsEquivalent': 0.0,
            'baseCoverageFraction': 0.0,
            'flexCoverageFraction': 0.0,
            'knownBaseResidualPvKWh': 0.0,
            'knownCommittedLoadAwarePvKWh': 0.0,
        }

    base_slots = first_list(base_doc, ['slots', 'forecast', 'quarterHours'])
    ww_slots = first_list(ww_doc, ['slots', 'plan', 'quarterHours'])
    pv_slots = first_list(pv_doc, ['slots', 'forecast', 'quarterHours'])

    base_by_ts = {}
    for slot in base_slots:
        t = normalized_ts(ts_of(slot))
        w = num(slot, ['baseLoadForecastW', 'forecastW', 'powerW', 'base_load_w'])
        if t and w is not None:
            base_by_ts[t] = max(0.0, w)

    ww_by_ts = {}
    ww_known_ts = set()
    for slot in ww_slots:
        t = normalized_ts(ts_of(slot))
        if not t:
            continue
        ww_known_ts.add(t)
        w = num(slot, ['wwPlanW', 'wwPlannedW', 'plannedPowerW', 'powerW', 'ww_w'])
        if w is None:
            action = str(slot.get('action') or '').upper()
            w = 1900.0 if action in ('RUN', 'ON', 'HEAT') else 0.0
        ww_by_ts[t] = max(0.0, w)

    pv_equiv = 0.0
    base_equiv = 0.0
    flex_equiv = 0.0
    base_residual_kwh = 0.0
    flex_kwh = 0.0

    for slot in pv_slots:
        raw_t = ts_of(slot)
        if not raw_t:
            continue
        try:
            start = parse_ts(raw_t).astimezone(timezone.utc)
        except Exception:
            continue

        end = start + timedelta(seconds=SLOT_SECONDS)
        overlap_start = max(start, now_utc)
        overlap_end = min(end, departure_utc)
        overlap_s = (overlap_end - overlap_start).total_seconds()
        if overlap_s <= 0:
            continue

        fraction = overlap_s / SLOT_SECONDS
        pv_equiv += fraction
        key = start.isoformat().replace('+00:00', 'Z')
        pv_w = max(0.0, float(slot.get('pvForecastW') or 0.0))

        if key in base_by_ts:
            base_equiv += fraction
            base_w = base_by_ts[key]
            base_residual_w = max(0.0, pv_w - base_w)
            base_residual_kwh += base_residual_w * overlap_s / 3_600_000.0

            if key in ww_known_ts:
                flex_equiv += fraction
                ww_w = ww_by_ts.get(key, 0.0)
                flex_w = max(0.0, pv_w - base_w - ww_w)
                flex_kwh += flex_w * overlap_s / 3_600_000.0

    base_cov = base_equiv / pv_equiv if pv_equiv else 0.0
    flex_cov = flex_equiv / pv_equiv if pv_equiv else 0.0

    return {
        'status': 'BOUNDED_TO_DEPARTURE',
        'fromUtc': now_utc.isoformat().replace('+00:00', 'Z'),
        'untilUtc': departure_utc.isoformat().replace('+00:00', 'Z'),
        'coveredPvSlotsEquivalent': round(pv_equiv, 3),
        'baseCoveredSlotsEquivalent': round(base_equiv, 3),
        'flexCoveredSlotsEquivalent': round(flex_equiv, 3),
        'baseCoverageFraction': round(base_cov, 4),
        'flexCoverageFraction': round(flex_cov, 4),
        'knownBaseResidualPvKWh': round(base_residual_kwh, 3),
        'knownCommittedLoadAwarePvKWh': round(flex_kwh, 3),
    }


outlook = load_json(OUTLOOK, required=True)
state = load_json(STATE, required=True)
energy_need = load_json(ENERGY_NEED)
config = load_json(CONFIG)
pv = load_json(PV)
base = load_json(BASE)
ww = load_json(WW)
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
        departure_at = departure_at.astimezone(TZ)
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
for d in outlook.get('daily') or []:
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

horizon = build_horizon_budget(now, departure_at, pv, base, ww)
bounded_flex_kwh = horizon.get('knownCommittedLoadAwarePvKWh') if horizon else None
bounded_base_residual_kwh = horizon.get('knownBaseResidualPvKWh') if horizon else None

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
        reason.append('ENERGY_BUDGET_NOT_COMPUTED_WITHOUT_DEPARTURE_BOUND')

    if remaining_need_kwh is not None and departure_at is not None and horizon is not None:
        energy_deficit_kwh = round(
            max(0.0, remaining_need_kwh - float(bounded_flex_kwh or 0.0)),
            3,
        )

    if remaining_need_kwh is not None:
        if remaining_need_kwh <= 0.001:
            mode = 'GOAL_REACHED_SHADOW' if not need_trusted_for_control else 'GOAL_REACHED'
        elif departure_at is None:
            mode = 'WAITING_FOR_DEPARTURE_TIME'
        elif horizon and horizon.get('status') == 'DEPARTURE_NOT_IN_FUTURE':
            mode = 'INVALID_DEPARTURE_TIME'
            reason.append('DEPARTURE_MUST_BE_IN_FUTURE')
        elif not need_trusted_for_control:
            mode = 'SHADOW_ENERGY_BUDGET_AVAILABLE'
        else:
            mode = 'WEEKEND_OPPORTUNITY' if energy_deficit_kwh <= 0.001 else 'WEEKEND_CONSTRAINED'

payload = {
    'schema': 'EMS_PI_TESLA_MULTI_DAY_STRATEGY_V0.3',
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
        'departureLocal': departure_at.isoformat() if departure_at else None,
        'departureSource': 'EXPLICIT_STRATEGY_CONFIG' if departure_at else 'UNAVAILABLE',
    },
    'energyBudget': {
        'budgetStatus': horizon.get('status') if horizon else 'WAITING_FOR_DEPARTURE_BOUND',
        'budgetFromUtc': horizon.get('fromUtc') if horizon else None,
        'budgetUntilUtc': horizon.get('untilUtc') if horizon else None,
        'knownCommittedLoadAwarePvKWh': bounded_flex_kwh,
        'knownBaseResidualPvKWh': bounded_base_residual_kwh,
        'baseCoverageFraction': horizon.get('baseCoverageFraction') if horizon else None,
        'flexCoverageFraction': horizon.get('flexCoverageFraction') if horizon else None,
        'energyDeficitAgainstKnownFlexKWh': energy_deficit_kwh,
        'latestGuaranteedStart': latest_guaranteed_start,
    },
    'daily': days,
    'semantics': {
        'shadowEstimatorUse': 'Tesla energy-need estimator may populate the strategy energy budget while remaining explicitly untrusted for control.',
        'controlAuthority': 'No control authority is granted by this input. Strategy and estimator remain shadow/read-only.',
        'departureBound': 'Strategic energy totals are not computed until departure is explicit. With departure present, totals are integrated only over overlap with now..departure at 15-minute slot resolution.',
        'knownCommittedLoadAwarePvKWh': 'Residual PV after base load and explicitly known committed WW, integrated only inside now..departure.',
        'knownBaseResidualPvKWh': 'Residual PV after base load, integrated only inside now..departure.',
        'energyDeficitAgainstKnownFlexKWh': 'Remaining need minus committed-load-aware PV inside the explicit departure horizon. Null until departure is known.',
        'dailyDisplay': 'Daily rows remain informational and may extend beyond departure; they are never summed into the Tesla departure-bounded energy budget.',
        'latestGuaranteedStart': 'Intentionally null until a validated max-charge feasibility model is available.',
        'noStaleDeadlineReuse': 'Homey remaining_kwh/deadline are not reused when deadline_active=false.'
    }
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUTPUT.with_suffix('.tmp')
tmp.write_text(json.dumps(payload, indent=2))
tmp.replace(OUTPUT)

print('PASS: Tesla multi-day strategy shadow v0.3 built')
print('strategyMode       :', mode)
print('weekendActive      :', weekend_active)
print('remainingNeedKWh   :', remaining_need_kwh, 'source=', need_source)
print('trustedForControl  :', need_trusted_for_control)
print('departureLocal     :', payload['inputs']['departureLocal'])
print('budgetStatus       :', payload['energyBudget']['budgetStatus'])
print('knownFlexKWh       :', payload['energyBudget']['knownCommittedLoadAwarePvKWh'])
print('baseResidualKWh    :', payload['energyBudget']['knownBaseResidualPvKWh'])
print('energyDeficitKWh   :', energy_deficit_kwh)
print('latestStart        :', latest_guaranteed_start)
print('output             :', OUTPUT)

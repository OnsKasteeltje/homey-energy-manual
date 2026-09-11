#!/usr/bin/env python3
from pathlib import Path

TARGET = Path('/home/jeroen/ems/runtime/planner/tesla-strategy/build_tesla_multiday_strategy.py')
SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.tesla-strategy-v01')

script = r'''#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Amsterdam')
OUTLOOK = Path('/home/jeroen/ems/data/multiday-energy-outlook.json')
STATE = Path('/home/jeroen/ems/data/energy-state-v2.json')
CONFIG = Path('/home/jeroen/ems/data/tesla-strategy-config.json')
OUTPUT = Path('/home/jeroen/ems/data/tesla-multiday-strategy.json')

if not OUTLOOK.exists():
    raise SystemExit(f'FAIL: missing {OUTLOOK}')
if not STATE.exists():
    raise SystemExit(f'FAIL: missing {STATE}')

outlook = json.loads(OUTLOOK.read_text())
state = json.loads(STATE.read_text())
config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
tesla = state.get('tesla') or {}

now = datetime.now(timezone.utc)
now_local = now.astimezone(TZ)
weekday = now_local.weekday()  # Mon=0 ... Sun=6

# Weekend session semantics are observational/shadow only. Thursday evening through
# Monday is the planning envelope, but no exact Monday departure time is invented.
weekend_active = bool(tesla.get('connected') is True and weekday in (3,4,5,6,0))

# Only use an explicitly configured departure. The existing Homey deadline may be stale
# or belong to another session and is therefore deliberately ignored here.
departure_local = config.get('departureLocal')
departure_at = None
if departure_local:
    try:
        departure_at = datetime.fromisoformat(departure_local)
        if departure_at.tzinfo is None:
            departure_at = departure_at.replace(tzinfo=TZ)
    except Exception:
        departure_at = None

# Same principle for energy need: only use a trusted explicit strategy input.
# Do not reuse tesla.remaining_kwh when deadline_active is false, because that value
# can be a stale manual deadline residue from an older session.
remaining_need_kwh = None
need_source = 'UNAVAILABLE'
explicit_need = config.get('remainingNeedKWh')
if explicit_need is not None:
    try:
        remaining_need_kwh = max(0.0, float(explicit_need))
        need_source = 'EXPLICIT_STRATEGY_CONFIG'
    except Exception:
        remaining_need_kwh = None

# Daily PV capacity surfaces. We preserve coverage instead of pretending uncovered
# committed-load horizons are zero-load horizons.
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

# Strategy state is intentionally conservative until both need and departure are trusted.
latest_guaranteed_start = None
energy_deficit_kwh = None
mode = 'WAITING_FOR_TRUSTED_INPUTS'
reason = []

if not weekend_active:
    mode = 'OUTSIDE_ACTIVE_WEEKEND_SESSION'
    reason.append('TESLA_NOT_IN_ACTIVE_WEEKEND_SESSION')
else:
    if remaining_need_kwh is None:
        reason.append('TRUSTED_REMAINING_ENERGY_NEED_REQUIRED')
    if departure_at is None:
        reason.append('EXPLICIT_MONDAY_DEPARTURE_REQUIRED')

    if remaining_need_kwh is not None:
        # knownFlexPotential is the safe committed-load-aware floor within current WW
        # coverage. Beyond that horizon we expose base residual separately but do not
        # silently count it as chargeable EV energy.
        energy_deficit_kwh = round(max(0.0, remaining_need_kwh - known_flex_total), 3)
        if remaining_need_kwh <= 0.001:
            mode = 'GOAL_REACHED'
        elif departure_at is not None:
            mode = 'WEEKEND_OPPORTUNITY' if energy_deficit_kwh <= 0.001 else 'WEEKEND_CONSTRAINED'
        else:
            mode = 'WAITING_FOR_DEPARTURE_TIME'

payload = {
    'schema': 'EMS_PI_TESLA_MULTI_DAY_STRATEGY_V0.1',
    'generatedAt': now.isoformat().replace('+00:00','Z'),
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
        'knownCommittedLoadAwarePvKWh': 'Sum of Outlook knownFlexPotentialKWh only; this is the safe PV floor where committed-load coverage exists.',
        'knownBaseResidualPvKWh': 'PV residual after base load across the multi-day horizon. Not automatically treated as EV-chargeable where committed WW/load coverage is missing.',
        'energyDeficitAgainstKnownFlexKWh': 'Remaining need minus currently known committed-load-aware PV. This is conservative and may shrink as future committed-load coverage becomes known.',
        'latestGuaranteedStart': 'Intentionally null in v0.1 until an explicit departure time and validated max-charge feasibility model are available.',
        'noStaleDeadlineReuse': 'Homey remaining_kwh/deadline are not reused when deadline_active=false.'
    }
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUTPUT.with_suffix('.tmp')
tmp.write_text(json.dumps(payload, indent=2))
tmp.replace(OUTPUT)

print('PASS: Tesla multi-day strategy shadow v0.1 built')
print('strategyMode       :', mode)
print('weekendActive      :', weekend_active)
print('remainingNeedKWh   :', remaining_need_kwh, 'source=', need_source)
print('departureLocal     :', payload['inputs']['departureLocal'])
print('knownFlexKWh       :', payload['energyBudget']['knownCommittedLoadAwarePvKWh'])
print('baseResidualKWh    :', payload['energyBudget']['knownBaseResidualPvKWh'])
print('energyDeficitKWh   :', energy_deficit_kwh)
print('latestStart        :', latest_guaranteed_start)
print('output             :', OUTPUT)
'''

TARGET.parent.mkdir(parents=True, exist_ok=True)
TARGET.write_text(script)
TARGET.chmod(0o755)
print('INSTALLED_TESLA_STRATEGY=1')

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')
service = SERVICE.read_text()
outlook_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/energy-outlook/build_multiday_energy_outlook.py\n'
tesla_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/tesla-strategy/build_tesla_multiday_strategy.py\n'
quarter_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/quarter-hour-plan/build_shadow_load_plan.py\n'

if tesla_line not in service:
    if outlook_line in service:
        service = service.replace(outlook_line, outlook_line + tesla_line, 1)
    elif quarter_line in service:
        service = service.replace(quarter_line, tesla_line + quarter_line, 1)
    else:
        raise SystemExit('FAIL: could not find safe insertion point for Tesla strategy')

# Verify strategy remains downstream of Outlook and upstream of action planners.
lines = service.splitlines()
out_idx = next((i for i,l in enumerate(lines) if 'build_multiday_energy_outlook.py' in l), -1)
tes_idx = next((i for i,l in enumerate(lines) if 'build_tesla_multiday_strategy.py' in l), -1)
q_idx = next((i for i,l in enumerate(lines) if 'build_shadow_load_plan.py' in l), -1)
if not (0 <= out_idx < tes_idx < q_idx):
    raise SystemExit(f'FAIL: unsafe service order outlook={out_idx} tesla={tes_idx} quarter={q_idx}')

STAGED.write_text(service)
print(f'STAGED_SERVICE={STAGED}')
print('PASS: Tesla multi-day strategy v0.1 staged after Outlook and before action planners')
print('NOTE: no control writes; no existing dynamic-planner action logic changed')

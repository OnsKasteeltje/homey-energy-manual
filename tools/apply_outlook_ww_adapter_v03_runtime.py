#!/usr/bin/env python3
from pathlib import Path

OUTLOOK = Path('/home/jeroen/ems/runtime/planner/energy-outlook/build_multiday_energy_outlook.py')

if not OUTLOOK.exists():
    raise SystemExit(f'FAIL: missing {OUTLOOK}')

text = OUTLOOK.read_text()

old = "w = num(s, ['wwPlannedW', 'plannedPowerW', 'powerW', 'ww_w'])"
new = "w = num(s, ['wwPlanW', 'wwPlannedW', 'plannedPowerW', 'powerW', 'ww_w'])"

if old in text:
    text = text.replace(old, new, 1)
elif "'wwPlanW'" in text:
    print('WW_PLAN_W_ALREADY_SUPPORTED=1')
else:
    raise SystemExit('FAIL: expected WW power adapter not found; refusing unsafe patch')

# Add explicit observability: count positive WW reservation slots and print known WW kWh.
old_loop = "    ww_kwh_known = 0.0\n\n    for s in ds:\n"
new_loop = "    ww_kwh_known = 0.0\n    ww_reserved_slots = 0\n\n    for s in ds:\n"
if old_loop in text:
    text = text.replace(old_loop, new_loop, 1)
elif 'ww_reserved_slots = 0' not in text:
    raise SystemExit('FAIL: expected daily WW accumulator block not found')

old_acc = "                ww_kwh_known += ww_w * 0.25 / 1000.0\n"
new_acc = "                ww_kwh_known += ww_w * 0.25 / 1000.0\n                if ww_w > 0:\n                    ww_reserved_slots += 1\n"
if old_acc in text:
    text = text.replace(old_acc, new_acc, 1)
elif 'ww_reserved_slots += 1' not in text:
    raise SystemExit('FAIL: expected WW accumulation line not found')

old_field = "        'committedWwKWhWithinKnownHorizon': round(ww_kwh_known, 3),\n"
new_field = "        'committedWwKWhWithinKnownHorizon': round(ww_kwh_known, 3),\n        'committedWwReservedSlotsWithinKnownHorizon': ww_reserved_slots,\n"
if old_field in text:
    text = text.replace(old_field, new_field, 1)
elif 'committedWwReservedSlotsWithinKnownHorizon' not in text:
    raise SystemExit('FAIL: expected committed WW output field not found')

old_print = "        f\"flexCov={d['flexCoverageFraction']} status={d['status']}\"\n"
new_print = "        f\"flexCov={d['flexCoverageFraction']} \"\n        f\"wwReserved={d['committedWwKWhWithinKnownHorizon']}kWh/\"\n        f\"{d['committedWwReservedSlotsWithinKnownHorizon']}slots status={d['status']}\"\n"
if old_print in text:
    text = text.replace(old_print, new_print, 1)
elif 'wwReserved=' not in text:
    raise SystemExit('FAIL: expected outlook print block not found')

text = text.replace("'schema': 'EMS_PI_MULTI_DAY_ENERGY_OUTLOOK_V0.2'", "'schema': 'EMS_PI_MULTI_DAY_ENERGY_OUTLOOK_V0.3'")

OUTLOOK.write_text(text)
OUTLOOK.chmod(0o755)

print('PATCHED_OUTLOOK_WW_ADAPTER=1')
print('SUPPORTED_WW_FIELD=wwPlanW')
print('PASS: multi-day outlook WW adapter v0.3 installed')
print('NOTE: no systemd service change required; restart ems-pv-forecast.service to validate')

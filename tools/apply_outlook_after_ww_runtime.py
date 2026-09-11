#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.outlook-after-ww')

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')

lines = SERVICE.read_text().splitlines()
outlook = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/energy-outlook/build_multiday_energy_outlook.py'

# Remove all current occurrences first so reruns stay idempotent.
lines = [line for line in lines if line.strip() != outlook]

# Prefer placing the outlook immediately after the last warm-water stage.
# This guarantees it sees the WW plan generated in the same service run.
warm_indexes = [
    i for i, line in enumerate(lines)
    if line.startswith('ExecStart=') and '/warm-water/' in line
]
if not warm_indexes:
    raise SystemExit('FAIL: no warm-water ExecStart lines found; refusing unsafe reorder')

insert_at = max(warm_indexes) + 1
lines.insert(insert_at, outlook)

# Safety check: outlook must still run before either downstream load planner.
downstream_indexes = [
    i for i, line in enumerate(lines)
    if line.startswith('ExecStart=') and (
        '/quarter-hour-plan/' in line
        or '/dynamic-plan/' in line
    )
]
outlook_index = lines.index(outlook)
if downstream_indexes and outlook_index > min(downstream_indexes):
    raise SystemExit('FAIL: outlook would be placed after downstream planner; refusing patch')

STAGED.write_text('\n'.join(lines) + '\n')
print(f'STAGED_SERVICE={STAGED}')
print('PASS: outlook reordered after warm-water stages and before downstream planners')
print('OUTLOOK_INDEX=', outlook_index)
print('LAST_WARM_WATER_INDEX=', max(warm_indexes))
if downstream_indexes:
    print('FIRST_DOWNSTREAM_INDEX=', min(downstream_indexes))
print('NOTE: install staged service with sudo cp, daemon-reload and start service')

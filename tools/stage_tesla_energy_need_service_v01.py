#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.tesla-energy-need-v01')

store_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/datastore/store_tesla_connection_from_state.py'
need_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/tesla-strategy/build_tesla_energy_need.py'
pv_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/pv-forecast/fetch_pv_forecast.py'

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')

lines = SERVICE.read_text().splitlines()

if store_line not in lines:
    raise SystemExit('FAIL: Tesla connection-state recorder is not present in the existing planner service')

if need_line not in lines:
    store_idx = lines.index(store_line)
    lines.insert(store_idx + 1, need_line)

store_idx = lines.index(store_line)
need_idx = lines.index(need_line)
pv_idx = lines.index(pv_line) if pv_line in lines else -1

if not (store_idx + 1 == need_idx):
    raise SystemExit(f'FAIL: unsafe order storeIndex={store_idx} needIndex={need_idx}')
if pv_idx < 0 or not (need_idx < pv_idx):
    raise SystemExit(f'FAIL: energy-need must stay before PV forecast; needIndex={need_idx} pvIndex={pv_idx}')
if lines.count(need_line) != 1:
    raise SystemExit(f'FAIL: expected exactly one Tesla energy-need ExecStart, found {lines.count(need_line)}')

STAGED.write_text('\n'.join(lines) + '\n')
print(f'STAGED={STAGED}')
print(f'storeIndex={store_idx}')
print(f'needIndex={need_idx}')
print(f'pvIndex={pv_idx}')
print('PASS: existing planner service staged with Tesla energy-need directly after connection-state history')
print('ARCHITECTURE: no extra Homey read, no extra timer, no new polling loop')
print('NOTE: Tesla multi-day strategy consumption remains unchanged')

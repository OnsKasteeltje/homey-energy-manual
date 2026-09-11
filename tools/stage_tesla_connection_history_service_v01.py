#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.tesla-state-history-v01')
STORE = '/home/jeroen/ems/runtime/datastore/store_tesla_connection_from_state.py'
FETCH = '/home/jeroen/ems/runtime/planner/fetch_energy_state.py'

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')
if not Path(STORE).exists():
    raise SystemExit(f'FAIL: missing runtime script {STORE}')

service = SERVICE.read_text()
fetch_line = f'ExecStart=/usr/bin/python3 {FETCH}\n'
store_line = f'ExecStart=/usr/bin/python3 {STORE}\n'

if fetch_line not in service:
    raise SystemExit('FAIL: existing energy-state fetch step not found; refusing change')

if store_line not in service:
    service = service.replace(fetch_line, fetch_line + store_line, 1)

lines = service.splitlines()
fetch_idx = next((i for i, line in enumerate(lines) if FETCH in line), -1)
store_idx = next((i for i, line in enumerate(lines) if STORE in line), -1)
pv_idx = next((i for i, line in enumerate(lines) if 'fetch_pv_forecast.py' in line), -1)

if not (0 <= fetch_idx < store_idx):
    raise SystemExit(f'FAIL: unsafe service order fetch={fetch_idx} store={store_idx}')
if pv_idx >= 0 and not (store_idx < pv_idx):
    raise SystemExit(f'FAIL: store must remain before PV forecast: store={store_idx} pv={pv_idx}')

STAGED.write_text(service)

print(f'STAGED={STAGED}')
print(f'fetchIndex={fetch_idx}')
print(f'storeIndex={store_idx}')
print(f'pvIndex={pv_idx}')
print('PASS: existing planner service staged with Tesla connection history directly after energy-state fetch')
print('ARCHITECTURE: no extra Homey read, no extra timer, no new polling loop')

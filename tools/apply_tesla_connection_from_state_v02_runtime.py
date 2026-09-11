#!/usr/bin/env python3
from pathlib import Path

TARGET = Path('/home/jeroen/ems/runtime/datastore/store_tesla_connection_from_state.py')
SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.tesla-state-history-v02')

script = r"""#!/usr/bin/env python3
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATE = Path('/home/jeroen/ems/data/energy-state-v2.json')
DB = Path('/home/jeroen/ems/data/ems-history.sqlite')

if not STATE.exists():
    raise SystemExit(f'FAIL: missing {STATE}')
if not DB.exists():
    raise SystemExit(f'FAIL: missing {DB}')

payload = json.loads(STATE.read_text())
tesla = payload.get('tesla') or {}
connected = tesla.get('connected')
if connected is not True and connected is not False:
    raise SystemExit('FAIL: energy-state Tesla connected is not boolean')

meta = payload.get('meta') or {}
source_ts = (
    meta.get('source_sample_at')
    or meta.get('generated_at')
    or payload.get('generatedAt')
    or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
)
state_revision = meta.get('state_revision')

con = sqlite3.connect(DB)
try:
    con.execute("""
        CREATE TABLE IF NOT EXISTS tesla_connection_events (
            id INTEGER PRIMARY KEY,
            ts_utc TEXT NOT NULL,
            connected INTEGER NOT NULL CHECK (connected IN (0,1)),
            event TEXT NOT NULL,
            state_revision INTEGER,
            source TEXT NOT NULL,
            UNIQUE(ts_utc, connected)
        )
    """)

    prev = con.execute(
        'SELECT connected, ts_utc FROM tesla_connection_events ORDER BY ts_utc DESC, id DESC LIMIT 1'
    ).fetchone()

    current = 1 if connected else 0
    if prev is None:
        event = 'BASELINE_CONNECTED' if connected else 'BASELINE_DISCONNECTED'
        changed = True
    elif int(prev[0]) != current:
        event = 'CONNECTED' if connected else 'DISCONNECTED'
        changed = True
    else:
        event = 'UNCHANGED'
        changed = False

    inserted = 0
    if changed:
        cur = con.execute("""
            INSERT OR IGNORE INTO tesla_connection_events
            (ts_utc, connected, event, state_revision, source)
            VALUES (?, ?, ?, ?, 'ENERGY_STATE_V2_EXISTING_PIPELINE')
        """, (source_ts, current, event, state_revision))
        inserted = cur.rowcount
        con.commit()

    count = con.execute('SELECT COUNT(*) FROM tesla_connection_events').fetchone()[0]
    print('PASS: Tesla connection state evaluated from existing energy-state cache')
    print('connected      :', connected)
    print('event          :', event)
    print('inserted       :', inserted)
    print('historyRows    :', count)
    print('sourceTs       :', source_ts)
    print('stateRevision  :', state_revision)
    print('homeyExtraReads: 0')
finally:
    con.close()
"""

TARGET.parent.mkdir(parents=True, exist_ok=True)
TARGET.write_text(script)
TARGET.chmod(0o755)
print(f'INSTALLED={TARGET}')

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')
service = SERVICE.read_text()
fetch_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/fetch_energy_state.py\n'
store_line = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/datastore/store_tesla_connection_from_state.py\n'

if store_line not in service:
    if fetch_line not in service:
        raise SystemExit('FAIL: existing energy-state fetch step not found; refusing unsafe insertion')
    service = service.replace(fetch_line, fetch_line + store_line, 1)

lines = service.splitlines()
fetch_idx = next((i for i, line in enumerate(lines) if 'fetch_energy_state.py' in line), -1)
store_idx = next((i for i, line in enumerate(lines) if 'store_tesla_connection_from_state.py' in line), -1)
pv_idx = next((i for i, line in enumerate(lines) if 'fetch_pv_forecast.py' in line), -1)
if not (0 <= fetch_idx < store_idx < pv_idx):
    raise SystemExit(f'FAIL: unsafe order fetch={fetch_idx} store={store_idx} pv={pv_idx}')

STAGED.write_text(service)
print(f'STAGED_SERVICE={STAGED}')
print('PASS: staged Tesla connection history on existing energy-state pipeline')
print('ARCHITECTURE: no new Homey API call, no extra timer, no new polling loop')

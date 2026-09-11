#!/usr/bin/env python3
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

create_sql = (
    'CREATE TABLE IF NOT EXISTS tesla_connection_events ('
    'id INTEGER PRIMARY KEY, '
    'ts_utc TEXT NOT NULL, '
    'connected INTEGER NOT NULL CHECK (connected IN (0,1)), '
    'event TEXT NOT NULL, '
    'state_revision INTEGER, '
    'source TEXT NOT NULL, '
    'UNIQUE(ts_utc, connected)'
    ')'
)
insert_sql = (
    'INSERT OR IGNORE INTO tesla_connection_events '
    '(ts_utc, connected, event, state_revision, source) '
    "VALUES (?, ?, ?, ?, 'ENERGY_STATE_V2_EXISTING_PIPELINE')"
)

con = sqlite3.connect(DB)
try:
    con.execute(create_sql)
    prev = con.execute(
        'SELECT connected, ts_utc FROM tesla_connection_events '
        'ORDER BY ts_utc DESC, id DESC LIMIT 1'
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
        cur = con.execute(insert_sql, (source_ts, current, event, state_revision))
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

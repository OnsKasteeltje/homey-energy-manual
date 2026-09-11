#!/usr/bin/env python3
from pathlib import Path

TARGET = Path('/home/jeroen/ems/runtime/datastore/collect_tesla_connection.py')
SERVICE_STAGED = Path('/tmp/ems-tesla-connection.service')
TIMER_STAGED = Path('/tmp/ems-tesla-connection.timer')

collector = r'''#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DB = Path('/home/jeroen/ems/data/ems-history.sqlite')
HOME = Path.home()
HOMEY_PROJECT = HOME / 'ems-homey-adapter'
HOMEY_CLI = HOMEY_PROJECT / 'node_modules' / '.bin' / 'homey'
NODE24_BIN = Path('/opt/node-v24.20.0/bin')
VARIABLE_NAME = 'TeslaGekoppeld'
SOURCE = 'HOMEY_LOGIC_TESLAGEKOPPELD'


def now_z():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read_logic_variables():
    env = os.environ.copy()
    env['PATH'] = f"{NODE24_BIN}:{env.get('PATH', '')}"
    cmd = [str(HOMEY_CLI), 'api', 'logic', 'get-variables', '--json']
    r = subprocess.run(cmd, cwd=HOMEY_PROJECT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or 'Homey CLI failed').strip())
    return json.loads(r.stdout)


def find_variable(payload):
    if isinstance(payload, dict):
        candidates = list(payload.values())
    elif isinstance(payload, list):
        candidates = payload
    else:
        candidates = []

    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = item.get('name') or item.get('title')
        if name == VARIABLE_NAME:
            return item
    return None


def normalize_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ('true', '1', 'yes', 'on'):
            return True
        if s in ('false', '0', 'no', 'off'):
            return False
    raise ValueError(f'Unsupported TeslaGekoppeld value: {value!r}')


def main():
    if not DB.exists():
        raise RuntimeError(f'Database not found: {DB}')
    if not HOMEY_CLI.exists():
        raise RuntimeError(f'Homey CLI not found: {HOMEY_CLI}')

    payload = read_logic_variables()
    var = find_variable(payload)
    if var is None:
        raise RuntimeError(f'Homey variable not found: {VARIABLE_NAME}')

    connected = normalize_bool(var.get('value'))
    ts = now_z()

    con = sqlite3.connect(DB)
    try:
        con.execute('''
            CREATE TABLE IF NOT EXISTS tesla_connection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                connected INTEGER NOT NULL CHECK (connected IN (0,1)),
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                homey_variable_name TEXT NOT NULL
            )
        ''')
        con.execute('''
            CREATE INDEX IF NOT EXISTS idx_tesla_connection_events_ts
            ON tesla_connection_events(ts_utc)
        ''')

        prev = con.execute('''
            SELECT connected, ts_utc
            FROM tesla_connection_events
            ORDER BY id DESC
            LIMIT 1
        ''').fetchone()

        if prev is None:
            event_type = 'BASELINE_CONNECTED' if connected else 'BASELINE_DISCONNECTED'
            changed = True
        else:
            previous_connected = bool(prev[0])
            changed = previous_connected != connected
            if not changed:
                print(f'PASS: TeslaGekoppeld unchanged connected={connected}; no event inserted')
                return
            event_type = 'CONNECTED' if connected else 'DISCONNECTED'

        con.execute('''
            INSERT INTO tesla_connection_events
            (ts_utc, connected, event_type, source, homey_variable_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (ts, 1 if connected else 0, event_type, SOURCE, VARIABLE_NAME))
        con.commit()

        print(f'PASS: Tesla connection event stored: {event_type} connected={connected} ts={ts}')
        print('source:', SOURCE)
        print('table : tesla_connection_events')
    finally:
        con.close()


if __name__ == '__main__':
    main()
'''

TARGET.parent.mkdir(parents=True, exist_ok=True)
TARGET.write_text(collector)
TARGET.chmod(0o755)

service = '''[Unit]\nDescription=EMS Tesla connection state collector\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nType=oneshot\nUser=jeroen\nWorkingDirectory=/home/jeroen/ems\nExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/datastore/collect_tesla_connection.py\n'''

timer = '''[Unit]\nDescription=Poll TeslaGekoppeld from Homey every minute\n\n[Timer]\nOnBootSec=45s\nOnUnitActiveSec=60s\nAccuracySec=5s\nPersistent=true\nUnit=ems-tesla-connection.service\n\n[Install]\nWantedBy=timers.target\n'''

SERVICE_STAGED.write_text(service)
TIMER_STAGED.write_text(timer)

print(f'INSTALLED_COLLECTOR={TARGET}')
print(f'STAGGED_SERVICE={SERVICE_STAGED}')
print(f'STAGGED_TIMER={TIMER_STAGED}')
print('PASS: Tesla connection-history collector v0.1 staged')
print('NOTE: stores baseline + state transitions only; no planner/control writes')

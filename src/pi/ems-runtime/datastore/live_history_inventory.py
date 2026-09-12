#!/usr/bin/env python3

import sqlite3
from pathlib import Path

DB = Path('/home/jeroen/ems/data/ems-history.sqlite')

THERMAL_HINTS = (
    'honeywell', 'zone', 'room', 'temp', 'target', 'setpoint',
    'quatt', 'heat', 'thermal', 'cop', 'cv', 'boiler', 'outside'
)


def rows(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def print_table(title, columns, data):
    print(f'\n=== {title} ===')
    if not data:
        print('(none)')
        return
    widths = [len(c) for c in columns]
    for row in data:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value if value is not None else 'NULL')))
    fmt = '  '.join('{:<%d}' % w for w in widths)
    print(fmt.format(*columns))
    print(fmt.format(*('-' * w for w in widths)))
    for row in data:
        print(fmt.format(*(str(v if v is not None else 'NULL') for v in row)))


def main():
    if not DB.exists():
        raise SystemExit(f'FAIL: database not found: {DB}')

    # SQLite URI mode=ro guarantees that this diagnostic cannot mutate the live DB.
    con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    try:
        tables = rows(con, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        print_table('TABLES', ['name'], tables)

        devices_cols = [r[1] for r in rows(con, 'PRAGMA table_info(devices)')]
        metrics_cols = [r[1] for r in rows(con, 'PRAGMA table_info(metrics)')]
        meas_cols = [r[1] for r in rows(con, 'PRAGMA table_info(measurements)')]
        print('\n=== SCHEMA COLUMNS ===')
        print('devices:', ', '.join(devices_cols))
        print('metrics:', ', '.join(metrics_cols))
        print('measurements:', ', '.join(meas_cols))

        devices = rows(con, '''
            SELECT id, source, source_device_id, device_key, name, device_type
            FROM devices
            ORDER BY device_key
        ''')
        print_table('DEVICE REGISTRY',
                    ['id','source','source_device_id','device_key','name','device_type'],
                    devices)

        metrics = rows(con, '''
            SELECT id, metric_key, unit, value_type, description
            FROM metrics
            ORDER BY metric_key
        ''')
        print_table('METRIC REGISTRY',
                    ['id','metric_key','unit','value_type','description'],
                    metrics)

        coverage = rows(con, '''
            SELECT d.device_key,
                   m.metric_key,
                   COUNT(*) AS samples,
                   MIN(x.ts_utc) AS first_ts,
                   MAX(x.ts_utc) AS last_ts,
                   MIN(x.source_resolution_seconds) AS min_res_s,
                   MAX(x.source_resolution_seconds) AS max_res_s,
                   GROUP_CONCAT(DISTINCT x.quality) AS qualities
            FROM measurements x
            JOIN devices d ON d.id=x.device_id
            JOIN metrics m ON m.id=x.metric_id
            GROUP BY d.device_key, m.metric_key
            ORDER BY d.device_key, m.metric_key
        ''')
        print_table('MEASUREMENT COVERAGE',
                    ['device_key','metric_key','samples','first_ts','last_ts','min_res_s','max_res_s','qualities'],
                    coverage)

        hints = []
        for row in coverage:
            haystack = f'{row[0]} {row[1]}'.lower()
            if any(h in haystack for h in THERMAL_HINTS):
                hints.append(row)
        print_table('THERMAL / HONEYWELL / CV CANDIDATES',
                    ['device_key','metric_key','samples','first_ts','last_ts','min_res_s','max_res_s','qualities'],
                    hints)

        overall = rows(con, '''
            SELECT COUNT(*) AS samples, MIN(ts_utc), MAX(ts_utc)
            FROM measurements
        ''')
        print_table('OVERALL HISTORY', ['samples','first_ts','last_ts'], overall)

        print('\n=== SAFETY ===')
        print('PASS: database opened with SQLite mode=ro; no Homey API calls; no writes performed.')
    finally:
        con.close()


if __name__ == '__main__':
    main()

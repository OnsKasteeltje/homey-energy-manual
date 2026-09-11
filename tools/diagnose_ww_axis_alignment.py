#!/usr/bin/env python3
import json
from pathlib import Path

FILES = {
    'pv': Path('/home/jeroen/ems/data/pv-forecast.json'),
    'base': Path('/home/jeroen/ems/data/base-load-forecast.json'),
    'weather': Path('/home/jeroen/ems/data/weather-forecast.json'),
    'quatt': Path('/home/jeroen/ems/data/quatt-forecast.json'),
}
SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')

TS_KEYS = ('slot_start_utc','start','start_utc','timestamp','time','ts','startAt','startUtc')

def ts_of(s):
    for k in TS_KEYS:
        v=s.get(k)
        if v:
            return str(v)
    return None

def slots(path):
    d=json.loads(path.read_text())
    arr=d.get('slots') or []
    out=[ts_of(s) for s in arr]
    return d, [x for x in out if x]

loaded={}
for name,path in FILES.items():
    if not path.exists():
        print(f'{name.upper()}_MISSING={path}')
        continue
    d,t=slots(path)
    loaded[name]=(d,t)
    print(f'{name.upper()} count={len(t)} first={t[0] if t else None} last={t[-1] if t else None} generated={d.get("generated_at") or d.get("generatedAt")}')

if all(k in loaded for k in ('pv','base','quatt')):
    p=set(loaded['pv'][1]); b=set(loaded['base'][1]); q=set(loaded['quatt'][1])
    common=sorted(p & b & q)
    print(f'COMMON_PV_BASE_QUATT={len(common)}')
    for label,a,bset in (
        ('PV_NOT_QUATT',p,q),('QUATT_NOT_PV',q,p),('BASE_NOT_QUATT',b,q),('QUATT_NOT_BASE',q,b)
    ):
        diff=sorted(a-bset)
        print(f'{label}_COUNT={len(diff)}')
        for x in diff[:4]: print(f'  {x}')

if SERVICE.exists():
    print('=== SERVICE EXECSTART ORDER ===')
    for i,line in enumerate(SERVICE.read_text().splitlines()):
        if line.startswith('ExecStart='):
            print(f'{i:03d} {line}')

#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('/etc/systemd/system/ems-pv-forecast.service')
STAGED = Path('/tmp/ems-pv-forecast.service.weather-quatt-refresh')

WEATHER = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/weather-forecast/fetch_weather_forecast.py\n'
QUATT = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/quatt-forecast/build_quatt_forecast.py\n'
WW_INPUT = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/warm-water/fetch_ww_input.py\n'
MULTI_BASE = 'ExecStart=/usr/bin/python3 /home/jeroen/ems/runtime/planner/base-load/build_multiday_base_load_forecast.py\n'

for p in (
    Path('/home/jeroen/ems/runtime/planner/weather-forecast/fetch_weather_forecast.py'),
    Path('/home/jeroen/ems/runtime/planner/quatt-forecast/build_quatt_forecast.py'),
):
    if not p.exists():
        raise SystemExit(f'FAIL: missing runtime dependency {p}')

if not SERVICE.exists():
    raise SystemExit(f'FAIL: missing {SERVICE}')

text = SERVICE.read_text()

# Remove any existing weather/quatt lines first so the resulting order is deterministic.
text = text.replace(WEATHER, '')
text = text.replace(QUATT, '')

# Refresh weather and Quatt on the same planner axis in every EMS forecast run.
# Place them immediately before WW input, after PV/base forecasts are available.
if WW_INPUT in text:
    text = text.replace(WW_INPUT, WEATHER + QUATT + WW_INPUT, 1)
elif MULTI_BASE in text:
    text = text.replace(MULTI_BASE, MULTI_BASE + WEATHER + QUATT, 1)
else:
    raise SystemExit('FAIL: no safe service insertion anchor found')

lines = text.splitlines()
execs = [(i + 1, line) for i, line in enumerate(lines) if line.startswith('ExecStart=')]
idx = {line: n for n, line in execs}

weather_line = WEATHER.rstrip('\n')
quatt_line = QUATT.rstrip('\n')
ww_line = WW_INPUT.rstrip('\n')

if weather_line not in idx or quatt_line not in idx or ww_line not in idx:
    raise SystemExit('FAIL: staged service missing expected weather/quatt/WW entries')
if not (idx[weather_line] < idx[quatt_line] < idx[ww_line]):
    raise SystemExit('FAIL: unsafe weather/quatt/WW order')

STAGED.write_text(text)
print(f'STAGED_SERVICE={STAGED}')
print('PASS: weather + Quatt refresh inserted before WW planning')
print('WEATHER_INDEX=', idx[weather_line])
print('QUATT_INDEX=', idx[quatt_line])
print('WW_INPUT_INDEX=', idx[ww_line])
print('NOTE: install staged service with sudo cp, daemon-reload and start service')

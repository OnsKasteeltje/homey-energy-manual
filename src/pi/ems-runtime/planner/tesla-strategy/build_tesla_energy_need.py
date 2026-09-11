#!/usr/bin/env python3
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path('/home/jeroen/ems/data/ems-history.sqlite')
STATE = Path('/home/jeroen/ems/data/energy-state-v2.json')
WEATHER = Path('/home/jeroen/ems/data/weather-forecast.json')
OUTPUT = Path('/home/jeroen/ems/data/tesla-energy-need.json')
KWH_PER_SOC_PCT = 0.55
TARGET_SOC_PCT = 100.0
MAX_WEATHER_OFFSET_SECONDS = 60 * 60


def parse_ts(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def write(payload):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(OUTPUT)


def estimate_arrival_soc(temp_c):
    # Observed household prior supplied for this Tesla:
    # ~10% at 5 C, ~20% at 15 C, ~30% at 25 C.
    # Linear interpolation, clamped to the observed prior range.
    return max(10.0, min(30.0, 10.0 + (temp_c - 5.0)))


def weather_temperature_near(session_start):
    if not WEATHER.exists():
        return None

    try:
        payload = json.loads(WEATHER.read_text())
    except Exception:
        return None

    if (payload.get('location') or {}).get('name') != 'Hauwert':
        return None

    target = parse_ts(session_start)
    best = None

    for slot in payload.get('slots') or []:
        value = slot.get('temperature_2m_c')
        start = slot.get('start')
        if value is None or not start:
            continue
        try:
            dt = parse_ts(start)
            offset_s = abs((dt - target).total_seconds())
            temp_c = float(value)
        except Exception:
            continue
        if best is None or offset_s < best['offset_s']:
            best = {
                'temperature_c': temp_c,
                'sample_utc': start,
                'offset_s': offset_s,
                'forecast_generated_at': payload.get('generated_at'),
            }

    if best is None or best['offset_s'] > MAX_WEATHER_OFFSET_SECONDS:
        return None

    return best


def main():
    now = datetime.now(timezone.utc)
    base = {
        'schema': 'EMS_PI_TESLA_ENERGY_NEED_V0.2',
        'generatedAt': now.isoformat().replace('+00:00', 'Z'),
        'mode': 'shadow',
        'readOnly': True,
        'controlWrites': False,
        'homeyExtraReads': 0,
    }

    if not DB.exists() or not STATE.exists():
        raise SystemExit('FAIL: missing SQLite or energy-state cache')

    state = json.loads(STATE.read_text())
    tesla = state.get('tesla') or {}
    if tesla.get('connected') is not True:
        payload = {**base, 'status': 'NOT_CONNECTED', 'remainingNeedKWh': None}
        write(payload)
        print('PASS: Tesla energy-need shadow: NOT_CONNECTED')
        print('homeyExtraReads: 0')
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        # A BASELINE_CONNECTED record does not prove session start. Deliberately wait
        # for the first observed DISCONNECTED -> CONNECTED transition.
        ev = con.execute("""
            SELECT id, ts_utc, connected, event
            FROM tesla_connection_events
            WHERE event='CONNECTED'
            ORDER BY ts_utc DESC, id DESC
            LIMIT 1
        """).fetchone()

        if ev is None:
            payload = {
                **base,
                'status': 'WAITING_FOR_OBSERVED_CONNECT_EVENT',
                'remainingNeedKWh': None,
                'reason': 'BASELINE_CONNECTED_DOES_NOT_PROVE_SESSION_START'
            }
            write(payload)
            print('PASS: Tesla energy-need shadow: WAITING_FOR_OBSERVED_CONNECT_EVENT')
            print('homeyExtraReads: 0')
            return

        session_start = ev['ts_utc']
        disconnected_after = con.execute("""
            SELECT 1 FROM tesla_connection_events
            WHERE event='DISCONNECTED' AND ts_utc > ?
            LIMIT 1
        """, (session_start,)).fetchone()
        if disconnected_after:
            payload = {**base, 'status': 'NO_ACTIVE_OBSERVED_SESSION', 'remainingNeedKWh': None}
            write(payload)
            print('PASS: Tesla energy-need shadow: NO_ACTIVE_OBSERVED_SESSION')
            print('homeyExtraReads: 0')
            return

        # Use only the existing Hauwert weather forecast already produced by the
        # EMS pipeline. Do not couple Tesla energy-need estimation to Quatt history.
        weather = weather_temperature_near(session_start)
        if weather is None:
            payload = {
                **base,
                'status': 'WAITING_FOR_CONNECTION_TEMPERATURE',
                'sessionStartUtc': session_start,
                'remainingNeedKWh': None,
                'temperatureSource': 'HAUWERT_WEATHER_FORECAST'
            }
            write(payload)
            print('PASS: Tesla energy-need shadow: WAITING_FOR_CONNECTION_TEMPERATURE')
            print('temperatureSource: HAUWERT_WEATHER_FORECAST')
            print('homeyExtraReads: 0')
            return

        temp_c = weather['temperature_c']
        arrival_soc = estimate_arrival_soc(temp_c)
        initial_need = max(0.0, (TARGET_SOC_PCT - arrival_soc) * KWH_PER_SOC_PCT)

        # Integrate already-stored Tesla power samples. Rectangle integration uses the
        # source resolution when available and caps each sample at 5 minutes to avoid
        # treating large data gaps as charging. This is AC energy and therefore remains
        # an estimate, not a trusted battery-SOC measurement.
        rows = con.execute("""
            SELECT m.ts_utc, m.value_real, COALESCE(m.source_resolution_seconds, 300) AS dt_s
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            JOIN metrics x ON x.id=m.metric_id
            WHERE d.device_key='tesla'
              AND x.metric_key='electrical_power_w'
              AND m.ts_utc >= ?
              AND m.value_real IS NOT NULL
            ORDER BY m.ts_utc
        """, (session_start,)).fetchall()

        charged_ac_kwh = 0.0
        for row in rows:
            power_w = max(0.0, float(row['value_real']))
            dt_s = max(0.0, min(300.0, float(row['dt_s'] or 300)))
            charged_ac_kwh += power_w * dt_s / 3_600_000.0

        remaining = max(0.0, initial_need - charged_ac_kwh)
        payload = {
            **base,
            'status': 'ESTIMATE_AVAILABLE_NOT_YET_TRUSTED',
            'sessionStartUtc': session_start,
            'connectionTemperatureC': round(temp_c, 2),
            'connectionTemperatureSampleUtc': weather['sample_utc'],
            'connectionTemperatureForecastGeneratedAt': weather['forecast_generated_at'],
            'connectionTemperatureOffsetSeconds': int(weather['offset_s']),
            'temperatureSource': 'HAUWERT_WEATHER_FORECAST',
            'arrivalSocPriorPct': round(arrival_soc, 1),
            'targetSocPct': TARGET_SOC_PCT,
            'kWhPerSocPct': KWH_PER_SOC_PCT,
            'initialNeedKWh': round(initial_need, 3),
            'chargedAcSinceConnectKWh': round(charged_ac_kwh, 3),
            'remainingNeedKWh': round(remaining, 3),
            'remainingNeedSource': 'HAUWERT_WEATHER_ARRIVAL_SOC_PRIOR_MINUS_MEASURED_AC_CHARGE',
            'trustedForControl': False,
            'semantics': {
                'baselineNotSessionStart': True,
                'temperatureSource': 'Existing Hauwert weather-forecast.json from the EMS pipeline; no Quatt-history fallback.',
                'arrivalSocPrior': '10% at 5C, 20% at 15C, 30% at 25C; linearly interpolated and clamped.',
                'chargeEnergy': 'Integrated from existing Tesla electrical_power_w SQLite samples; no extra Homey/API read.',
                'controlUse': 'Shadow validation only until estimator accuracy is validated against real sessions.'
            }
        }
        write(payload)
        print('PASS: Tesla energy-need shadow estimate built')
        print('sessionStartUtc   :', session_start)
        print('temperatureC      :', round(temp_c, 2))
        print('temperatureSource : HAUWERT_WEATHER_FORECAST')
        print('arrivalSocPriorPct:', round(arrival_soc, 1))
        print('initialNeedKWh    :', round(initial_need, 3))
        print('chargedAcKWh      :', round(charged_ac_kwh, 3))
        print('remainingNeedKWh :', round(remaining, 3))
        print('trustedForControl : False')
        print('homeyExtraReads   : 0')
    finally:
        con.close()


if __name__ == '__main__':
    main()

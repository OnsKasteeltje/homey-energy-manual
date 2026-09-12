#!/usr/bin/env python3

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
OUTPUT = Path("/home/jeroen/ems/runtime/thermal/quatt-current.json")

HOME = Path.home()
HOMEY_PROJECT = HOME / "ems-homey-adapter"
HOMEY_CLI = HOMEY_PROJECT / "node_modules" / ".bin" / "homey"
NODE24_BIN = Path("/opt/node-v24.20.0/bin")

DEVICE_KEY = "quatt_cic"
DEVICE_ID = "1e5dcde5-c1cf-4c32-9141-33e00ce36de9"
SOURCE_RESOLUTION_SECONDS = 300

# Canonical SQLite metrics. These MUST already exist; this collector never
# extends the datastore schema implicitly.
CANONICAL = {
    "measure_power": "electrical_power_w",
    "measure_heatpump_temperature_outside.heatpump1": "outside_temperature_c",
    "measure_heatpump_temperature_outside.heatpump2": "hp2_outside_temperature_c",
    "measure_heatpump_thermal_power.heatpump1": "hp1_thermal_power_w",
    "measure_heatpump_thermal_power.heatpump2": "hp2_thermal_power_w",
    "measure_heatpump_cop.heatpump1": "hp1_cop",
    "measure_heatpump_cop.heatpump2": "hp2_cop",
    "measure_thermostat_heating_on": "heating_on",
}

# Useful observer-only signals retained in the JSON artifact. These are not
# inserted into SQLite until their canonical metric semantics are explicitly
# defined.
OBSERVER_ONLY = {
    "measure_boiler_cic_central_heating_onoff_boiler": "boilerAssistOn",
    "measure_flowmeter_water_flow_speed": "waterFlow_Lph",
    "measure_flowmeter_water_supply_temperature": "waterSupplyTemperature_C",
    "measure_thermostat_setpoint_water_supply_temperature": "waterSupplySetpoint_C",
}


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_device():
    env = os.environ.copy()
    env["PATH"] = f"{NODE24_BIN}:{env.get('PATH', '')}"
    cmd = [
        str(HOMEY_CLI),
        "api",
        "devices",
        "get-device",
        "--id",
        DEVICE_ID,
        "--json",
    ]
    result = subprocess.run(
        cmd,
        cwd=HOMEY_PROJECT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Homey get-device failed: {err}")
    return json.loads(result.stdout)


def capability(caps, key):
    obj = caps.get(key)
    if not isinstance(obj, dict):
        return None
    return {
        "value": obj.get("value"),
        "sourceLastUpdated": obj.get("lastUpdated"),
    }


def atomic_write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def numeric_value(value):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def main():
    if not DB.exists():
        raise RuntimeError(f"Database not found: {DB}")

    observed_at = now_utc_iso()
    device = fetch_device()
    caps = device.get("capabilitiesObj") or {}

    canonical_state = {}
    for capability_key, metric_key in CANONICAL.items():
        canonical_state[metric_key] = capability(caps, capability_key)

    observer_state = {}
    for capability_key, output_key in OBSERVER_ONLY.items():
        observer_state[output_key] = capability(caps, capability_key)

    payload = {
        "schema": "EMS_QUATT_CURRENT_STATE_V0.1",
        "generatedAt": observed_at,
        "mode": "READ_ONLY",
        "source": "HOMEY_DEVICE_CURRENT_STATE",
        "sourceCallCount": 1,
        "device": {
            "deviceKey": DEVICE_KEY,
            "homeyDeviceId": DEVICE_ID,
            "name": device.get("name"),
            "available": device.get("available"),
            "ready": device.get("ready"),
            "lastSeenAt": device.get("lastSeenAt"),
        },
        "canonical": canonical_state,
        "observerOnly": observer_state,
    }

    con = sqlite3.connect(DB)
    try:
        row = con.execute(
            "SELECT id FROM devices WHERE device_key=?",
            (DEVICE_KEY,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Unknown canonical device_key: {DEVICE_KEY}")
        device_db_id = row[0]

        metric_ids = {}
        for metric_key in CANONICAL.values():
            row = con.execute(
                "SELECT id FROM metrics WHERE metric_key=?",
                (metric_key,),
            ).fetchone()
            if not row:
                raise RuntimeError(f"Missing canonical metric_key: {metric_key}")
            metric_ids[metric_key] = row[0]

        attempted = 0
        inserted = 0
        skipped_null = 0

        for metric_key, state in canonical_state.items():
            attempted += 1
            if not state:
                skipped_null += 1
                continue
            value = numeric_value(state.get("value"))
            if value is None:
                skipped_null += 1
                continue

            cur = con.execute(
                """
                INSERT OR IGNORE INTO measurements
                (
                    ts_utc,
                    device_id,
                    metric_id,
                    value_real,
                    quality,
                    source_resolution_seconds
                )
                VALUES (?, ?, ?, ?, 'observed', ?)
                """,
                (
                    observed_at,
                    device_db_id,
                    metric_ids[metric_key],
                    value,
                    SOURCE_RESOLUTION_SECONDS,
                ),
            )
            inserted += cur.rowcount

        con.commit()
    finally:
        con.close()

    # Only publish the current-state artifact after both the Homey read and the
    # canonical database write have completed successfully.
    atomic_write_json(OUTPUT, payload)

    print(
        f"PASS: schema={payload['schema']} observedAt={observed_at} "
        f"attempted={attempted} inserted={inserted} skipped_null={skipped_null}"
    )
    print(f"output={OUTPUT}")
    print(
        "heating_on="
        f"{(canonical_state.get('heating_on') or {}).get('value')} "
        "boilerAssistOn="
        f"{(observer_state.get('boilerAssistOn') or {}).get('value')}"
    )


if __name__ == "__main__":
    main()

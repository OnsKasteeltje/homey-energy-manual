#!/usr/bin/env python3

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")

HOME = Path.home()
HOMEY_PROJECT = HOME / "ems-homey-adapter"
HOMEY_CLI = HOMEY_PROJECT / "node_modules" / ".bin" / "homey"
NODE24_BIN = Path("/opt/node-v24.20.0/bin")

DEVICE_KEY = "quatt_cic"
DEVICE_ID = "1e5dcde5-c1cf-4c32-9141-33e00ce36de9"
URI = f"homey:device:{DEVICE_ID}"

RESOLUTION = "last24Hours"
SOURCE_RESOLUTION_SECONDS = 300

LOGS = [
    {
        "metric_key": "electrical_power_w",
        "log_id": f"{URI}:energy_power",
    },
    {
        "metric_key": "outside_temperature_c",
        "log_id": f"{URI}:measure_heatpump_temperature_outside.heatpump1",
    },
    {
        "metric_key": "hp2_outside_temperature_c",
        "log_id": f"{URI}:measure_heatpump_temperature_outside.heatpump2",
    },
    {
        "metric_key": "hp1_thermal_power_w",
        "log_id": f"{URI}:measure_heatpump_thermal_power.heatpump1",
    },
    {
        "metric_key": "hp2_thermal_power_w",
        "log_id": f"{URI}:measure_heatpump_thermal_power.heatpump2",
    },
    {
        "metric_key": "hp1_cop",
        "log_id": f"{URI}:measure_heatpump_cop.heatpump1",
    },
    {
        "metric_key": "hp2_cop",
        "log_id": f"{URI}:measure_heatpump_cop.heatpump2",
    },
]


def fetch(log_id):
    env = os.environ.copy()
    env["PATH"] = f"{NODE24_BIN}:{env.get('PATH', '')}"

    cmd = [
        str(HOMEY_CLI),
        "api",
        "insights",
        "get-log-entries",
        "--uri",
        URI,
        "--id",
        log_id,
        "--resolution",
        RESOLUTION,
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

        if "429" in err:
            print("FAIL: Homey rate limit (429); collector stopped", file=sys.stderr)
        else:
            print(f"FAIL: Homey read failed: {err}", file=sys.stderr)

        raise RuntimeError("Homey Insights read failed")

    return json.loads(result.stdout)


def get_values(payload):
    if isinstance(payload, dict) and isinstance(payload.get("values"), list):
        return payload["values"]

    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        return payload["entries"]

    if isinstance(payload, list):
        return payload

    raise ValueError("Unexpected Homey Insights response")


def main():
    if not DB.exists():
        raise RuntimeError(f"Database not found: {DB}")

    con = sqlite3.connect(DB)

    try:
        device = con.execute(
            "SELECT id FROM devices WHERE device_key=?",
            (DEVICE_KEY,),
        ).fetchone()

        if not device:
            raise RuntimeError(f"Unknown device_key: {DEVICE_KEY}")

        device_db_id = device[0]

        total_fetched = 0
        total_inserted = 0
        total_gaps = 0

        for spec in LOGS:
            metric = con.execute(
                "SELECT id FROM metrics WHERE metric_key=?",
                (spec["metric_key"],),
            ).fetchone()

            if not metric:
                raise RuntimeError(f"Unknown metric_key: {spec['metric_key']}")

            metric_id = metric[0]

            payload = fetch(spec["log_id"])
            values = get_values(payload)

            fetched = len(values)
            inserted = 0
            gaps = 0

            for item in values:
                ts = item.get("t")
                value = item.get("v")

                if not ts:
                    continue

                if value is None:
                    gaps += 1
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
                        ts,
                        device_db_id,
                        metric_id,
                        float(value),
                        SOURCE_RESOLUTION_SECONDS,
                    ),
                )

                inserted += cur.rowcount

            con.commit()

            total_fetched += fetched
            total_inserted += inserted
            total_gaps += gaps

            print(
                f"{spec['metric_key']}: "
                f"fetched={fetched} inserted={inserted} gaps={gaps}"
            )

        print(
            f"PASS: fetched={total_fetched} "
            f"inserted={total_inserted} gaps={total_gaps}"
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()

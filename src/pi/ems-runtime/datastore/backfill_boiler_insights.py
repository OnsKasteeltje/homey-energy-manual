#!/usr/bin/env python3

import json
import os
import sqlite3
import subprocess
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")

HOME = Path.home()
HOMEY_PROJECT = HOME / "ems-homey-adapter"
HOMEY_CLI = HOMEY_PROJECT / "node_modules" / ".bin" / "homey"
NODE24_BIN = Path("/opt/node-v24.20.0/bin")

DEVICE_KEY = "boiler"
DEVICE_ID = "8238b270-21a2-4284-aa78-6b9b58d254ab"
URI = f"homey:device:{DEVICE_ID}"
LOG_ID = f"{URI}:energy_power"
METRIC_KEY = "electrical_power_w"

LAYERS = [
    ("last6Months", 604800),
    ("last3Months", 21600),
    ("last7Days", 3600),
    ("last6Hours", 60),
]


def fetch(resolution):
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
        LOG_ID,
        "--resolution",
        resolution,
        "--json",
    ]

    result = subprocess.run(
        cmd,
        cwd=HOMEY_PROJECT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(result.stdout)


def main():
    con = sqlite3.connect(DB)

    try:
        device_id = con.execute(
            "SELECT id FROM devices WHERE device_key=?",
            (DEVICE_KEY,),
        ).fetchone()[0]

        metric_id = con.execute(
            "SELECT id FROM metrics WHERE metric_key=?",
            (METRIC_KEY,),
        ).fetchone()[0]

        for resolution, source_seconds in LAYERS:
            payload = fetch(resolution)
            values = payload.get("values", [])

            inserted = 0
            upgraded = 0
            skipped = 0

            for item in values:
                ts = item.get("t")
                value = item.get("v")

                if not ts or value is None:
                    continue

                existing = con.execute(
                    """
                    SELECT source_resolution_seconds
                    FROM measurements
                    WHERE ts_utc=? AND device_id=? AND metric_id=?
                    """,
                    (ts, device_id, metric_id),
                ).fetchone()

                if existing is None:
                    con.execute(
                        """
                        INSERT INTO measurements
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
                            device_id,
                            metric_id,
                            float(value),
                            source_seconds,
                        ),
                    )
                    inserted += 1

                elif existing[0] is None or source_seconds < existing[0]:
                    con.execute(
                        """
                        UPDATE measurements
                        SET value_real=?,
                            quality='observed',
                            source_resolution_seconds=?
                        WHERE ts_utc=? AND device_id=? AND metric_id=?
                        """,
                        (
                            float(value),
                            source_seconds,
                            ts,
                            device_id,
                            metric_id,
                        ),
                    )
                    upgraded += 1

                else:
                    skipped += 1

            con.commit()

            print(
                f"{resolution}: fetched={len(values)} "
                f"inserted={inserted} upgraded={upgraded} skipped={skipped}"
            )

        print("PASS: boiler history backfill complete")

    finally:
        con.close()


if __name__ == "__main__":
    main()

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

METRIC_KEY = "electrical_power_w"

DEVICES = [
    {
        "device_key": "grid_p1",
        "device_id": "7a696d77-15fb-4b68-9bce-f1e39bff5045",
        "capability": "measure_power",
    },
    {
        "device_key": "pv_solaredge",
        "device_id": "c52c1c1d-9080-4a3b-b2e0-acc1eed7bf20",
        "capability": "measure_power",
    },
    {
        "device_key": "pv_goodwe4200",
        "device_id": "9f55af14-a080-4129-8887-c81b95f649bb",
        "capability": "measure_power",
    },
    {
        "device_key": "pv_goodwe2000",
        "device_id": "cbb98288-1c44-4718-9a66-13709b9d0172",
        "capability": "measure_power",
    },
]

# Coarse-to-fine layering: older history remains available at the resolution
# Homey exposes for that horizon, while newer overlapping points are upgraded
# to the finer source resolution.
LAYERS = [
    ("last6Months", 604800),
    ("last3Months", 21600),
    ("last7Days", 3600),
    ("last6Hours", 60),
]


def fetch(uri: str, log_id: str, resolution: str):
    env = os.environ.copy()
    env["PATH"] = f"{NODE24_BIN}:{env.get('PATH', '')}"

    cmd = [
        str(HOMEY_CLI),
        "api",
        "insights",
        "get-log-entries",
        "--uri",
        uri,
        "--id",
        log_id,
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
    )

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Homey Insights read failed for {log_id} / {resolution}: {err}"
        )

    return json.loads(result.stdout)


def get_values(payload):
    if isinstance(payload, dict) and isinstance(payload.get("values"), list):
        return payload["values"]
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        return payload["entries"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Unexpected Homey Insights response")


def upsert_layer(con, device_db_id: int, metric_id: int, values, source_seconds: int):
    inserted = 0
    upgraded = 0
    skipped = 0
    gaps = 0

    for item in values:
        ts = item.get("t")
        value = item.get("v")

        if not ts:
            continue
        if value is None:
            gaps += 1
            continue

        existing = con.execute(
            """
            SELECT source_resolution_seconds
            FROM measurements
            WHERE ts_utc=? AND device_id=? AND metric_id=?
            """,
            (ts, device_db_id, metric_id),
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
                (ts, device_db_id, metric_id, float(value), source_seconds),
            )
            inserted += 1
        elif existing[0] is None or source_seconds < existing[0]:
            con.execute(
                """
                UPDATE measurements
                SET value_real=?, quality='observed', source_resolution_seconds=?
                WHERE ts_utc=? AND device_id=? AND metric_id=?
                """,
                (float(value), source_seconds, ts, device_db_id, metric_id),
            )
            upgraded += 1
        else:
            skipped += 1

    return inserted, upgraded, skipped, gaps


def main():
    if not DB.exists():
        raise RuntimeError(f"Database not found: {DB}")

    con = sqlite3.connect(DB)

    try:
        metric = con.execute(
            "SELECT id FROM metrics WHERE metric_key=?",
            (METRIC_KEY,),
        ).fetchone()
        if not metric:
            raise RuntimeError(f"Unknown metric_key: {METRIC_KEY}")
        metric_id = metric[0]

        grand_inserted = 0
        grand_upgraded = 0
        grand_skipped = 0
        grand_gaps = 0

        for spec in DEVICES:
            device = con.execute(
                "SELECT id FROM devices WHERE device_key=?",
                (spec["device_key"],),
            ).fetchone()
            if not device:
                raise RuntimeError(f"Unknown device_key: {spec['device_key']}")
            device_db_id = device[0]

            uri = f"homey:device:{spec['device_id']}"
            log_id = f"{uri}:{spec['capability']}"

            print(f"=== {spec['device_key']} ===")

            for resolution, source_seconds in LAYERS:
                payload = fetch(uri, log_id, resolution)
                values = get_values(payload)

                inserted, upgraded, skipped, gaps = upsert_layer(
                    con,
                    device_db_id,
                    metric_id,
                    values,
                    source_seconds,
                )
                con.commit()

                grand_inserted += inserted
                grand_upgraded += upgraded
                grand_skipped += skipped
                grand_gaps += gaps

                print(
                    f"{resolution}: fetched={len(values)} "
                    f"inserted={inserted} upgraded={upgraded} "
                    f"skipped={skipped} gaps={gaps}"
                )

        print(
            "PASS: energy Insights backfill complete "
            f"inserted={grand_inserted} upgraded={grand_upgraded} "
            f"skipped={grand_skipped} gaps={grand_gaps}"
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()

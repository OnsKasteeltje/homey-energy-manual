#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

DEVICE_ID = "1e5dcde5-c1cf-4c32-9141-33e00ce36de9"
URI = f"homey:device:{DEVICE_ID}"

LOG_IDS = [
    f"{URI}:measure_heatpump_thermal_power.heatpump1",
    f"{URI}:measure_heatpump_thermal_power.heatpump2",
]

HOME = Path.home()
HOMEY_PROJECT = HOME / "ems-homey-adapter"
HOMEY_CLI = HOMEY_PROJECT / "node_modules" / ".bin" / "homey"
NODE24_BIN = Path("/opt/node-v24.20.0/bin")

NORMALIZER = Path(__file__).with_name("quatt_archive_normalize.py")


def fetch_log(log_id: str, resolution: str) -> dict:
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
        resolution,
        "--json",
    ]

    result = subprocess.run(
        cmd,
        cwd=HOMEY_PROJECT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    return json.loads(result.stdout)


def archive_log(log_id: str, resolution: str, db: Path) -> None:
    payload = fetch_log(log_id, resolution)

    values = payload.get("values", [])
    real = sum(1 for item in values if item.get("v") is not None)
    gaps = len(values) - real

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
    ) as f:
        json.dump(payload, f)
        tmp = Path(f.name)

    try:
        cmd = [
            "python3",
            str(NORMALIZER),
            "--log-id",
            log_id,
            "--resolution",
            resolution,
            "--db",
            str(db),
            str(tmp),
        ]
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        tmp.unlink(missing_ok=True)

    print(f"{log_id}")
    print(f"  fetched : {len(values)}")
    print(f"  values  : {real}")
    print(f"  gaps    : {gaps}")
    print(f"  archive : {result.stdout.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Homey -> Pi Quatt Insights archive fetcher"
    )
    parser.add_argument(
        "--resolution",
        default="last24Hours",
        help="Homey Insights resolution (default: last24Hours)",
    )
    parser.add_argument(
        "--db",
        default="data/quatt/quatt-insights.sqlite3",
        help="SQLite archive path",
    )
    args = parser.parse_args()

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)

    for log_id in LOG_IDS:
        archive_log(log_id, args.resolution, db)


if __name__ == "__main__":
    main()

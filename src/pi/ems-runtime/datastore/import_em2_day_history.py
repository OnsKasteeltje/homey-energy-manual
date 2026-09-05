#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
INPUT = Path("/home/jeroen/ems/data/homey-day-history.json")
SOURCE_RESOLUTION_SECONDS = 300

DEVICES = {
    "grid_p1": {
        "source_device_id": "em2:p1",
        "name": "P1 Grid",
        "device_type": "grid_meter",
        "field": "p1W",
    },
    "pv_solaredge": {
        "source_device_id": "em2:solaredge",
        "name": "SolarEdge",
        "device_type": "pv_inverter",
        "field": "solarEdgeW",
    },
    "pv_goodwe4200": {
        "source_device_id": "em2:goodwe4200",
        "name": "GoodWe 4200",
        "device_type": "pv_inverter",
        "field": "goodWe4200W",
    },
    "pv_goodwe2000": {
        "source_device_id": "em2:goodwe2000",
        "name": "GoodWe 2000",
        "device_type": "pv_inverter",
        "field": "goodWe2000W",
    },
}

def main():
    payload = json.loads(INPUT.read_text())
    samples = payload.get("samples")

    if not isinstance(samples, list):
        raise RuntimeError("Invalid homey-day-history.json")

    con = sqlite3.connect(DB)

    try:
        metric = con.execute(
            "SELECT id FROM metrics WHERE metric_key='electrical_power_w'"
        ).fetchone()

        if not metric:
            raise RuntimeError("Metric electrical_power_w not found")

        metric_id = metric[0]
        device_ids = {}

        for device_key, spec in DEVICES.items():
            con.execute(
                """
                INSERT OR IGNORE INTO devices
                (source, source_device_id, device_key, name, device_type)
                VALUES ('homey_em2', ?, ?, ?, ?)
                """,
                (
                    spec["source_device_id"],
                    device_key,
                    spec["name"],
                    spec["device_type"],
                ),
            )

            row = con.execute(
                "SELECT id FROM devices WHERE device_key=?",
                (device_key,),
            ).fetchone()

            device_ids[device_key] = row[0]

        inserted = 0
        skipped = 0

        for sample in samples:
            ts = sample.get("ts")
            if not ts:
                continue

            quality = "held" if sample.get("held") else "observed"

            for device_key, spec in DEVICES.items():
                value = sample.get(spec["field"])

                if value is None:
                    skipped += 1
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
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        device_ids[device_key],
                        metric_id,
                        float(value),
                        quality,
                        SOURCE_RESOLUTION_SECONDS,
                    ),
                )

                inserted += cur.rowcount

        con.commit()

        print(f"PASS: samples={len(samples)} inserted={inserted} skipped={skipped}")
        print("date:", payload.get("date_local"))

    finally:
        con.close()

if __name__ == "__main__":
    main()

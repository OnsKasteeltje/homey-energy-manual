#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
INPUT = Path("/home/jeroen/ems/data/homey-day-history.json")
SOURCE_RESOLUTION_SECONDS = 300

POWER_DEVICES = {
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
    "tesla": {
        "source_device_id": "em2:tesla",
        "name": "Tesla charging",
        "device_type": "ev_charger",
        "field": "teslaW",
    },
    "boiler": {
        "source_device_id": "em2:boiler",
        "name": "Stiebel Eltron HSTP200",
        "device_type": "water_heater",
        "field": "boilerW",
    },
}

STATE_DEVICES = {
    "washer": {
        "source_device_id": "em2:washer",
        "name": "Washing machine",
        "device_type": "appliance",
        "field": "washerActive",
    },
    "dryer": {
        "source_device_id": "em2:dryer",
        "name": "Dryer",
        "device_type": "appliance",
        "field": "dryerActive",
    },
}


def ensure_device(con, device_key, spec):
    row = con.execute(
        "SELECT id FROM devices WHERE device_key=?",
        (device_key,),
    ).fetchone()
    if row:
        return row[0]

    con.execute(
        """
        INSERT INTO devices
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
    return con.execute(
        "SELECT id FROM devices WHERE device_key=?",
        (device_key,),
    ).fetchone()[0]


def main():
    payload = json.loads(INPUT.read_text())
    samples = payload.get("samples")

    if not isinstance(samples, list):
        raise RuntimeError("Invalid homey-day-history.json")

    con = sqlite3.connect(DB)

    try:
        power_metric = con.execute(
            "SELECT id FROM metrics WHERE metric_key='electrical_power_w'"
        ).fetchone()
        if not power_metric:
            raise RuntimeError("Metric electrical_power_w not found")
        power_metric_id = power_metric[0]

        con.execute(
            """
            INSERT OR IGNORE INTO metrics
            (metric_key, unit, value_type, description)
            VALUES ('active', NULL, 'boolean', 'Device active state')
            """
        )
        active_metric_id = con.execute(
            "SELECT id FROM metrics WHERE metric_key='active'"
        ).fetchone()[0]

        power_device_ids = {
            key: ensure_device(con, key, spec)
            for key, spec in POWER_DEVICES.items()
        }
        state_device_ids = {
            key: ensure_device(con, key, spec)
            for key, spec in STATE_DEVICES.items()
        }

        inserted = 0
        skipped = 0

        for sample in samples:
            ts = sample.get("ts")
            if not ts:
                continue

            quality = "held" if sample.get("held") else "observed"

            for device_key, spec in POWER_DEVICES.items():
                if device_key == "grid_p1" and sample.get("p1Valid") is not True:
                    skipped += 1
                    continue

                value = sample.get(spec["field"])
                if value is None:
                    skipped += 1
                    continue

                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO measurements
                    (
                        ts_utc, device_id, metric_id, value_real,
                        quality, source_resolution_seconds
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        power_device_ids[device_key],
                        power_metric_id,
                        float(value),
                        quality,
                        SOURCE_RESOLUTION_SECONDS,
                    ),
                )
                inserted += cur.rowcount

            for device_key, spec in STATE_DEVICES.items():
                value = sample.get(spec["field"])
                if value is None:
                    skipped += 1
                    continue

                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO measurements
                    (
                        ts_utc, device_id, metric_id, value_real,
                        quality, source_resolution_seconds
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        state_device_ids[device_key],
                        active_metric_id,
                        1.0 if value is True else 0.0,
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

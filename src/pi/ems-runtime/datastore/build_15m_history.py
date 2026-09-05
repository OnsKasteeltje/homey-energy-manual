#!/usr/bin/env python3

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")


def floor_15m(ts):
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    dt = dt.astimezone(timezone.utc)
    minute = (dt.minute // 15) * 15
    dt = dt.replace(minute=minute, second=0, microsecond=0)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def main():
    con = sqlite3.connect(DB)

    con.execute("""
        CREATE TABLE IF NOT EXISTS measurements_15m (
            slot_start_utc TEXT NOT NULL,
            device_id INTEGER NOT NULL,
            metric_id INTEGER NOT NULL,
            value_avg REAL,
            value_min REAL,
            value_max REAL,
            sample_count INTEGER NOT NULL,
            energy_wh REAL,
            quality TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (slot_start_utc, device_id, metric_id),
            FOREIGN KEY(device_id) REFERENCES devices(id),
            FOREIGN KEY(metric_id) REFERENCES metrics(id)
        )
    """)

    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_measurements_15m_device_metric_time
        ON measurements_15m(device_id, metric_id, slot_start_utc)
    """)

    rows = con.execute("""
        SELECT
            x.ts_utc,
            x.device_id,
            x.metric_id,
            x.value_real,
            x.source_resolution_seconds,
            m.metric_key
        FROM measurements x
        JOIN metrics m ON m.id = x.metric_id
        WHERE x.value_real IS NOT NULL
        AND COALESCE(x.source_resolution_seconds, 300) <= 900
        ORDER BY x.ts_utc
    """).fetchall()

    buckets = {}

    for ts, device_id, metric_id, value, resolution, metric_key in rows:
        key = (floor_15m(ts), device_id, metric_id, metric_key)
        buckets.setdefault(key, []).append(
            (float(value), resolution or 300)
        )

    written = 0

    for (slot, device_id, metric_id, metric_key), samples in buckets.items():
        values = [v for v, _ in samples]

        avg = sum(values) / len(values)
        minimum = min(values)
        maximum = max(values)
        count = len(values)

        energy_wh = None
        if metric_key.endswith("_power_w"):
            energy_wh = sum(
                value * resolution / 3600.0
                for value, resolution in samples
            )

        quality = "complete" if count >= 3 else "partial"

        con.execute("""
            INSERT INTO measurements_15m (
                slot_start_utc,
                device_id,
                metric_id,
                value_avg,
                value_min,
                value_max,
                sample_count,
                energy_wh,
                quality
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slot_start_utc, device_id, metric_id)
            DO UPDATE SET
                value_avg=excluded.value_avg,
                value_min=excluded.value_min,
                value_max=excluded.value_max,
                sample_count=excluded.sample_count,
                energy_wh=excluded.energy_wh,
                quality=excluded.quality,
                updated_at_utc=CURRENT_TIMESTAMP
        """, (
            slot,
            device_id,
            metric_id,
            avg,
            minimum,
            maximum,
            count,
            energy_wh,
            quality,
        ))

        written += 1

    con.commit()

    print(f"PASS: aggregated_slots={written}")

    for row in con.execute("""
        SELECT
            m.metric_key,
            COUNT(*),
            SUM(CASE WHEN x.quality='complete' THEN 1 ELSE 0 END),
            SUM(CASE WHEN x.quality='partial' THEN 1 ELSE 0 END),
            MIN(x.slot_start_utc),
            MAX(x.slot_start_utc)
        FROM measurements_15m x
        JOIN metrics m ON m.id=x.metric_id
        JOIN devices d ON d.id=x.device_id
        WHERE d.device_key='quatt_cic'
        GROUP BY m.metric_key
        ORDER BY m.metric_key
    """):
        print(row)

    con.close()


if __name__ == "__main__":
    main()

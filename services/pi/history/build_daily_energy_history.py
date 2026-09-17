#!/usr/bin/env python3

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
TZ = ZoneInfo("Europe/Amsterdam")

TARGETS = [
    ("boiler", "electrical_power_w"),
]

def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)

def main():
    con = sqlite3.connect(DB)

    con.execute("""
    CREATE TABLE IF NOT EXISTS daily_energy_history (
        local_date TEXT NOT NULL,
        device_id INTEGER NOT NULL,
        metric_id INTEGER NOT NULL,
        energy_kwh REAL,
        coverage_pct REAL,
        best_resolution_seconds INTEGER,
        worst_resolution_seconds INTEGER,
        sample_count INTEGER NOT NULL,
        quality TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (local_date, device_id, metric_id),
        FOREIGN KEY(device_id) REFERENCES devices(id),
        FOREIGN KEY(metric_id) REFERENCES metrics(id)
    )
    """)

    con.execute("""
    CREATE INDEX IF NOT EXISTS idx_daily_energy_history_device_metric_date
    ON daily_energy_history(device_id, metric_id, local_date)
    """)

    written = 0

    for device_key, metric_key in TARGETS:
        row = con.execute("""
            SELECT d.id, m.id
            FROM devices d
            JOIN metrics m
            WHERE d.device_key=? AND m.metric_key=?
        """, (device_key, metric_key)).fetchone()

        if not row:
            print(f"SKIP: {device_key}/{metric_key} not found")
            continue

        device_id, metric_id = row

        samples = con.execute("""
            SELECT ts_utc, value_real, source_resolution_seconds
            FROM measurements
            WHERE device_id=?
              AND metric_id=?
              AND value_real IS NOT NULL
              AND source_resolution_seconds IS NOT NULL
            ORDER BY ts_utc
        """, (device_id, metric_id)).fetchall()

        # Build minute buckets. Finest source resolution wins where sources overlap.
        minute_map = {}

        for ts_utc, value, resolution in samples:
            resolution = int(resolution)

            # Daily energy may use source data up to 6-hour resolution.
            # Weekly Homey aggregates must never be expanded into daily coverage.
            if resolution > 21600:
                continue

            end = parse_ts(ts_utc)
            start = end - timedelta(seconds=resolution)

            cur = start.replace(second=0, microsecond=0)

            while cur < end:
                nxt = cur + timedelta(minutes=1)

                overlap_start = max(cur, start)
                overlap_end = min(nxt, end)
                seconds = max(0.0, (overlap_end - overlap_start).total_seconds())

                if seconds > 0:
                    key = cur
                    existing = minute_map.get(key)

                    candidate = {
                        "value": float(value),
                        "resolution": resolution,
                        "seconds": seconds,
                    }

                    if existing is None or resolution < existing["resolution"]:
                        minute_map[key] = candidate

                cur = nxt

        by_day = defaultdict(list)

        for minute_utc, item in minute_map.items():
            local_date = minute_utc.astimezone(TZ).date().isoformat()
            by_day[local_date].append(item)

        for local_date, items in sorted(by_day.items()):
            seconds_covered = sum(x["seconds"] for x in items)
            energy_wh = sum(
                x["value"] * x["seconds"] / 3600.0
                for x in items
            )

            local_start = datetime.fromisoformat(local_date).replace(tzinfo=TZ)
            local_end = local_start + timedelta(days=1)
            day_seconds = (
                local_end.astimezone(timezone.utc)
                - local_start.astimezone(timezone.utc)
            ).total_seconds()

            coverage_pct = 100.0 * seconds_covered / day_seconds
            best_resolution = min(x["resolution"] for x in items)
            worst_resolution = max(x["resolution"] for x in items)

            if coverage_pct >= 95:
                quality = "complete"
            elif coverage_pct >= 75:
                quality = "usable"
            else:
                quality = "partial"

            con.execute("""
                INSERT INTO daily_energy_history (
                    local_date,
                    device_id,
                    metric_id,
                    energy_kwh,
                    coverage_pct,
                    best_resolution_seconds,
                    worst_resolution_seconds,
                    sample_count,
                    quality
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_date, device_id, metric_id)
                DO UPDATE SET
                    energy_kwh=excluded.energy_kwh,
                    coverage_pct=excluded.coverage_pct,
                    best_resolution_seconds=excluded.best_resolution_seconds,
                    worst_resolution_seconds=excluded.worst_resolution_seconds,
                    sample_count=excluded.sample_count,
                    quality=excluded.quality,
                    updated_at_utc=CURRENT_TIMESTAMP
            """, (
                local_date,
                device_id,
                metric_id,
                energy_wh / 1000.0,
                coverage_pct,
                best_resolution,
                worst_resolution,
                len(items),
                quality,
            ))

            written += 1

    con.commit()

    print(f"PASS: daily rows={written}")

    for row in con.execute("""
        SELECT
            h.local_date,
            ROUND(h.energy_kwh, 2),
            ROUND(h.coverage_pct, 1),
            h.best_resolution_seconds,
            h.quality
        FROM daily_energy_history h
        JOIN devices d ON d.id=h.device_id
        JOIN metrics m ON m.id=h.metric_id
        WHERE d.device_key='boiler'
          AND m.metric_key='electrical_power_w'
        ORDER BY h.local_date DESC
        LIMIT 20
    """):
        print(row)

    con.close()

if __name__ == "__main__":
    main()

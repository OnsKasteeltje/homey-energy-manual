#!/usr/bin/env python3

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
SLOT_SECONDS = 15 * 60
DEFAULT_SOURCE_RESOLUTION_SECONDS = 300
COMPLETE_COVERAGE_RATIO = 0.95


def parse_ts(ts):
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"timestamp must be offset-aware: {ts}")
    return dt.astimezone(timezone.utc)


def floor_15m_dt(dt):
    dt = dt.astimezone(timezone.utc)
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


def floor_15m(ts):
    return floor_15m_dt(parse_ts(ts)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _resolution_seconds(value):
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SOURCE_RESOLUTION_SECONDS
    if seconds <= 0:
        return DEFAULT_SOURCE_RESOLUTION_SECONDS
    return seconds


def aggregate_power_series(samples, *, now=None):
    """Aggregate one power series using actual elapsed time.

    source_resolution_seconds is the maximum validity horizon of a sample, not
    the duration that every stored row represents. Each sample therefore holds
    until the next sample or its validity horizon, whichever comes first.
    Segments are split at quarter-hour boundaries.
    """
    parsed = sorted(
        (
            parse_ts(ts),
            float(value),
            _resolution_seconds(resolution),
        )
        for ts, value, resolution in samples
    )
    if not parsed:
        return {}

    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    buckets = defaultdict(
        lambda: {
            "sample_values": [],
            "coverage_seconds": 0.0,
            "weighted_value_seconds": 0.0,
            "segment_values": [],
            "energy_wh": 0.0,
        }
    )

    # Preserve raw-sample count semantics for observability.
    for ts, value, _ in parsed:
        buckets[floor_15m_dt(ts)]["sample_values"].append(value)

    for index, (ts, value, resolution) in enumerate(parsed):
        next_ts = (
            parsed[index + 1][0]
            if index + 1 < len(parsed)
            else now
        )
        valid_until = ts + timedelta(seconds=resolution)
        end = min(next_ts, valid_until, now)
        if end <= ts:
            continue

        cursor = ts
        while cursor < end:
            bucket = floor_15m_dt(cursor)
            bucket_end = bucket + timedelta(seconds=SLOT_SECONDS)
            segment_end = min(end, bucket_end)
            seconds = (segment_end - cursor).total_seconds()
            if seconds <= 0:
                break

            item = buckets[bucket]
            item["coverage_seconds"] += seconds
            item["weighted_value_seconds"] += value * seconds
            item["segment_values"].append(value)
            item["energy_wh"] += value * seconds / 3600.0
            cursor = segment_end

    result = {}
    complete_seconds = SLOT_SECONDS * COMPLETE_COVERAGE_RATIO

    for bucket, item in buckets.items():
        sample_values = item["sample_values"]
        segment_values = item["segment_values"]
        coverage = item["coverage_seconds"]

        if coverage > 0:
            value_avg = (
                item["weighted_value_seconds"] / coverage
            )
            extrema = segment_values
        else:
            # No elapsed interval can be proven yet (for example a just-arrived
            # latest sample). Keep sample statistics but do not invent energy.
            value_avg = (
                sum(sample_values) / len(sample_values)
                if sample_values
                else None
            )
            extrema = sample_values

        result[bucket] = {
            "value_avg": value_avg,
            "value_min": min(extrema) if extrema else None,
            "value_max": max(extrema) if extrema else None,
            "sample_count": len(sample_values),
            "energy_wh": item["energy_wh"],
            "coverage_seconds": coverage,
            "quality": (
                "complete"
                if coverage >= complete_seconds
                else "partial"
            ),
        }

    return result


def aggregate_non_power_series(samples):
    buckets = defaultdict(list)
    for ts, value, _resolution in samples:
        buckets[floor_15m(ts)].append(float(value))

    result = {}
    for slot, values in buckets.items():
        result[slot] = {
            "value_avg": sum(values) / len(values),
            "value_min": min(values),
            "value_max": max(values),
            "sample_count": len(values),
            "energy_wh": None,
            "quality": "complete" if len(values) >= 3 else "partial",
        }
    return result


def ensure_schema(con):
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


def rebuild(con, *, now=None):
    ensure_schema(con)

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
        ORDER BY x.device_id, x.metric_id, x.ts_utc
    """).fetchall()

    series = defaultdict(list)
    metric_keys = {}
    for ts, device_id, metric_id, value, resolution, metric_key in rows:
        key = (device_id, metric_id)
        series[key].append((ts, value, resolution))
        metric_keys[key] = metric_key

    generated = []
    for (device_id, metric_id), samples in series.items():
        metric_key = metric_keys[(device_id, metric_id)]
        if metric_key.endswith("_power_w"):
            aggregates = aggregate_power_series(
                samples,
                now=now,
            )
            for bucket, item in aggregates.items():
                generated.append(
                    (
                        bucket.isoformat(timespec="seconds").replace(
                            "+00:00", "Z"
                        ),
                        device_id,
                        metric_id,
                        item["value_avg"],
                        item["value_min"],
                        item["value_max"],
                        item["sample_count"],
                        item["energy_wh"],
                        item["quality"],
                    )
                )
        else:
            aggregates = aggregate_non_power_series(samples)
            for slot, item in aggregates.items():
                generated.append(
                    (
                        slot,
                        device_id,
                        metric_id,
                        item["value_avg"],
                        item["value_min"],
                        item["value_max"],
                        item["sample_count"],
                        item["energy_wh"],
                        item["quality"],
                    )
                )

    # measurements_15m is a deterministic derived projection. Rebuild it in one
    # transaction so obsolete values from earlier aggregation semantics cannot
    # survive, while a failure rolls the delete back.
    with con:
        con.execute("DELETE FROM measurements_15m")
        con.executemany("""
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
        """, generated)

    return len(generated)


def main():
    con = sqlite3.connect(DB)
    try:
        written = rebuild(con)
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
    finally:
        con.close()


if __name__ == "__main__":
    main()

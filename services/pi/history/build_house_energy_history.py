#!/usr/bin/env python3
"""Build household-energy intervals from cumulative Homey Core counters."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
MAX_NORMAL_GAP_SECONDS = 900
COUNTER_DECREASE_EPSILON_KWH = 1e-6
GAP_MULTIPLIER = 1.5

COUNTERS = (
    ("grid_p1", "energy_import_kwh", "import_kwh"),
    ("grid_p1", "energy_export_kwh", "export_kwh"),
    ("pv_solaredge", "energy_produced_kwh", "pv_solaredge_kwh"),
    ("pv_goodwe4200", "energy_produced_kwh", "pv_goodwe4200_kwh"),
    ("pv_goodwe2000", "energy_produced_kwh", "pv_goodwe2000_kwh"),
)


def _counter_rows(con):
    parts = []
    args = []
    for device_key, metric_key, alias in COUNTERS:
        parts.append(
            """MAX(CASE WHEN d.device_key=? AND m.metric_key=?
                     THEN x.value_real END) AS %s""" % alias
        )
        args.extend((device_key, metric_key))
    sql = f"""
        SELECT x.ts_utc, MAX(x.source_resolution_seconds), {", ".join(parts)}
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE x.value_real IS NOT NULL
          AND (
            {" OR ".join("(d.device_key=? AND m.metric_key=?)" for _ in COUNTERS)}
          )
        GROUP BY x.ts_utc
        ORDER BY x.ts_utc
    """
    for device_key, metric_key, _ in COUNTERS:
        args.extend((device_key, metric_key))
    return con.execute(sql, args).fetchall()


def _parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def build(db_path=DB):
    con = sqlite3.connect(str(db_path), timeout=2.0)
    con.execute("PRAGMA busy_timeout=2000")
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS house_energy_intervals (
                start_ts_utc TEXT NOT NULL,
                end_ts_utc TEXT NOT NULL PRIMARY KEY,
                duration_seconds INTEGER NOT NULL,
                import_kwh REAL,
                export_kwh REAL,
                pv_solaredge_kwh REAL,
                pv_goodwe4200_kwh REAL,
                pv_goodwe2000_kwh REAL,
                pv_total_kwh REAL,
                house_kwh REAL,
                quality TEXT NOT NULL,
                discontinuity_reason TEXT,
                updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_house_energy_intervals_start
            ON house_energy_intervals(start_ts_utc)
        """)

        rows = _counter_rows(con)
        # Fully derived: rebuild transactionally so obsolete intervals from
        # older derivation semantics cannot survive a corrected rebuild.
        con.execute("DELETE FROM house_energy_intervals")
        written = 0
        previous = None

        for row in rows:
            ts, source_resolution_seconds, *values = row
            if any(value is None for value in values):
                # Cumulative counters permit bridging incomplete intermediate snapshots.
                # Retain the last complete baseline; the next complete point forms the
                # interval and is quality-marked as a gap when it exceeds 1.5x the expected source resolution.
                continue
            values = tuple(float(value) for value in values)

            if previous is None:
                previous = (ts, source_resolution_seconds, values)
                continue

            prev_ts, prev_resolution, prev_values = previous
            elapsed_seconds = (_parse_utc(ts) - _parse_utc(prev_ts)).total_seconds()
            deltas = tuple(cur - old for cur, old in zip(values, prev_values))

            reason = None
            quality = "observed"
            output = deltas
            if elapsed_seconds <= 0:
                reason = "NON_FORWARD_TIME"
                seconds = 0
            elif elapsed_seconds < 1:
                # Preserve cumulative energy without inventing a one-second
                # interval: keep the earlier baseline. The next representable
                # interval absorbs any counter delta from this source sample.
                continue
            else:
                seconds = int(elapsed_seconds)

            if reason is None and any(delta < -COUNTER_DECREASE_EPSILON_KWH for delta in deltas):
                reason = "COUNTER_DECREASE"
            elif reason is None:
                expected_resolution = max(MAX_NORMAL_GAP_SECONDS, int(source_resolution_seconds or prev_resolution or MAX_NORMAL_GAP_SECONDS))
                if elapsed_seconds > expected_resolution * GAP_MULTIPLIER:
                    quality = "gap"

            if reason:
                quality = "discontinuity"
                output = (None,) * len(deltas)

            imp, exp, se, gw42, gw20 = output
            pv_total = None if se is None else se + gw42 + gw20
            house = None if imp is None else imp + pv_total - exp

            con.execute("""
                INSERT INTO house_energy_intervals (
                    start_ts_utc, end_ts_utc, duration_seconds,
                    import_kwh, export_kwh,
                    pv_solaredge_kwh, pv_goodwe4200_kwh, pv_goodwe2000_kwh,
                    pv_total_kwh, house_kwh, quality, discontinuity_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(end_ts_utc) DO UPDATE SET
                    start_ts_utc=excluded.start_ts_utc,
                    duration_seconds=excluded.duration_seconds,
                    import_kwh=excluded.import_kwh,
                    export_kwh=excluded.export_kwh,
                    pv_solaredge_kwh=excluded.pv_solaredge_kwh,
                    pv_goodwe4200_kwh=excluded.pv_goodwe4200_kwh,
                    pv_goodwe2000_kwh=excluded.pv_goodwe2000_kwh,
                    pv_total_kwh=excluded.pv_total_kwh,
                    house_kwh=excluded.house_kwh,
                    quality=excluded.quality,
                    discontinuity_reason=excluded.discontinuity_reason,
                    updated_at_utc=CURRENT_TIMESTAMP
            """, (prev_ts, ts, seconds, imp, exp, se, gw42, gw20,
                  pv_total, house, quality, reason))
            written += 1
            previous = (ts, source_resolution_seconds, values)

        con.commit()
        return {"rows": written, "counter_snapshots": len(rows)}
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB))
    args = parser.parse_args()
    result = build(Path(args.db))
    print(f"PASS: house_energy_intervals={result['rows']} counter_snapshots={result['counter_snapshots']}")


if __name__ == "__main__":
    main()

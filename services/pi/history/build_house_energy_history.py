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
MAX_PV_INTERPOLATION_SECONDS = 3 * 3600
# Close-in-time duplicate samples are not material interpolation anchors.
MIN_MATERIAL_PV_INTERIOR_SECONDS = 5.0

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
        SELECT x.ts_utc,
               MAX(x.source_resolution_seconds),
               MAX(CASE WHEN x.quality='held' THEN 1 ELSE 0 END) AS has_held_input,
               {", ".join(parts)},
               {", ".join(
                   "MAX(CASE WHEN d.device_key='%s' AND m.metric_key='energy_produced_kwh' "
                   "THEN CASE WHEN x.quality='observed' THEN 1 ELSE 0 END END) AS %s_observed"
                   % (key, key)
                   for key in ("pv_solaredge", "pv_goodwe4200", "pv_goodwe2000")
               )}
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE x.value_real IS NOT NULL
          AND x.quality IN ('observed','held')
          AND (
            {" OR ".join("(d.device_key=? AND m.metric_key=?)" for _ in COUNTERS)}
          )
        GROUP BY x.ts_utc
        -- Source timestamps can mix ISO precision (Z vs .481Z).
        -- Lexicographic ordering incorrectly places .481Z before Z,
        -- creating a false non-forward-time discontinuity.
        ORDER BY julianday(x.ts_utc), x.ts_utc
    """
    for device_key, metric_key, _ in COUNTERS:
        args.extend((device_key, metric_key))
    return con.execute(sql, args).fetchall()


def _parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)



def _reconcile_held_pv(rows):
    """Time-attribute sparse cumulative PV changes without shifting P1 data.

    Even 'observed' cumulative readings can repeat a cached inverter value.
    A positive increase is distributed between the last distinct observed
    reading and the next distinct observed reading; held values are never
    used as anchors. Unknown gaps stay gaps, not synthetic power spikes.
    """
    projected = [list(row) for row in rows]
    invalid_ends = set()
    reconstructed_ends = set()
    withheld_pv_ends = {5: set(), 6: set(), 7: set()}  # per inverter
    for value_index, quality_index in ((5, 8), (6, 9), (7, 10)):
        anchors = []
        last_value = None
        for i, row in enumerate(rows):
            value = row[value_index]
            if value is None or row[quality_index] != 1:
                continue
            value = float(value)
            if last_value is None or abs(value - last_value) > COUNTER_DECREASE_EPSILON_KWH:
                anchors.append(i)
                last_value = value
        for left, right in zip(anchors, anchors[1:]):
            a, b = rows[left], rows[right]
            duration = (_parse_utc(b[0]) - _parse_utc(a[0])).total_seconds()
            delta = float(b[value_index]) - float(a[value_index])
            if duration <= 0 or delta < -COUNTER_DECREASE_EPSILON_KWH:
                continue
            if duration > MAX_PV_INTERPOLATION_SECONDS and delta > 0:
                # A PV reading resuming after a long sleep cannot time-locate
                # production. Do not attribute energy into arbitrary night slots.
                invalid_ends.update(range(left + 1, right + 1))
                withheld_pv_ends[value_index].update(range(left + 1, right + 1))
                continue
            # All covered intermediate endpoints are estimates, including
            # repeated 'observed' counter values. Preserve the total energy.
            for i in range(left + 1, right):
                elapsed = (_parse_utc(rows[i][0]) - _parse_utc(a[0])).total_seconds()
                projected[i][value_index] = float(a[value_index]) + delta * elapsed / duration
            # A duplicate <5s from an anchor must not relabel an otherwise
            # fully observed 5-minute interval as reconstructed/held. Genuine
            # intermediate observations (e.g. 5-minute stale readings between
            # a 10-minute delta) still require estimated quality.
            if any(
                (_parse_utc(rows[i][0]) - _parse_utc(a[0])).total_seconds()
                >= MIN_MATERIAL_PV_INTERIOR_SECONDS
                and (_parse_utc(b[0]) - _parse_utc(rows[i][0])).total_seconds()
                >= MIN_MATERIAL_PV_INTERIOR_SECONDS
                for i in range(left + 1, right)
            ):
                reconstructed_ends.update(range(left + 1, right + 1))
    return projected, invalid_ends, reconstructed_ends, withheld_pv_ends

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
                p1_quality TEXT NOT NULL DEFAULT 'unknown',
                pv_quality TEXT NOT NULL DEFAULT 'unknown',
                discontinuity_reason TEXT,
                updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        existing_columns = {x[1] for x in con.execute("PRAGMA table_info(house_energy_intervals)")}
        for column in ("p1_quality", "pv_quality"):
            if column not in existing_columns:
                con.execute(
                    f"ALTER TABLE house_energy_intervals ADD COLUMN {column} TEXT NOT NULL DEFAULT 'unknown'"
                )
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_house_energy_intervals_start
            ON house_energy_intervals(start_ts_utc)
        """)

        rows, invalid_pv_ends, reconstructed_pv_ends, withheld_pv_ends = _reconcile_held_pv(_counter_rows(con))
        # Fully derived: rebuild transactionally so obsolete intervals from
        # older derivation semantics cannot survive a corrected rebuild.
        con.execute("DELETE FROM house_energy_intervals")
        written = 0
        previous = None

        for row_index, row in enumerate(rows):
            ts, source_resolution_seconds, has_held_input, *values = row[:8]
            if any(value is None for value in values):
                # Cumulative counters permit bridging incomplete intermediate snapshots.
                # Retain the last complete baseline; the next complete point forms the
                # interval and is quality-marked as a gap when it exceeds 1.5x the expected source resolution.
                continue
            values = tuple(float(value) for value in values)

            if previous is None:
                previous = (ts, source_resolution_seconds, bool(has_held_input), values)
                continue

            prev_ts, prev_resolution, prev_has_held_input, prev_values = previous
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
                elif prev_has_held_input or bool(has_held_input) or row_index in reconstructed_pv_ends:
                    # Cumulative counters are monotonic state. A sleeping/stale
                    # inverter may keep exposing an unchanged total as "held".
                    # Keep the household interval instead of truncating history,
                    # but do not label the counter endpoints as freshly observed.
                    quality = "held"

            if reason:
                quality = "discontinuity"
                output = (None,) * len(deltas)

            imp, exp, se, gw42, gw20 = output
            p1_quality = "gap" if quality == "gap" else ("discontinuity" if reason else "observed")
            pv_quality = (
                "gap" if row_index in invalid_pv_ends or quality == "gap"
                else "discontinuity" if reason
                else "estimated" if row_index in reconstructed_pv_ends or quality == "held"
                else "observed"
            )
            # Preserve the raw P1 energy even where PV is not time-locatable.
            # No house energy is invented from an unknown PV allocation.
            if row_index in withheld_pv_ends[5]:
                se = None
            if row_index in withheld_pv_ends[6]:
                gw42 = None
            if row_index in withheld_pv_ends[7]:
                gw20 = None
            pv_total = None if any(v is None for v in (se, gw42, gw20)) else se + gw42 + gw20
            house = None if imp is None or pv_total is None else imp + pv_total - exp

            con.execute("""
                INSERT INTO house_energy_intervals (
                    start_ts_utc, end_ts_utc, duration_seconds,
                    import_kwh, export_kwh,
                    pv_solaredge_kwh, pv_goodwe4200_kwh, pv_goodwe2000_kwh,
                    pv_total_kwh, house_kwh, quality, p1_quality, pv_quality, discontinuity_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    p1_quality=excluded.p1_quality,
                    pv_quality=excluded.pv_quality,
                    discontinuity_reason=excluded.discontinuity_reason,
                    updated_at_utc=CURRENT_TIMESTAMP
            """, (prev_ts, ts, seconds, imp, exp, se, gw42, gw20,
                  pv_total, house, quality, p1_quality, pv_quality, reason))
            written += 1
            previous = (ts, source_resolution_seconds, bool(has_held_input), values)

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

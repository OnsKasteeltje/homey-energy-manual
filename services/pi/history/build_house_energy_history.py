#!/usr/bin/env python3
"""Build household-energy intervals from cumulative Homey Core counters."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
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

PV_COUNTERS = COUNTERS[2:]


def _counter_rows(con):
    value_parts = []
    quality_parts = []
    args = []

    for device_key, metric_key, alias in COUNTERS:
        value_parts.append(
            """MAX(CASE WHEN d.device_key=? AND m.metric_key=?
                     THEN x.value_real END) AS %s""" % alias
        )
        args.extend((device_key, metric_key))

    for device_key, metric_key, alias in PV_COUNTERS:
        quality_parts.append(
            """MAX(CASE WHEN d.device_key=? AND m.metric_key=?
                     THEN CASE WHEN x.quality='held' THEN 1 ELSE 0 END END)
               AS %s_held""" % alias
        )
        args.extend((device_key, metric_key))

    sql = f"""
        SELECT x.ts_utc,
               MAX(x.source_resolution_seconds),
               MAX(CASE WHEN x.quality='held' THEN 1 ELSE 0 END) AS has_held_input,
               {", ".join(value_parts)},
               {", ".join(quality_parts)}
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE x.value_real IS NOT NULL
          AND x.quality IN ('observed','held')
          AND (
            {" OR ".join("(d.device_key=? AND m.metric_key=?)" for _ in COUNTERS)}
          )
        GROUP BY x.ts_utc
        ORDER BY julianday(x.ts_utc), x.ts_utc
    """
    for device_key, metric_key, _ in COUNTERS:
        args.extend((device_key, metric_key))
    return con.execute(sql, args).fetchall()


def _parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _prepare_counter_rows(rows):
    """Normalize complete counter snapshots and redistribute PV plateaus.

    For each inverter independently, repeated identical cumulative readings
    followed by a positive counter step are treated as delayed counter timing.
    The exact energy delta is preserved and spread linearly over the existing
    timestamps of that plateau. This applies regardless of whether the repeated
    source samples were labelled observed or held.

    Redistribution never crosses an Amsterdam calendar-day boundary. That keeps
    a genuine overnight zero-production plateau from smearing the next morning's
    first production backward into the night.
    """
    value_count = len(COUNTERS)
    pv_count = len(PV_COUNTERS)
    prepared = []

    for row in rows:
        ts, source_resolution_seconds, has_held_input, *rest = row
        values = rest[:value_count]
        pv_held = rest[value_count:value_count + pv_count]
        if any(value is None for value in values):
            continue

        prepared.append({
            "ts": ts,
            "source_resolution_seconds": source_resolution_seconds,
            "has_held_input": bool(has_held_input),
            "values": [float(value) for value in values],
            "pv_held": [bool(value) for value in pv_held],
            "pv_estimated_interval": False,
        })

    # Values 0..1 are P1 import/export; PV values start at index 2.
    for pv_offset in range(pv_count):
        value_index = 2 + pv_offset
        raw_values = [item["values"][value_index] for item in prepared]

        for index in range(1, len(prepared)):
            previous_value = raw_values[index - 1]
            current_value = raw_values[index]
            delta = current_value - previous_value

            if delta <= COUNTER_DECREASE_EPSILON_KWH:
                continue

            # Walk back over the unchanged cumulative plateau immediately
            # preceding this positive step.
            plateau_start = index - 1
            while (
                plateau_start > 0
                and abs(
                    raw_values[plateau_start]
                    - raw_values[plateau_start - 1]
                ) <= COUNTER_DECREASE_EPSILON_KWH
            ):
                plateau_start -= 1

            # A direct next-sample increment already has precise interval timing.
            if index <= plateau_start + 1:
                continue

            first = prepared[plateau_start]
            last = prepared[index]
            start_time = _parse_utc(first["ts"])
            end_time = _parse_utc(last["ts"])

            # Do not smear sunrise production backward across an overnight
            # constant counter plateau.
            if (
                start_time.astimezone(LOCAL_TZ).date()
                != end_time.astimezone(LOCAL_TZ).date()
            ):
                continue

            elapsed = (end_time - start_time).total_seconds()
            if elapsed <= 0:
                continue

            start_value = raw_values[plateau_start]
            end_value = current_value
            total_delta = end_value - start_value

            for fill_index in range(plateau_start + 1, index + 1):
                fill = prepared[fill_index]
                fraction = (
                    (_parse_utc(fill["ts"]) - start_time).total_seconds()
                    / elapsed
                )
                fill["values"][value_index] = (
                    start_value + total_delta * fraction
                )
                fill["pv_estimated_interval"] = True

    return prepared


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
        # Preserve the existing read-only PV/Flex source quality contract.
        cols = {r[1] for r in con.execute("PRAGMA table_info(house_energy_intervals)")}
        for column in ("p1_quality", "pv_quality"):
            if column not in cols:
                con.execute(f"ALTER TABLE house_energy_intervals ADD COLUMN {column} TEXT NOT NULL DEFAULT 'unknown'")
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_house_energy_intervals_start
            ON house_energy_intervals(start_ts_utc)
        """)

        rows = _counter_rows(con)
        prepared_rows = _prepare_counter_rows(rows)
        # Fully derived: rebuild transactionally so obsolete intervals from
        # older derivation semantics cannot survive a corrected rebuild.
        con.execute("DELETE FROM house_energy_intervals")
        written = 0
        previous = None

        for row in prepared_rows:
            ts = row["ts"]
            source_resolution_seconds = row["source_resolution_seconds"]
            has_held_input = row["has_held_input"]
            values = tuple(row["values"])
            pv_estimated_interval = row["pv_estimated_interval"]

            if previous is None:
                previous = (
                    ts,
                    source_resolution_seconds,
                    bool(has_held_input),
                    values,
                )
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
                elif pv_estimated_interval:
                    # At least one inverter had a repeated cumulative plateau
                    # whose next positive counter step was redistributed.
                    # Energy is known, exact intra-plateau timing is estimated.
                    quality = "estimated"
                elif prev_has_held_input or bool(has_held_input):
                    # Tail held values without a later observed endpoint cannot
                    # be redistributed yet. Preserve them without inventing data.
                    quality = "held"

            if reason:
                quality = "discontinuity"
                output = (None,) * len(deltas)

            imp, exp, se, gw42, gw20 = output
            p1_quality = "discontinuity" if reason else "gap" if quality == "gap" else "observed"
            pv_quality = (
                "discontinuity" if reason else
                "gap" if quality == "gap" else
                "estimated" if quality == "estimated" else
                "held" if quality == "held" else
                "observed"
            )
            pv_total = None if se is None else se + gw42 + gw20
            house = None if imp is None else imp + pv_total - exp

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
        estimated_intervals = sum(
            1 for row in prepared_rows if row["pv_estimated_interval"]
        )
        return {
            "rows": written,
            "counter_snapshots": len(rows),
            "pv_estimated_intervals": estimated_intervals,
        }
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB))
    args = parser.parse_args()
    result = build(Path(args.db))
    print(
        "PASS: "
        f"house_energy_intervals={result['rows']} "
        f"counter_snapshots={result['counter_snapshots']} "
        f"pv_estimated_intervals={result['pv_estimated_intervals']}"
    )


if __name__ == "__main__":
    main()

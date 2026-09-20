#!/usr/bin/env python3
"""Import an explicit Homey Insights cumulative-counter export into EMS history.

Maintenance tool only. It never connects to Homey and is not a service/timer.
Input JSON schema: EMS_HOMEY_COUNTER_BACKFILL_V1.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
SCHEMA = "EMS_HOMEY_COUNTER_BACKFILL_V1"
SERIES = {
    "grid_import": ("grid_p1", "energy_import_kwh"),
    "grid_export": ("grid_p1", "energy_export_kwh"),
    "pv_solaredge": ("pv_solaredge", "energy_produced_kwh"),
    "pv_goodwe4200": ("pv_goodwe4200", "energy_produced_kwh"),
    "pv_goodwe2000": ("pv_goodwe2000", "energy_produced_kwh"),
}


def parse_ts(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("TIMESTAMP_TZ_REQUIRED")
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ids(con, device_key, metric_key):
    row = con.execute(
        """SELECT d.id,m.id FROM devices d CROSS JOIN metrics m
           WHERE d.device_key=? AND m.metric_key=?""",
        (device_key, metric_key),
    ).fetchone()
    if not row:
        raise ValueError(f"UNKNOWN_TARGET:{device_key}/{metric_key}")
    return row


def import_file(input_path, db_path=DB):
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise ValueError("INPUT_SCHEMA_INVALID")
    resolution = payload.get("source_resolution_seconds")
    if not isinstance(resolution, int) or resolution <= 0:
        raise ValueError("SOURCE_RESOLUTION_INVALID")
    data = payload.get("series")
    if not isinstance(data, dict) or set(data) != set(SERIES):
        raise ValueError("SERIES_SET_INVALID")

    con = sqlite3.connect(str(db_path), timeout=2.0)
    con.execute("PRAGMA busy_timeout=2000")
    inserted = refined = skipped = 0
    try:
        target_ids = {name: ids(con, *target) for name, target in SERIES.items()}

        # Backfill is authoritative only before canonical live observation starts.
        # Homey Insights values are downsampled historical estimates and must not
        # overlap the observed archive as if they were exact counter readings.
        observed_starts = {}
        for name, (device_id, metric_id) in target_ids.items():
            row = con.execute(
                """SELECT MIN(ts_utc) FROM measurements
                   WHERE device_id=? AND metric_id=? AND quality='observed'""",
                (device_id, metric_id),
            ).fetchone()
            observed_starts[name] = row[0] if row and row[0] else None

        # If the final backfill anchor immediately before live observation is
        # already above the first observed counter value, that anchor is not a
        # valid exact boundary reading. Exclude it from future imports as well.
        conflicting_boundary = {}
        for name, (device_id, metric_id) in target_ids.items():
            observed_start = observed_starts[name]
            conflicting_boundary[name] = None
            if observed_start is None:
                continue
            first_observed = con.execute(
                """SELECT value_real FROM measurements
                   WHERE device_id=? AND metric_id=? AND quality='observed'
                     AND ts_utc=?
                   ORDER BY id LIMIT 1""",
                (device_id, metric_id, observed_start),
            ).fetchone()
            previous_backfill = con.execute(
                """SELECT ts_utc,value_real FROM measurements
                   WHERE device_id=? AND metric_id=? AND quality='backfill'
                     AND ts_utc < ?
                   ORDER BY ts_utc DESC LIMIT 1""",
                (device_id, metric_id, observed_start),
            ).fetchone()
            if (
                first_observed
                and previous_backfill
                and previous_backfill[1] is not None
                and first_observed[0] is not None
                and previous_backfill[1] > first_observed[0]
            ):
                conflicting_boundary[name] = previous_backfill[0]

        for name, entries in data.items():
            if isinstance(entries, dict):
                entries = entries.get("entries")
            if not isinstance(entries, list):
                raise ValueError(f"SERIES_INVALID:{name}")
            device_id, metric_id = target_ids[name]
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError(f"ENTRY_INVALID:{name}")
                ts = parse_ts(entry.get("t"))
                value = entry.get("v")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"VALUE_INVALID:{name}:{ts}")
                observed_start = observed_starts[name]
                if (
                    (observed_start is not None and ts >= observed_start)
                    or ts == conflicting_boundary[name]
                ):
                    skipped += 1
                    continue
                existing = con.execute(
                    """SELECT id,quality,source_resolution_seconds
                       FROM measurements
                       WHERE ts_utc=? AND device_id=? AND metric_id=?""",
                    (ts, device_id, metric_id),
                ).fetchone()
                if existing is None:
                    con.execute(
                        """INSERT INTO measurements
                           (ts_utc,device_id,metric_id,value_real,quality,
                            source_resolution_seconds,collected_at_utc)
                           VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                        (ts, device_id, metric_id, float(value), "backfill", resolution),
                    )
                    inserted += 1
                elif (
                    existing[1] == "backfill"
                    and isinstance(existing[2], int)
                    and resolution < existing[2]
                ):
                    con.execute(
                        """UPDATE measurements
                           SET value_real=?,quality='backfill',
                               source_resolution_seconds=?,
                               collected_at_utc=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (float(value), resolution, existing[0]),
                    )
                    refined += 1
                else:
                    # Never overwrite observed/live data, and never replace a
                    # backfill point with equal or coarser source resolution.
                    skipped += 1
        con.commit()
        return {"inserted": inserted, "refined": refined, "skipped": skipped}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("--db", default=str(DB))
    args = parser.parse_args()
    result = import_file(args.input_json, Path(args.db))
    print(f"PASS: inserted={result['inserted']} refined={result['refined']} skipped={result['skipped']}")


if __name__ == "__main__":
    main()

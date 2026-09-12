#!/usr/bin/env python3

"""One-time guarded migration of Honeywell target_temperature_c to room_setpoint_c.

Default mode is audit-only. Use --apply to migrate transactionally.
No schema is created; existing canonical metrics/devices are required.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
LEGACY = "target_temperature_c"
CANONICAL = "room_setpoint_c"


def metric_id(con: sqlite3.Connection, key: str) -> int | None:
    row = con.execute("SELECT id FROM metrics WHERE metric_key=?", (key,)).fetchone()
    return int(row[0]) if row else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform migration")
    args = parser.parse_args()

    if not DB.exists():
        raise SystemExit(f"ERROR: database not found: {DB}")

    con = sqlite3.connect(DB)
    try:
        legacy_id = metric_id(con, LEGACY)
        canonical_id = metric_id(con, CANONICAL)

        if legacy_id is None:
            print("PASS: legacy metric absent; nothing to migrate")
            return
        if canonical_id is None:
            raise SystemExit(f"ERROR: canonical metric missing: {CANONICAL}")

        rows = con.execute(
            """
            SELECT x.id, x.ts_utc, x.device_id, d.device_key,
                   x.value_real, x.value_text, x.quality,
                   x.source_resolution_seconds
            FROM measurements x
            JOIN devices d ON d.id=x.device_id
            WHERE x.metric_id=?
            ORDER BY x.ts_utc, d.device_key
            """,
            (legacy_id,),
        ).fetchall()

        non_honeywell = [r for r in rows if not str(r[3]).startswith("honeywell_")]
        if non_honeywell:
            raise SystemExit(
                f"ERROR: legacy metric has {len(non_honeywell)} non-Honeywell rows; refusing migration"
            )

        print(f"legacy_metric_id={legacy_id} canonical_metric_id={canonical_id}")
        print(f"legacy_rows={len(rows)}")
        for r in rows:
            print(
                f"  {r[1]} {r[3]} value_real={r[4]} "
                f"quality={r[6]} resolution={r[7]}"
            )

        conflicts = []
        for r in rows:
            existing = con.execute(
                """
                SELECT value_real, value_text, quality, source_resolution_seconds
                FROM measurements
                WHERE ts_utc=? AND device_id=? AND metric_id=?
                """,
                (r[1], r[2], canonical_id),
            ).fetchone()
            if existing and tuple(existing) != (r[4], r[5], r[6], r[7]):
                conflicts.append((r[1], r[3], existing, (r[4], r[5], r[6], r[7])))

        if conflicts:
            for c in conflicts:
                print(f"CONFLICT: ts={c[0]} device={c[1]} canonical={c[2]} legacy={c[3]}")
            raise SystemExit(f"ERROR: {len(conflicts)} canonical conflicts; refusing migration")

        if not args.apply:
            print("AUDIT PASS: safe to migrate; rerun with --apply")
            return

        con.execute("BEGIN IMMEDIATE")
        inserted = 0
        for r in rows:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO measurements
                (ts_utc, device_id, metric_id, value_real, value_text, quality, source_resolution_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (r[1], r[2], canonical_id, r[4], r[5], r[6], r[7]),
            )
            inserted += cur.rowcount

        con.execute("DELETE FROM measurements WHERE metric_id=?", (legacy_id,))
        remaining = con.execute(
            "SELECT COUNT(*) FROM measurements WHERE metric_id=?", (legacy_id,)
        ).fetchone()[0]
        if remaining != 0:
            raise RuntimeError(f"legacy rows remain after delete: {remaining}")

        con.execute("DELETE FROM metrics WHERE id=?", (legacy_id,))
        con.commit()

        print(
            f"MIGRATION PASS: legacy_rows={len(rows)} inserted_canonical={inserted} "
            f"legacy_metric_removed=True"
        )
    except Exception:
        if con.in_transaction:
            con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()

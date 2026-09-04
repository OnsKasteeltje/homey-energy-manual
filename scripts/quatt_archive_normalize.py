#!/usr/bin/env python3
"""Normalize Homey Insights JSON for Quatt into a local SQLite archive.

This is deliberately transport-agnostic: it accepts exported/fetched JSON and
stores valid numeric samples while preserving null samples as explicit gaps.
No Homey credentials are required by this script.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


def iter_entries(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        yield from payload["entries"]
        return
    if isinstance(payload, list):
        yield from payload
        return
    raise ValueError("Expected a JSON list or an object containing an 'entries' list")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quatt_insights (
            log_id TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            value REAL,
            is_gap INTEGER NOT NULL DEFAULT 0,
            source_resolution TEXT,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (log_id, timestamp_utc)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quatt_insights_time "
        "ON quatt_insights(timestamp_utc)"
    )


def normalize_value(value: Any) -> tuple[float | None, int]:
    if value is None:
        return None, 1
    if isinstance(value, bool):
        return float(value), 0
    if isinstance(value, (int, float)):
        return float(value), 0
    raise ValueError(f"Unsupported Insights value type: {type(value).__name__}")


def import_file(
    conn: sqlite3.Connection,
    input_path: Path,
    log_id: str,
    resolution: str | None,
) -> tuple[int, int]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    imported = 0
    gaps = 0

    for entry in iter_entries(payload):
        timestamp = entry.get("t")
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError(f"Entry without valid timestamp: {entry!r}")

        value, is_gap = normalize_value(entry.get("v"))
        conn.execute(
            """
            INSERT INTO quatt_insights
                (log_id, timestamp_utc, value, is_gap, source_resolution)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(log_id, timestamp_utc) DO UPDATE SET
                value=excluded.value,
                is_gap=excluded.is_gap,
                source_resolution=excluded.source_resolution
            """,
            (log_id, timestamp, value, is_gap, resolution),
        )
        imported += 1
        gaps += is_gap

    conn.commit()
    return imported, gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Homey Insights JSON file")
    parser.add_argument("--log-id", required=True, help="Full Homey Insights log ID")
    parser.add_argument("--resolution", help="Homey resolution used for the source request")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/quatt/quatt-insights.sqlite3"),
        help="SQLite archive path",
    )
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as conn:
        init_db(conn)
        imported, gaps = import_file(conn, args.input, args.log_id, args.resolution)

    print(f"imported={imported} gaps={gaps} db={args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

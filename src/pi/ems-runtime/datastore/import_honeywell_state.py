#!/usr/bin/env python3

"""Import normalized Honeywell state into canonical EMS history.

Reads only the local Honeywell state artifact and writes two canonical metrics per
mapped Honeywell zone:

- room_temperature_c
- room_setpoint_c

The importer deliberately does not create devices or metrics. Missing schema
objects are treated as configuration errors so database semantics cannot drift
silently. The legacy experimental metric target_temperature_c is audited only;
it is never written or deleted by this importer.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
STATE = Path("/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json")
SOURCE_RESOLUTION_SECONDS = 300
EXPECTED_SCHEMA = "EMS_HONEYWELL_STATE_V0.2"
EXPECTED_ZONE_COUNT = 8

CANONICAL_METRICS = {
    "room_temperature_c": "roomTemperature_C",
    "room_setpoint_c": "targetTemperature_C",
}


def load_state() -> dict:
    if not STATE.exists():
        raise RuntimeError(f"Honeywell state not found: {STATE}")

    payload = json.loads(STATE.read_text())

    if payload.get("schema") != EXPECTED_SCHEMA:
        raise RuntimeError(
            f"Unexpected Honeywell schema: {payload.get('schema')!r}; "
            f"expected {EXPECTED_SCHEMA!r}"
        )

    zones = payload.get("zones")
    if not isinstance(zones, list) or len(zones) != EXPECTED_ZONE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_ZONE_COUNT} Honeywell zones, got "
            f"{len(zones) if isinstance(zones, list) else 'invalid'}"
        )

    if not payload.get("generatedAt"):
        raise RuntimeError("Honeywell state missing generatedAt")

    return payload


def require_metric_ids(con: sqlite3.Connection) -> dict[str, int]:
    result: dict[str, int] = {}
    for metric_key in CANONICAL_METRICS:
        row = con.execute(
            "SELECT id FROM metrics WHERE metric_key=?",
            (metric_key,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Missing canonical metric_key: {metric_key}")
        result[metric_key] = int(row[0])
    return result


def require_device_ids(con: sqlite3.Connection, zones: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for zone in zones:
        key = zone.get("key")
        if not key:
            raise RuntimeError("Honeywell zone missing key")

        device_key = f"honeywell_{key}"
        row = con.execute(
            "SELECT id FROM devices WHERE device_key=?",
            (device_key,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Missing Honeywell device_key: {device_key}")
        result[key] = int(row[0])
    return result


def audit_legacy_target_metric(con: sqlite3.Connection, device_ids: list[int]) -> tuple[bool, int]:
    row = con.execute(
        "SELECT id FROM metrics WHERE metric_key='target_temperature_c'"
    ).fetchone()
    if not row:
        return False, 0

    placeholders = ",".join("?" for _ in device_ids)
    count = con.execute(
        f"SELECT COUNT(*) FROM measurements WHERE metric_id=? AND device_id IN ({placeholders})",
        (int(row[0]), *device_ids),
    ).fetchone()[0]
    return True, int(count)


def main() -> None:
    if not DB.exists():
        raise RuntimeError(f"Database not found: {DB}")

    state = load_state()
    zones = state["zones"]
    ts = state["generatedAt"]

    con = sqlite3.connect(DB)
    try:
        metric_ids = require_metric_ids(con)
        device_ids = require_device_ids(con, zones)

        legacy_exists, legacy_rows = audit_legacy_target_metric(
            con, list(device_ids.values())
        )

        attempted = 0
        inserted = 0
        skipped_null = 0

        for zone in zones:
            key = zone["key"]
            device_id = device_ids[key]

            for metric_key, source_field in CANONICAL_METRICS.items():
                attempted += 1
                value = zone.get(source_field)
                if value is None:
                    skipped_null += 1
                    continue

                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO measurements
                    (
                        ts_utc,
                        device_id,
                        metric_id,
                        value_real,
                        quality,
                        source_resolution_seconds
                    )
                    VALUES (?, ?, ?, ?, 'observed', ?)
                    """,
                    (
                        ts,
                        device_id,
                        metric_ids[metric_key],
                        float(value),
                        SOURCE_RESOLUTION_SECONDS,
                    ),
                )
                inserted += cur.rowcount

        con.commit()

        print(f"PASS: generatedAt={ts}")
        print(f"zones={len(zones)} attempted={attempted} inserted={inserted} skipped_null={skipped_null}")
        print("canonical_metrics=room_temperature_c,room_setpoint_c")
        print(
            "legacy_target_temperature_c="
            + (f"present honeywell_rows={legacy_rows} action=AUDIT_ONLY" if legacy_exists else "absent")
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

"""Build a read-only EMS thermal observer artifact.

Inputs:
- canonical SQLite history (Honeywell room temperature/setpoint + Quatt telemetry)
- normalized Honeywell schedule artifact

Output:
- /home/jeroen/ems/runtime/thermal/thermal-observer.json

This module performs no Homey, Honeywell/Resideo, Quatt or OpenTherm writes.
It does not infer actual Evohome valve/heat demand; it only reports observed
room/setpoint relationships and available Quatt context.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
SCHEDULE = Path("/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-schedule.json")
OUTPUT = Path("/home/jeroen/ems/runtime/thermal/thermal-observer.json")

HONEYWELL_DEVICE_PREFIX = "honeywell_"
EXPECTED_ZONES = 8
ROOM_METRICS = ("room_temperature_c", "room_setpoint_c")
QUATT_DEVICE_KEY = "quatt_cic"
QUATT_METRICS = (
    "electrical_power_w",
    "outside_temperature_c",
    "hp1_thermal_power_w",
    "hp2_thermal_power_w",
    "hp1_cop",
    "hp2_cop",
)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_seconds(ts: str | None, now: datetime) -> float | None:
    dt = parse_ts(ts)
    if dt is None:
        return None
    return round((now - dt).total_seconds(), 3)


def latest_measurement(con: sqlite3.Connection, device_key: str, metric_key: str) -> dict[str, Any] | None:
    row = con.execute(
        """
        SELECT x.ts_utc, x.value_real, x.quality, x.source_resolution_seconds
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE d.device_key=? AND m.metric_key=? AND x.value_real IS NOT NULL
        ORDER BY x.ts_utc DESC
        LIMIT 1
        """,
        (device_key, metric_key),
    ).fetchone()
    if not row:
        return None
    return {
        "tsUtc": row[0],
        "value": row[1],
        "quality": row[2],
        "sourceResolutionSeconds": row[3],
    }


def load_schedule() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    raw = json.loads(SCHEDULE.read_text())
    if raw.get("schema") != "EMS_HONEYWELL_SCHEDULE_V0.1":
        raise RuntimeError(f"Unexpected Honeywell schedule schema: {raw.get('schema')}")
    zones = raw.get("zones") or []
    by_key = {z["key"]: z for z in zones}
    if len(by_key) != EXPECTED_ZONES:
        raise RuntimeError(f"Expected {EXPECTED_ZONES} schedule zones, got {len(by_key)}")
    return raw, by_key


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    os.chmod(tmp, 0o644)
    tmp.replace(path)


def main() -> None:
    if not DB.exists():
        raise RuntimeError(f"Database not found: {DB}")
    if not SCHEDULE.exists():
        raise RuntimeError(f"Honeywell schedule not found: {SCHEDULE}")

    now = datetime.now(timezone.utc)
    schedule_raw, schedule_by_key = load_schedule()

    con = sqlite3.connect(DB)
    try:
        device_rows = con.execute(
            "SELECT device_key, name FROM devices WHERE device_key LIKE ? ORDER BY device_key",
            (HONEYWELL_DEVICE_PREFIX + "%",),
        ).fetchall()

        if len(device_rows) != EXPECTED_ZONES:
            raise RuntimeError(f"Expected {EXPECTED_ZONES} Honeywell devices, got {len(device_rows)}")

        zones = []
        latest_zone_ts: list[datetime] = []

        for device_key, device_name in device_rows:
            key = device_key.removeprefix(HONEYWELL_DEVICE_PREFIX)
            sched = schedule_by_key.get(key)
            if sched is None:
                raise RuntimeError(f"No schedule mapping for {device_key}")

            room = latest_measurement(con, device_key, "room_temperature_c")
            setpoint = latest_measurement(con, device_key, "room_setpoint_c")
            if room is None or setpoint is None:
                raise RuntimeError(f"Missing canonical room metrics for {device_key}")

            room_dt = parse_ts(room["tsUtc"])
            setpoint_dt = parse_ts(setpoint["tsUtc"])
            if room_dt:
                latest_zone_ts.append(room_dt)
            if setpoint_dt:
                latest_zone_ts.append(setpoint_dt)

            room_c = float(room["value"])
            setpoint_c = float(setpoint["value"])
            error_c = round(setpoint_c - room_c, 3)

            zones.append(
                {
                    "key": key,
                    "deviceKey": device_key,
                    "displayName": sched.get("displayName") or device_name or key,
                    "roomTemperature_C": room_c,
                    "roomTemperatureTsUtc": room["tsUtc"],
                    "roomTemperatureAgeSeconds": age_seconds(room["tsUtc"], now),
                    "setpoint_C": setpoint_c,
                    "setpointTsUtc": setpoint["tsUtc"],
                    "setpointAgeSeconds": age_seconds(setpoint["tsUtc"], now),
                    "temperatureError_C": error_c,
                    "belowSetpoint": error_c > 0.0,
                    "scheduleStatus": sched.get("scheduleStatus"),
                    "currentSwitchpoint": sched.get("currentSwitchpoint"),
                    "nextSwitchpoint": sched.get("nextSwitchpoint"),
                }
            )

        quatt_metrics: dict[str, Any] = {}
        for metric_key in QUATT_METRICS:
            item = latest_measurement(con, QUATT_DEVICE_KEY, metric_key)
            if item is None:
                quatt_metrics[metric_key] = None
            else:
                quatt_metrics[metric_key] = {
                    "value": item["value"],
                    "tsUtc": item["tsUtc"],
                    "ageSeconds": age_seconds(item["tsUtc"], now),
                    "quality": item["quality"],
                    "sourceResolutionSeconds": item["sourceResolutionSeconds"],
                }

        newest_zone_ts = max(latest_zone_ts).isoformat().replace("+00:00", "Z") if latest_zone_ts else None
        oldest_zone_ts = min(latest_zone_ts).isoformat().replace("+00:00", "Z") if latest_zone_ts else None

        payload = {
            "schema": "EMS_THERMAL_OBSERVER_V0.1",
            "generatedAt": now.isoformat().replace("+00:00", "Z"),
            "mode": "OBSERVE_ONLY",
            "executeAllowed": False,
            "sources": {
                "canonicalHistory": str(DB),
                "honeywellSchedule": str(SCHEDULE),
                "honeywellScheduleGeneratedAt": schedule_raw.get("generatedAt"),
                "honeywellScheduleAgeSeconds": age_seconds(schedule_raw.get("generatedAt"), now),
            },
            "zoneCount": len(zones),
            "zoneObservationWindow": {
                "oldestTsUtc": oldest_zone_ts,
                "newestTsUtc": newest_zone_ts,
            },
            "zones": zones,
            "quatt": {
                "deviceKey": QUATT_DEVICE_KEY,
                "metrics": quatt_metrics,
            },
            "semantics": {
                "temperatureError_C": "setpoint minus room temperature; positive means room is below setpoint",
                "belowSetpoint": "observational comparison only; not actual Evohome valve or heat-demand state",
                "control": "no Honeywell/Homey/Quatt/OpenTherm writes",
            },
        }

        atomic_write(OUTPUT, payload)

        print(f"PASS: schema={payload['schema']} zones={payload['zoneCount']} mode={payload['mode']}")
        print(f"output={OUTPUT}")
        print(f"schedule_age_seconds={payload['sources']['honeywellScheduleAgeSeconds']}")
        for z in zones:
            nxt = z["nextSwitchpoint"] or {}
            print(
                f"{z['displayName']}: room={z['roomTemperature_C']} "
                f"setpoint={z['setpoint_C']} error={z['temperatureError_C']} "
                f"next={nxt.get('time')}->{nxt.get('targetTemperature_C')}"
            )

    finally:
        con.close()


if __name__ == "__main__":
    main()

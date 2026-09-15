#!/usr/bin/env python3
"""Build EMS_HEATING_ROOM_MODEL_V0.1 from canonical Honeywell snapshots.

Pure interpretation layer: no Honeywell/Homey calls and no physical writes.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEDULE_SCHEMA = "EMS_HONEYWELL_SCHEDULE_V0.2"
STATE_SCHEMA = "EMS_HONEYWELL_STATE_V0.2"
OUTPUT_SCHEMA = "EMS_HEATING_ROOM_MODEL_V0.1"
HOME_TZ_NAME = "Europe/Amsterdam"
HOME_TZ = ZoneInfo(HOME_TZ_NAME)


class ModelError(ValueError):
    pass


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelError(f"{label} must be an object")
    return value


def _require_rooms(payload: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    zones = payload.get("zones")
    if not isinstance(zones, list) or not zones:
        raise ModelError(f"{label}.zones must be a non-empty array")
    result: dict[str, dict[str, Any]] = {}
    for zone in zones:
        z = _require_dict(zone, f"{label}.zone")
        key = z.get("key")
        if not isinstance(key, str) or not key:
            raise ModelError(f"{label} zone missing key")
        if key in result:
            raise ModelError(f"duplicate {label} room key: {key}")
        result[key] = z
    return result


def _parse_aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ModelError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ModelError(f"{label} must be offset-aware")
    return dt


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelError(f"{label} must be numeric")
    return float(value)


def _transition(current: float, nxt: float) -> str:
    if nxt > current:
        return "UP"
    if nxt < current:
        return "DOWN"
    return "NONE"


def build_model(schedule: dict[str, Any], state: dict[str, Any], *, generated_at: datetime | None = None) -> dict[str, Any]:
    if schedule.get("schema") != SCHEDULE_SCHEMA:
        raise ModelError(f"unexpected schedule schema: {schedule.get('schema')}")
    if state.get("schema") != STATE_SCHEMA:
        raise ModelError(f"unexpected state schema: {state.get('schema')}")

    schedule_generated = _parse_aware(schedule.get("generatedAt"), "schedule.generatedAt")
    state_generated = _parse_aware(state.get("generatedAt"), "state.generatedAt")
    schedule_rooms = _require_rooms(schedule, "schedule")
    state_rooms = _require_rooms(state, "state")

    if set(schedule_rooms) != set(state_rooms):
        missing_state = sorted(set(schedule_rooms) - set(state_rooms))
        missing_schedule = sorted(set(state_rooms) - set(schedule_rooms))
        raise ModelError(f"room key mismatch: missingState={missing_state}, missingSchedule={missing_schedule}")

    rooms: list[dict[str, Any]] = []
    for key, sz in schedule_rooms.items():
        if sz.get("scheduleStatus") != "OK":
            raise ModelError(f"schedule not OK for {key}: {sz.get('scheduleStatus')}")

        current_sp = _require_dict(sz.get("currentSwitchpoint"), f"{key}.currentSwitchpoint")
        next_sp = _require_dict(sz.get("nextSwitchpoint"), f"{key}.nextSwitchpoint")
        current_time = _parse_aware(current_sp.get("time"), f"{key}.currentSwitchpoint.time").astimezone(HOME_TZ)
        next_time = _parse_aware(next_sp.get("time"), f"{key}.nextSwitchpoint.time").astimezone(HOME_TZ)
        if next_time <= current_time:
            raise ModelError(f"next switchpoint must be after current switchpoint for {key}")

        current_baseline = _number(current_sp.get("targetTemperature_C"), f"{key}.currentSwitchpoint.targetTemperature_C")
        next_baseline = _number(next_sp.get("targetTemperature_C"), f"{key}.nextSwitchpoint.targetTemperature_C")

        st = state_rooms[key]
        temperature = _number(st.get("roomTemperature_C"), f"{key}.roomTemperature_C")
        actual_target = _number(st.get("targetTemperature_C"), f"{key}.targetTemperature_C")
        setpoint_mode = st.get("setpointMode")
        if not isinstance(setpoint_mode, str) or not setpoint_mode:
            raise ModelError(f"{key}.setpointMode missing")

        rooms.append({
            "key": key,
            "displayName": sz.get("displayName") or st.get("displayName") or key,
            "valid": True,
            "current": {
                "temperature_C": temperature,
                "targetTemperature_C": actual_target,
                "setpointMode": setpoint_mode,
            },
            "baseline": {
                "currentTarget_C": current_baseline,
                "currentSince": current_time.isoformat(),
                "nextChangeAt": next_time.isoformat(),
                "nextTarget_C": next_baseline,
                "direction": _transition(current_baseline, next_baseline),
            },
        })

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ModelError("generated_at must be offset-aware")

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": HOME_TZ_NAME,
        "baselineAuthority": "HONEYWELL",
        "valid": True,
        "sources": {
            "scheduleSchema": SCHEDULE_SCHEMA,
            "scheduleGeneratedAt": schedule_generated.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "stateSchema": STATE_SCHEMA,
            "stateGeneratedAt": state_generated.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "roomCount": len(rooms),
        "rooms": rooms,
    }


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return _require_dict(json.load(fh), str(path))


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        model = build_model(_load(args.schedule), _load(args.state))
        _atomic_write(args.output, model)
    except (OSError, json.JSONDecodeError, ModelError) as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"OK: {args.output} ({model['roomCount']} rooms, {OUTPUT_SCHEMA})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

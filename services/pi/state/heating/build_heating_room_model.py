#!/usr/bin/env python3
"""Build EMS_HEATING_ROOM_MODEL_V0.1 from canonical Honeywell snapshots.

Pure interpretation layer: no Honeywell/Homey calls and no physical writes.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
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



_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _weekly_switchpoints(
    zone: dict[str, Any],
    now: datetime,
    key: str,
) -> list[tuple[datetime, float]]:
    """Resolve the Honeywell weekly baseline around now in Europe/Amsterdam."""

    weekly = zone.get("weeklySchedule")
    if not isinstance(weekly, list) or not weekly:
        raise ModelError(f"{key}.weeklySchedule must be a non-empty array")

    now_local = now.astimezone(HOME_TZ)
    monday = now_local.date() - timedelta(days=now_local.weekday())

    resolved: list[tuple[datetime, float]] = []

    # Resolve previous/current/next week so that the active baseline can
    # cross midnight and the Sunday -> Monday week boundary safely.
    for week_offset in (-1, 0, 1):
        week_start = monday + timedelta(days=7 * week_offset)

        for day in weekly:
            d = _require_dict(day, f"{key}.weeklySchedule.day")

            day_name = d.get("day_of_week")
            if day_name not in _WEEKDAYS:
                raise ModelError(
                    f"{key}.weeklySchedule invalid day_of_week: {day_name}"
                )

            switchpoints = d.get("switchpoints")
            if not isinstance(switchpoints, list):
                raise ModelError(
                    f"{key}.weeklySchedule.{day_name}.switchpoints must be an array"
                )

            day_date = week_start + timedelta(days=_WEEKDAYS[day_name])

            for index, switchpoint in enumerate(switchpoints):
                sp = _require_dict(
                    switchpoint,
                    f"{key}.weeklySchedule.{day_name}.switchpoints[{index}]",
                )

                tod = sp.get("time_of_day")
                if not isinstance(tod, str):
                    raise ModelError(
                        f"{key}.weeklySchedule.{day_name}."
                        f"switchpoints[{index}].time_of_day missing"
                    )

                try:
                    local_time = datetime.strptime(tod, "%H:%M:%S").time()
                except ValueError as exc:
                    raise ModelError(
                        f"{key}.weeklySchedule invalid time_of_day: {tod}"
                    ) from exc

                target = _number(
                    sp.get("heat_setpoint"),
                    f"{key}.weeklySchedule.{day_name}."
                    f"switchpoints[{index}].heat_setpoint",
                )

                local_dt = datetime.combine(
                    day_date,
                    local_time,
                    tzinfo=HOME_TZ,
                )

                resolved.append((local_dt, target))

    resolved.sort(key=lambda item: item[0])
    return resolved


def _resolve_baseline(
    zone: dict[str, Any],
    now: datetime,
    key: str,
) -> tuple[datetime, float, datetime, float]:
    """Resolve the scheduled baseline active at now and its next transition."""

    points = _weekly_switchpoints(zone, now, key)
    now_local = now.astimezone(HOME_TZ)

    current = None
    upcoming = None

    for point in points:
        if point[0] <= now_local:
            current = point
        elif upcoming is None:
            upcoming = point
            break

    if current is None or upcoming is None:
        raise ModelError(
            f"cannot resolve current/next weekly switchpoint for {key}"
        )

    current_time, current_target = current
    next_time, next_target = upcoming

    if next_time <= current_time:
        raise ModelError(
            f"next weekly switchpoint must be after current switchpoint for {key}"
        )

    return current_time, current_target, next_time, next_target


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

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ModelError("generated_at must be offset-aware")

    rooms: list[dict[str, Any]] = []
    for key, sz in schedule_rooms.items():
        if sz.get("scheduleStatus") != "OK":
            raise ModelError(f"schedule not OK for {key}: {sz.get('scheduleStatus')}")

        # The Honeywell schedule collector is deliberately low-frequency.
        # Its resolved current/next switchpoints describe collection time and
        # can therefore become stale before this model is rebuilt. The weekly
        # Honeywell schedule remains the baseline authority; resolve it at
        # model-generation time in Europe/Amsterdam.
        current_time, current_baseline, next_time, next_baseline = (
            _resolve_baseline(sz, now, key)
        )

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

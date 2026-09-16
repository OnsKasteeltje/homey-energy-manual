#!/usr/bin/env python3
"""Build EMS_HEATING_PREHEAT_PLAN_V0.1 from the canonical heating room model.

Shadow candidate builder only. It identifies upcoming Honeywell UP transitions but
does not select PV slots. PV allocation belongs to the joint Dynamic Pi Planner.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE_SCHEMA = "EMS_HEATING_ROOM_MODEL_V0.1"
OUTPUT_SCHEMA = "EMS_HEATING_PREHEAT_PLAN_V0.1"
HOME_TZ_NAME = "Europe/Amsterdam"


class PlanError(ValueError):
    pass


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlanError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanError(f"{label} must be numeric")
    return float(value)


def _aware_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PlanError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PlanError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise PlanError(f"{label} must be offset-aware")
    return value


def build_plan(room_model: dict[str, Any], *, generated_at: datetime | None = None) -> dict[str, Any]:
    if room_model.get("schema") != SOURCE_SCHEMA:
        raise PlanError(f"unexpected room model schema: {room_model.get('schema')}")
    if room_model.get("mode") != "READ_ONLY" or room_model.get("controlMode") != "SHADOW":
        raise PlanError("room model must be READ_ONLY / SHADOW")
    if room_model.get("timezone") != HOME_TZ_NAME:
        raise PlanError(f"unexpected room model timezone: {room_model.get('timezone')}")
    if room_model.get("baselineAuthority") != "HONEYWELL":
        raise PlanError(f"unexpected baseline authority: {room_model.get('baselineAuthority')}")
    if room_model.get("valid") is not True:
        raise PlanError("room model is not valid")

    source_generated_at = _aware_timestamp(
        room_model.get("generatedAt"), "room model generatedAt"
    )

    rooms_source = room_model.get("rooms")
    if not isinstance(rooms_source, list) or not rooms_source:
        raise PlanError("room model rooms must be a non-empty array")

    seen: set[str] = set()
    rooms: list[dict[str, Any]] = []
    for item in rooms_source:
        room = _require_dict(item, "room")
        key = room.get("key")
        if not isinstance(key, str) or not key:
            raise PlanError("room missing key")
        if key in seen:
            raise PlanError(f"duplicate room key: {key}")
        seen.add(key)
        if room.get("valid") is not True:
            raise PlanError(f"room is not valid: {key}")

        baseline = _require_dict(room.get("baseline"), f"{key}.baseline")
        direction = baseline.get("direction")
        if direction not in {"UP", "DOWN", "NONE"}:
            raise PlanError(f"invalid baseline direction for {key}: {direction}")
        change_at = _aware_timestamp(
            baseline.get("nextChangeAt"), f"{key}.baseline.nextChangeAt"
        )
        target = _number(baseline.get("nextTarget_C"), f"{key}.baseline.nextTarget_C")

        eligible = direction == "UP"
        rooms.append({
            "key": key,
            "displayName": room.get("displayName") or key,
            "baseline": {
                "changeAt": change_at,
                "targetTemperature_C": target,
                "direction": direction,
            },
            "candidate": {
                "status": "ELIGIBLE_UP_TRANSITION" if eligible else "NOT_ELIGIBLE",
                "startAt": None,
                "targetTemperature_C": target,
                "reason": "AWAITING_OPPORTUNITY_EVALUATION" if eligible else f"BASELINE_{direction}",
            },
        })

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise PlanError("generated_at must be offset-aware")

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": HOME_TZ_NAME,
        "baselineAuthority": "HONEYWELL",
        "sourceRoomModelSchema": SOURCE_SCHEMA,
        "sourceRoomModelGeneratedAt": source_generated_at,
        "roomCount": len(rooms),
        "rooms": rooms,
    }

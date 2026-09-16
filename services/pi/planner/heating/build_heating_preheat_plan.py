#!/usr/bin/env python3
"""Build EMS_HEATING_PREHEAT_PLAN_V0.2 from the canonical heating room model.

Shadow candidate builder only. It evaluates room/schedule eligibility and produces
bounded 0.5 C candidate steps. It does not select PV slots or write devices.
PV allocation remains owned by the joint Dynamic Pi Planner.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SOURCE_SCHEMA = "EMS_HEATING_ROOM_MODEL_V0.1"
OUTPUT_SCHEMA = "EMS_HEATING_PREHEAT_PLAN_V0.2"
HOME_TZ_NAME = "Europe/Amsterdam"
MAX_ADVANCE = timedelta(hours=3)
MAX_STEP_C = 0.5
SCOPED_ROOMS = {"woonkamer", "eetkamer", "keuken", "serre"}
ROOM_GROUPS = {"living_area": ["woonkamer", "eetkamer"]}


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


def _aware_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PlanError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PlanError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise PlanError(f"{label} must be offset-aware")
    return dt


def _candidate_steps(current_baseline: float, future_target: float, actual: float) -> list[float]:
    """Split an advanced baseline rise into <=0.5 C setpoint steps.

    Steps already satisfied by measured room temperature are omitted. The final
    step never exceeds the future Honeywell baseline target.
    """
    steps: list[float] = []
    value = current_baseline
    while value < future_target - 1e-9:
        value = min(value + MAX_STEP_C, future_target)
        value = round(value, 2)
        if value > actual + 1e-9:
            steps.append(value)
    return steps


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

    source_generated_at = _aware_datetime(room_model.get("generatedAt"), "room model generatedAt")
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise PlanError("generated_at must be offset-aware")

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

        current = _require_dict(room.get("current"), f"{key}.current")
        baseline = _require_dict(room.get("baseline"), f"{key}.baseline")
        actual = _number(current.get("temperature_C"), f"{key}.current.temperature_C")
        current_target = _number(baseline.get("currentTarget_C"), f"{key}.baseline.currentTarget_C")
        future_target = _number(baseline.get("nextTarget_C"), f"{key}.baseline.nextTarget_C")
        direction = baseline.get("direction")
        if direction not in {"UP", "DOWN", "NONE"}:
            raise PlanError(f"invalid baseline direction for {key}: {direction}")
        change_dt = _aware_datetime(baseline.get("nextChangeAt"), f"{key}.baseline.nextChangeAt")

        in_scope = key in SCOPED_ROOMS
        seconds_to_change = (change_dt - now).total_seconds()
        within_window = 0 <= seconds_to_change <= MAX_ADVANCE.total_seconds()
        heat_demand = actual < future_target - 1e-9

        if not in_scope:
            status, reason = "NOT_ELIGIBLE", "ROOM_OUT_OF_PREHEAT_SCOPE"
        elif direction != "UP":
            status, reason = "NOT_ELIGIBLE", f"BASELINE_{direction}"
        elif not within_window:
            status, reason = "NOT_ELIGIBLE", "OUTSIDE_MAX_ADVANCE_WINDOW"
        elif not heat_demand:
            status, reason = "NOT_ELIGIBLE", "NO_HEAT_DEMAND_AT_CURRENT_TEMPERATURE"
        else:
            status, reason = "ELIGIBLE_UP_TRANSITION", "AWAITING_PV_OPPORTUNITY_EVALUATION"

        steps = _candidate_steps(current_target, future_target, actual) if status == "ELIGIBLE_UP_TRANSITION" else []
        group = next((name for name, members in ROOM_GROUPS.items() if key in members), None)
        rooms.append({
            "key": key,
            "displayName": room.get("displayName") or key,
            "preheatScope": in_scope,
            "group": group,
            "current": {"temperature_C": actual},
            "baseline": {
                "currentTargetTemperature_C": current_target,
                "changeAt": baseline.get("nextChangeAt"),
                "targetTemperature_C": future_target,
                "direction": direction,
            },
            "candidate": {
                "status": status,
                "earliestStartAt": (change_dt - MAX_ADVANCE).isoformat(),
                "startAt": None,
                "targetTemperature_C": future_target,
                "steps_C": steps,
                "reason": reason,
            },
        })

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": HOME_TZ_NAME,
        "baselineAuthority": "HONEYWELL",
        "sourceRoomModelSchema": SOURCE_SCHEMA,
        "sourceRoomModelGeneratedAt": source_generated_at.isoformat(),
        "policy": {
            "maxAdvanceMinutes": 180,
            "maxStep_C": MAX_STEP_C,
            "pvAllocationOwner": "DYNAMIC_PI_PLANNER",
            "intentionalGridImportAllowed": False,
            "scopedRooms": sorted(SCOPED_ROOMS),
            "roomGroups": ROOM_GROUPS,
        },
        "roomCount": len(rooms),
        "rooms": rooms,
    }

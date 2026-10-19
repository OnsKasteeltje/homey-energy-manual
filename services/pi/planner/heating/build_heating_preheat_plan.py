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
SCOPED_ROOMS = {"woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe"}
ROOM_GROUPS = {"living_area": ["woonkamer", "eetkamer"]}
ADJACENT_PEER = {
    "woonkamer": "eetkamer",
    "eetkamer": "woonkamer",
    "douwe_slaapkamer": "erker_douwe",
    "erker_douwe": "douwe_slaapkamer",
}


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
    room_by_key = {
        item.get("key"): item for item in rooms_source
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
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
        effective = _require_dict(room.get("effective"), f"{key}.effective")
        baseline = _require_dict(room.get("baseline"), f"{key}.baseline")
        actual = _number(current.get("temperature_C"), f"{key}.current.temperature_C")
        effective_target = _number(
            effective.get("currentTarget_C"),
            f"{key}.effective.currentTarget_C",
        )
        scheduled_current_target = _number(
            baseline.get("currentTarget_C"),
            f"{key}.baseline.currentTarget_C",
        )
        future_target = _number(baseline.get("nextTarget_C"), f"{key}.baseline.nextTarget_C")
        advance_allowed = effective.get("preheatAdvanceAllowed") is True
        effective_reason = effective.get("reason")
        if not isinstance(effective_reason, str) or not effective_reason:
            raise PlanError(f"{key}.effective.reason missing")
        direction = baseline.get("direction")
        if direction not in {"UP", "DOWN", "NONE"}:
            raise PlanError(f"invalid baseline direction for {key}: {direction}")
        change_dt = _aware_datetime(baseline.get("nextChangeAt"), f"{key}.baseline.nextChangeAt")

        # Look beyond the first change, but never cross a scheduled setback:
        # a later rise following a reduction is a separate heating episode.
        # Legacy fixtures without lookahead keep the next-transition behavior.
        horizon = room.get("lookahead")
        lookahead_selected = False
        episode_start = None
        if horizon is not None:
            horizon = _require_dict(horizon, f"{key}.lookahead")
            if horizon.get("windowMinutes") != 180:
                raise PlanError(f"{key}.lookahead unexpected window")
            if horizon.get("episodeStartAt") is not None:
                episode_start = _aware_datetime(horizon["episodeStartAt"], f"{key}.lookahead.episodeStartAt")
            points = horizon.get("switchpoints")
            if not isinstance(points, list):
                raise PlanError(f"{key}.lookahead.switchpoints must be an array")
            previous_target = scheduled_current_target
            highest_target = effective_target
            selected_change = None
            for point in points:
                point = _require_dict(point, f"{key}.lookahead.switchpoint")
                point_at = _aware_datetime(point.get("time"), f"{key}.lookahead.time")
                point_target = _number(point.get("targetTemperature_C"), f"{key}.lookahead.target")
                if not now < point_at <= now + MAX_ADVANCE:
                    raise PlanError(f"{key}.lookahead switchpoint outside current window")
                if point_target < previous_target - 1e-9:
                    break
                if point_target > highest_target + 1e-9:
                    highest_target = point_target
                    selected_change = point_at
                previous_target = point_target
            if selected_change is not None:
                future_target = highest_target
                change_dt = selected_change
                direction = "UP"
                lookahead_selected = True

        in_scope = key in SCOPED_ROOMS
        seconds_to_change = (change_dt - now).total_seconds()
        within_window = 0 <= seconds_to_change <= MAX_ADVANCE.total_seconds()
        heat_demand = actual < future_target - 1e-9

        # Independent, temporary adjacency opportunity: the receiver may use
        # one +0.5 C step even when Honeywell has no upcoming UP switchpoint.
        # It requires exactly one other *scheduled* room with normal demand;
        # V0.3 repeats the shared-heat-source check and retains Quatt/CV guards.
        peer_key = ADJACENT_PEER.get(key)
        peer_room = room_by_key.get(peer_key)
        normal_demand_rooms = set()
        for other_key, other_room in room_by_key.items():
            if not isinstance(other_room, dict) or other_room.get("valid") is not True:
                continue
            other_effective = other_room.get("effective")
            other_current = other_room.get("current")
            if not isinstance(other_effective, dict) or not isinstance(other_current, dict):
                continue
            if other_effective.get("source") != "SCHEDULE" or other_effective.get("preheatAdvanceAllowed") is not True:
                continue
            other_actual = _number(other_current.get("temperature_C"), f"{other_key}.actual")
            other_target = _number(other_effective.get("currentTarget_C"), f"{other_key}.target")
            if other_actual < other_target:
                normal_demand_rooms.add(other_key)
        pair_target = round(effective_target + MAX_STEP_C, 2)
        paired_only = (
            in_scope and advance_allowed and effective.get("source") == "SCHEDULE"
            and peer_room is not None and normal_demand_rooms == {peer_key}
            and effective_target <= actual + 1e-9
            and actual < pair_target - 1e-9
        )

        if not in_scope:
            status, reason = "NOT_ELIGIBLE", "ROOM_OUT_OF_PREHEAT_SCOPE"
        elif not advance_allowed:
            status, reason = "NOT_ELIGIBLE", effective_reason
        elif direction != "UP":
            status, reason = "NOT_ELIGIBLE", f"BASELINE_{direction}"
        elif not within_window:
            status, reason = "NOT_ELIGIBLE", "OUTSIDE_MAX_ADVANCE_WINDOW"
        elif not heat_demand:
            status, reason = "NOT_ELIGIBLE", "NO_HEAT_DEMAND_AT_CURRENT_TEMPERATURE"
        else:
            status, reason = "ELIGIBLE_UP_TRANSITION", "AWAITING_PV_OPPORTUNITY_EVALUATION"

        # A valid paired-room opportunity may not be suppressed just because
        # its OWN future schedule is flat or moving DOWN.
        if status == "NOT_ELIGIBLE" and paired_only and advance_allowed:
            status, reason = "ELIGIBLE_PAIRED_BASELINE", "ADJACENT_NORMAL_BASELINE_DEMAND"
            future_target = pair_target
            direction = "PAIRED_BASELINE"
            change_dt = _aware_datetime(baseline.get("nextChangeAt"), f"{key}.paired.nextChangeAt")

        steps = (
            _candidate_steps(effective_target, future_target, actual)
            if status in {"ELIGIBLE_UP_TRANSITION", "ELIGIBLE_PAIRED_BASELINE"}
            else []
        )
        opportunity_id = None
        if status == "ELIGIBLE_UP_TRANSITION" and episode_start is not None:
            opportunity_id = f"{key}|HONEYWELL_EPISODE|{episode_start.isoformat()}"
        elif status == "ELIGIBLE_PAIRED_BASELINE":
            current_since = _aware_datetime(baseline.get("currentSince"), f"{key}.paired.currentSince")
            opportunity_id = f"{key}|PAIRED_BASELINE|{peer_key}|{current_since.isoformat()}"
        group = next((name for name, members in ROOM_GROUPS.items() if key in members), None)
        rooms.append({
            "key": key,
            "displayName": room.get("displayName") or key,
            "preheatScope": in_scope,
            "group": group,
            "current": {"temperature_C": actual},
            "effective": {
                "currentTargetTemperature_C": effective_target,
                "source": effective.get("source"),
                "systemMode": effective.get("systemMode"),
                "setpointMode": effective.get("setpointMode"),
                "overrideUntil": effective.get("overrideUntil"),
                "preheatAdvanceAllowed": advance_allowed,
                "reason": effective_reason,
            },
            "baseline": {
                "currentTargetTemperature_C": effective_target,
                "scheduledCurrentTargetTemperature_C": scheduled_current_target,
                "changeAt": baseline.get("nextChangeAt"),
                "targetTemperature_C": future_target,
                "direction": direction,
            },
            "candidate": {
                "status": status,
                "earliestStartAt": (
                    now.isoformat() if status == "ELIGIBLE_PAIRED_BASELINE"
                    else (change_dt - MAX_ADVANCE).isoformat()
                ),
                "startAt": None,
                "opportunityId": opportunity_id,
                "targetTemperature_C": future_target,
                "targetChangeAt": change_dt.isoformat(),
                "targetDirection": direction,
                "lookaheadSelected": lookahead_selected,
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

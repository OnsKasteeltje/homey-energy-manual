#!/usr/bin/env python3
"""Build the read-only Heating Preheat V0.3 shadow state.

This layer does not select PV slots and does not write devices. It combines the
canonical room model, the V0.2 thermal/schedule candidate plan and fresh Quatt
observer state into explicit safety/eligibility state for later central-planner
allocation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ROOM_MODEL_SCHEMA = "EMS_HEATING_ROOM_MODEL_V0.1"
CANDIDATE_SCHEMA = "EMS_HEATING_PREHEAT_PLAN_V0.2"
QUATT_SCHEMA = "EMS_QUATT_CURRENT_STATE_V0.1"
OUTPUT_SCHEMA = "EMS_HEATING_PREHEAT_SHADOW_V0.3"

# Quatt current is collected every five minutes. Two collection intervals is a
# conservative shadow-only freshness bound. Unknown/stale CV status blocks a
# new preheat increment; it never affects normal Honeywell baseline heating.
MAX_QUATT_AGE_SECONDS = 600

# No unvalidated thermal tolerance is invented in V0.3 shadow. Exact measured
# comparisons are deliberately conservative until Thermal Learning validates a
# suitable tolerance/hysteresis.
BASELINE_TOLERANCE_C = 0.0
STEP_REACHED_TOLERANCE_C = 0.0


class ShadowError(ValueError):
    pass


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ShadowError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShadowError(f"{label} must be numeric")
    return float(value)


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ShadowError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ShadowError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ShadowError(f"{label} must be offset-aware")
    return dt


def _room_map(items: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ShadowError(f"{label} must be a non-empty array")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        room = _dict(item, label)
        key = room.get("key")
        if not isinstance(key, str) or not key:
            raise ShadowError(f"{label} room missing key")
        if key in result:
            raise ShadowError(f"duplicate {label} room key: {key}")
        result[key] = room
    return result


def _cv_guard(quatt_current: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not isinstance(quatt_current, dict) or quatt_current.get("schema") != QUATT_SCHEMA:
        return {
            "status": "UNKNOWN",
            "reason": "QUATT_SOURCE_INVALID",
            "cvActive": None,
            "ageSeconds": None,
        }

    try:
        generated = _aware(quatt_current.get("generatedAt"), "quatt.generatedAt")
    except ShadowError:
        return {
            "status": "UNKNOWN",
            "reason": "QUATT_GENERATED_AT_INVALID",
            "cvActive": None,
            "ageSeconds": None,
        }

    age = (now.astimezone(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds()
    if age < -30:
        return {
            "status": "UNKNOWN",
            "reason": "QUATT_SOURCE_FROM_FUTURE",
            "cvActive": None,
            "ageSeconds": round(age, 1),
        }
    if age > MAX_QUATT_AGE_SECONDS:
        return {
            "status": "STALE",
            "reason": "QUATT_SOURCE_STALE",
            "cvActive": None,
            "ageSeconds": round(age, 1),
        }

    observer = quatt_current.get("observerOnly")
    signal = observer.get("cvActive") if isinstance(observer, dict) else None
    value = signal.get("value") if isinstance(signal, dict) else None
    if not isinstance(value, bool):
        return {
            "status": "UNKNOWN",
            "reason": "CV_ACTIVE_SIGNAL_UNKNOWN",
            "cvActive": None,
            "ageSeconds": None,
            "collectorAgeSeconds": round(max(0.0, age), 1),
            "observedAt": None,
            "sourceLastUpdated": signal.get("sourceLastUpdated") if isinstance(signal, dict) else None,
        }

    try:
        observed_at = _aware(signal.get("observedAt"), "cvActive.observedAt")
    except ShadowError:
        return {
            "status": "UNKNOWN",
            "reason": "CV_ACTIVE_OBSERVED_AT_INVALID",
            "cvActive": None,
            "ageSeconds": round(max(0.0, age), 1),
            "observedAt": signal.get("observedAt") if isinstance(signal, dict) else None,
            "sourceLastUpdated": signal.get("sourceLastUpdated") if isinstance(signal, dict) else None,
        }

    # observedAt is provenance for the same successful Homey current-state fetch
    # that produced quatt.generatedAt. It must be coherent with that fetch, but it
    # is deliberately NOT a second independent freshness gate.
    observation_skew = (
        observed_at.astimezone(timezone.utc) - generated.astimezone(timezone.utc)
    ).total_seconds()
    if abs(observation_skew) > 5:
        return {
            "status": "UNKNOWN",
            "reason": "CV_ACTIVE_OBSERVATION_MISMATCH",
            "cvActive": None,
            "ageSeconds": round(max(0.0, age), 1),
            "observedAt": signal.get("observedAt"),
            "sourceLastUpdated": signal.get("sourceLastUpdated"),
        }

    return {
        "status": "OK",
        "reason": "CURRENT_QUATT_OBSERVER",
        "cvActive": value,
        "ageSeconds": round(max(0.0, age), 1),
        "observedAt": signal.get("observedAt"),
        "sourceLastUpdated": signal.get("sourceLastUpdated"),
    }


def build_shadow(
    room_model: dict[str, Any],
    candidate_plan: dict[str, Any],
    quatt_current: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    if room_model.get("schema") != ROOM_MODEL_SCHEMA:
        raise ShadowError(f"unexpected room model schema: {room_model.get('schema')}")
    if candidate_plan.get("schema") != CANDIDATE_SCHEMA:
        raise ShadowError(f"unexpected candidate schema: {candidate_plan.get('schema')}")
    if room_model.get("mode") != "READ_ONLY" or room_model.get("controlMode") != "SHADOW":
        raise ShadowError("room model must be READ_ONLY / SHADOW")
    if candidate_plan.get("mode") != "READ_ONLY" or candidate_plan.get("controlMode") != "SHADOW":
        raise ShadowError("candidate plan must be READ_ONLY / SHADOW")
    if room_model.get("baselineAuthority") != "HONEYWELL":
        raise ShadowError("Honeywell must remain baseline authority")
    if candidate_plan.get("baselineAuthority") != "HONEYWELL":
        raise ShadowError("candidate plan baseline authority mismatch")

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ShadowError("generated_at must be offset-aware")

    model_rooms = _room_map(room_model.get("rooms"), "room model rooms")
    candidate_rooms = _room_map(candidate_plan.get("rooms"), "candidate rooms")
    if set(model_rooms) != set(candidate_rooms):
        raise ShadowError("room key mismatch between room model and candidate plan")

    baseline_demand_rooms: list[str] = []
    for key, room in model_rooms.items():
        if room.get("valid") is not True:
            raise ShadowError(f"room invalid: {key}")
        current = _dict(room.get("current"), f"{key}.current")
        baseline = _dict(room.get("baseline"), f"{key}.baseline")
        actual = _number(current.get("temperature_C"), f"{key}.current.temperature_C")
        baseline_target = _number(baseline.get("currentTarget_C"), f"{key}.baseline.currentTarget_C")
        if actual < baseline_target - BASELINE_TOLERANCE_C:
            baseline_demand_rooms.append(key)

    candidate_policy = _dict(candidate_plan.get("policy"), "candidate policy")
    max_advance_minutes = _number(
        candidate_policy.get("maxAdvanceMinutes"),
        "candidate policy.maxAdvanceMinutes",
    )
    if max_advance_minutes <= 0:
        raise ShadowError("candidate policy.maxAdvanceMinutes must be positive")

    baseline_demand_present = bool(baseline_demand_rooms)
    cv_guard = _cv_guard(quatt_current, now)

    rooms: list[dict[str, Any]] = []
    for key, candidate_room in candidate_rooms.items():
        model_room = model_rooms[key]
        current = _dict(model_room.get("current"), f"{key}.current")
        baseline = _dict(model_room.get("baseline"), f"{key}.baseline")
        candidate = _dict(candidate_room.get("candidate"), f"{key}.candidate")

        actual = _number(current.get("temperature_C"), f"{key}.current.temperature_C")
        baseline_target = _number(baseline.get("currentTarget_C"), f"{key}.baseline.currentTarget_C")
        future_target = _number(baseline.get("nextTarget_C"), f"{key}.baseline.nextTarget_C")
        steps = candidate.get("steps_C")
        if not isinstance(steps, list):
            raise ShadowError(f"{key}.candidate.steps_C must be an array")
        steps = [_number(v, f"{key}.candidate.steps_C") for v in steps]
        next_step = steps[0] if steps else None

        candidate_status = candidate.get("status")
        if candidate_status != "ELIGIBLE_UP_TRANSITION":
            state = "NOT_ELIGIBLE"
            reason = candidate.get("reason") or "CANDIDATE_NOT_ELIGIBLE"
        elif baseline_demand_present:
            state = "BASELINE_HEATING"
            reason = "BASELINE_HEATING_DEMAND_PRESENT"
        elif cv_guard["status"] != "OK":
            state = "PREHEAT_BLOCKED_CV_STATUS_UNKNOWN"
            reason = cv_guard["reason"]
        elif cv_guard["cvActive"] is True:
            state = "PREHEAT_BLOCKED_CV_ASSIST"
            reason = "CV_ASSIST_DURING_PURE_PREHEAT"
        else:
            state = "PREHEAT_READY_FOR_GRANT"
            reason = "AWAITING_CENTRAL_PV_PRIORITY"

        rooms.append({
            "key": key,
            "displayName": candidate_room.get("displayName") or key,
            "preheatScope": candidate_room.get("preheatScope") is True,
            "group": candidate_room.get("group"),
            "current": {
                "temperature_C": actual,
                "baselineDemand": actual < baseline_target - BASELINE_TOLERANCE_C,
            },
            "baseline": {
                "currentTargetTemperature_C": baseline_target,
                "changeAt": baseline.get("nextChangeAt"),
                "targetTemperature_C": future_target,
                "direction": baseline.get("direction"),
            },
            "candidate": {
                "status": candidate_status,
                "reason": candidate.get("reason"),
                "opportunityOpensAt": candidate.get("earliestStartAt"),
                "opportunityClosesAt": baseline.get("nextChangeAt"),
                "steps_C": steps,
            },
            "shadow": {
                "state": state,
                "reason": reason,
                "plannerGrant": "NOT_EVALUATED",
                "activeStepTarget_C": None,
                "activeStepReached": None,
                "nextStepTarget_C": next_step,
            },
        })

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "generatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": "Europe/Amsterdam",
        "baselineAuthority": "HONEYWELL",
        "allocationAuthority": "DYNAMIC_PI_PLANNER",
        "house": {
            "baselineHeatingDemandPresent": baseline_demand_present,
            "baselineDemandRooms": sorted(baseline_demand_rooms),
        },
        "cvGuard": cv_guard,
        "policy": {
            "maxAdvanceMinutes": max_advance_minutes,
            "maxStep_C": 0.5,
            "baselineTolerance_C": BASELINE_TOLERANCE_C,
            "stepReachedTolerance_C": STEP_REACHED_TOLERANCE_C,
            "cvCheckedEveryIteration": True,
            "advanceOnlyAfterCurrentStepReached": True,
            "normalBaselineCvIsNotPreheatFault": True,
            "purePreheatCvAssistBlocksFurtherSteps": True,
            "plannerGrantRequiredBeforeAnyFutureWrite": True,
            "intentionalGridImportAllowed": False,
        },
        "rooms": rooms,
    }

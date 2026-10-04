#!/usr/bin/env python3
"""Build Heating Control Gate V0.5 SHADOW.

First control-boundary layer downstream of Heating Preheat V0.4. It translates
already-decided shadow progression into a guarded hypothetical edge command.
It never calls Homey/Honeywell/network APIs and never performs a physical write.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HEATING_SCHEMA = "EMS_HEATING_PREHEAT_SHADOW_V0.3"
PROGRESSION_SCHEMA = "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4"
OUTPUT_SCHEMA = "EMS_HEATING_CONTROL_GATE_SHADOW_V0.5"
PREVIOUS_SCHEMA = OUTPUT_SCHEMA

MAX_HEATING_AGE_SECONDS = 420
MAX_PROGRESSION_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 30
MAX_STEP_C = 0.5
COMMANDABLE_PROGRESSION_STATES = {"STEP_WAIT", "STEP_REACHED", "STEP_REACHED_GROUP_WAIT"}


class ControlGateError(ValueError):
    pass


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ControlGateError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlGateError(f"{label} must be numeric")
    return float(value)


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ControlGateError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlGateError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ControlGateError(f"{label} must be offset-aware")
    return dt.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _freshness(generated: datetime, now: datetime, max_age: int, label: str) -> dict[str, Any]:
    age = (now - generated).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return {"status": "INVALID", "reason": f"{label}_FROM_FUTURE", "ageSeconds": round(age, 1)}
    if age > max_age:
        return {"status": "STALE", "reason": f"{label}_STALE", "ageSeconds": round(age, 1)}
    return {"status": "OK", "reason": f"{label}_CURRENT", "ageSeconds": round(max(0.0, age), 1)}


def _room_map(payload: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    rooms = payload.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        raise ControlGateError(f"{label}.rooms must be a non-empty array")
    result = {}
    for room in rooms:
        room = _dict(room, f"{label}.room")
        key = room.get("key")
        if not isinstance(key, str) or not key:
            raise ControlGateError(f"{label} room key missing")
        if key in result:
            raise ControlGateError(f"duplicate {label} room key: {key}")
        result[key] = room
    return result


def _previous_room_map(previous: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(previous, dict):
        return {}
    if previous.get("schema") != PREVIOUS_SCHEMA:
        return {}
    if previous.get("mode") != "READ_ONLY" or previous.get("controlMode") != "SHADOW":
        return {}
    if previous.get("controlWrites") is not False or previous.get("physicalWriteAllowed") is not False:
        return {}
    return {
        room["key"]: room
        for room in previous.get("rooms") or []
        if isinstance(room, dict) and isinstance(room.get("key"), str)
    }


def _previous_ownership(room: dict[str, Any] | None) -> tuple[bool, str | None, float | None]:
    if not isinstance(room, dict):
        return False, None, None
    ownership = room.get("shadowOwnership")
    if not isinstance(ownership, dict) or ownership.get("wouldOwnOverride") is not True:
        return False, None, None
    opportunity_id = ownership.get("opportunityId")
    target = ownership.get("target_C")
    if not isinstance(opportunity_id, str) or not opportunity_id:
        return False, None, None
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        return False, None, None
    return True, opportunity_id, float(target)


def _opportunity_id(key: str, baseline: dict[str, Any]) -> str:
    close = baseline.get("changeAt")
    _aware(close, f"{key}.baseline.changeAt")
    target = _number(baseline.get("targetTemperature_C"), f"{key}.baseline.targetTemperature_C")
    return f"{key}|{close}|{target:.3f}"


def _validate_contracts(heating: dict[str, Any], progression: dict[str, Any]) -> None:
    if heating.get("schema") != HEATING_SCHEMA:
        raise ControlGateError(f"unexpected heating schema: {heating.get('schema')}")
    if heating.get("mode") != "READ_ONLY" or heating.get("controlMode") != "SHADOW":
        raise ControlGateError("Heating V0.3 must be READ_ONLY / SHADOW")
    if heating.get("controlWrites") is not False or heating.get("baselineAuthority") != "HONEYWELL":
        raise ControlGateError("Heating V0.3 write/authority contract invalid")

    if progression.get("schema") != PROGRESSION_SCHEMA:
        raise ControlGateError(f"unexpected progression schema: {progression.get('schema')}")
    if progression.get("mode") != "READ_ONLY" or progression.get("controlMode") != "SHADOW":
        raise ControlGateError("Heating V0.4 must be READ_ONLY / SHADOW")
    if progression.get("controlWrites") is not False or progression.get("physicalWriteAllowed") is not False:
        raise ControlGateError("Heating V0.4 must disallow writes")
    if progression.get("baselineAuthority") != "HONEYWELL":
        raise ControlGateError("Heating V0.4 baseline authority must be HONEYWELL")

    policy = _dict(progression.get("policy"), "progression.policy")
    if _number(policy.get("maxStep_C"), "progression.policy.maxStep_C") != MAX_STEP_C:
        raise ControlGateError("Heating V0.4 maxStep_C contract mismatch")
    if policy.get("plannerGrantRequiredForStartAndAdvance") is not True:
        raise ControlGateError("Heating V0.4 planner grant contract missing")
    if policy.get("intentionalGridImportAllowed") is not False:
        raise ControlGateError("Heating V0.4 may not allow intentional grid import")


def _first_failure(checks: dict[str, bool]) -> str:
    order = (
        ("sourcesFresh", "SOURCE_NOT_FRESH"),
        ("sourceOrder", "PROGRESSION_PRE_DATES_HEATING"),
        ("progressionUpstreamSafe", "PROGRESSION_UPSTREAM_NOT_SAFE"),
        ("v04NoPhysicalWrite", "PROGRESSION_WRITE_CONTRACT_INVALID"),
        ("preheatScope", "ROOM_OUT_OF_PREHEAT_SCOPE"),
        ("opportunityAligned", "OPPORTUNITY_ID_MISMATCH"),
        ("baselineUp", "BASELINE_NOT_UP"),
        ("cvSafe", "CV_GUARD_NOT_SAFE"),
        ("heatingReady", "HEATING_NOT_READY"),
        ("plannerGrant", "PLANNER_GRANT_NOT_PRESENT"),
        ("progressionState", "PROGRESSION_NOT_COMMANDABLE"),
        ("activeTargetNumeric", "NO_ACTIVE_STEP_TARGET"),
        ("targetAboveBaseline", "TARGET_NOT_ABOVE_HONEYWELL_BASELINE"),
        ("targetWithinFuture", "TARGET_EXCEEDS_HONEYWELL_FUTURE_TARGET"),
        ("stepBound", "TARGET_STEP_EXCEEDS_0_5C"),
    )
    for key, reason in order:
        if checks.get(key) is not True:
            return reason
    return "UNKNOWN_GUARD_FAILURE"


def _policy() -> dict[str, Any]:
    return {
        "maxStep_C": MAX_STEP_C,
        "baselineAuthority": "HONEYWELL",
        "plannerAuthority": "UPSTREAM_ONLY",
        "physicalWriteAllowed": False,
        "intentionalGridImportAllowed": False,
        "singlePhysicalWriterRequired": True,
        "futurePhysicalWriter": "HOMEY_HONEYWELL_ACTUATOR_ONLY",
        "rollbackBehavior": "RESET_TO_HONEYWELL_SCHEDULE_IF_SHADOW_OWNED",
        "shadowOwnershipIsPhysicalProof": False,
        "livePromotionRequires": "HOMEY_ACK_AND_HONEYWELL_READBACK",
    }


def build_fail_closed(
    previous: dict[str, Any] | None,
    *,
    reason: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ControlGateError("generated_at must be offset-aware")
    now = now.astimezone(timezone.utc)

    rooms = []
    for key, previous_room in sorted(_previous_room_map(previous).items()):
        owned, opportunity_id, target = _previous_ownership(previous_room)
        rooms.append({
            "key": key,
            "displayName": previous_room.get("displayName") or key,
            "preheatScope": previous_room.get("preheatScope") is True,
            "group": previous_room.get("group"),
            "checks": {
                "sourcesFresh": False, "sourceOrder": False,
                "progressionUpstreamSafe": False, "v04NoPhysicalWrite": False,
                "preheatScope": previous_room.get("preheatScope") is True,
                "opportunityAligned": False, "baselineUp": False, "cvSafe": False,
                "heatingReady": False, "plannerGrant": False,
                "progressionState": False, "activeTargetNumeric": False,
                "targetAboveBaseline": False, "targetWithinFuture": False,
                "stepBound": False,
            },
            "command": {
                "action": "WOULD_RESET_TO_SCHEDULE" if owned else "HOLD",
                "target_C": None,
                "reason": reason,
                "physicalWrite": False,
            },
            "shadowOwnership": {
                "wouldOwnOverride": False,
                "opportunityId": None,
                "target_C": None,
                "previouslyOwned": owned,
                "previousOpportunityId": opportunity_id,
                "previousTarget_C": target,
                "simulatedRollback": owned,
                "physicalOwnershipProven": False,
            },
        })

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "generatedAt": _iso(now),
        "baselineAuthority": "HONEYWELL",
        "sourceFreshness": {
            "heating": {"status": "UNKNOWN", "reason": reason, "ageSeconds": None},
            "progression": {"status": "UNKNOWN", "reason": reason, "ageSeconds": None},
            "progressionConsistentWithHeating": False,
            "progressionUpstreamSafe": False,
        },
        "failureReason": reason,
        "policy": _policy(),
        "lifecycle": {
            "state": "COMMISSIONING_SHADOW",
            "promotion": "REPLACE_OR_PROMOTE_AFTER_HOMEY_EDGE_ACK_READBACK_VALIDATION",
        },
        "rooms": rooms,
    }


def build_gate(
    heating: dict[str, Any],
    progression: dict[str, Any],
    previous: dict[str, Any] | None = None,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    _validate_contracts(heating, progression)
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ControlGateError("generated_at must be offset-aware")
    now = now.astimezone(timezone.utc)

    heating_generated = _aware(heating.get("generatedAt"), "heating.generatedAt")
    progression_generated = _aware(progression.get("generatedAt"), "progression.generatedAt")
    heating_freshness = _freshness(heating_generated, now, MAX_HEATING_AGE_SECONDS, "HEATING_SHADOW")
    progression_freshness = _freshness(
        progression_generated, now, MAX_PROGRESSION_AGE_SECONDS, "HEATING_PROGRESSION"
    )
    source_order = progression_generated >= heating_generated
    sources_fresh = heating_freshness["status"] == "OK" and progression_freshness["status"] == "OK"

    upstream = _dict(progression.get("sourceFreshness"), "progression.sourceFreshness")
    progression_upstream_safe = (
        _dict(upstream.get("heating"), "progression.sourceFreshness.heating").get("status") == "OK"
        and _dict(upstream.get("priority"), "progression.sourceFreshness.priority").get("status") == "OK"
        and upstream.get("priorityConsistentWithHeating") is True
    )

    heating_rooms = _room_map(heating, "heating")
    progression_rooms = _room_map(progression, "progression")
    if set(heating_rooms) != set(progression_rooms):
        raise ControlGateError("room key mismatch between V0.3 and V0.4")
    previous_rooms = _previous_room_map(previous)

    cv_guard = _dict(heating.get("cvGuard"), "heating.cvGuard")
    cv_safe = cv_guard.get("status") == "OK" and cv_guard.get("cvActive") is False

    output_rooms = []
    for key in sorted(heating_rooms):
        hroom = heating_rooms[key]
        proom = progression_rooms[key]
        previous_room = previous_rooms.get(key)
        baseline = _dict(hroom.get("baseline"), f"{key}.baseline")
        hstate = _dict(hroom.get("shadow"), f"{key}.shadow")
        eligibility = _dict(proom.get("heatingEligibility"), f"{key}.heatingEligibility")
        planner = _dict(proom.get("planner"), f"{key}.planner")
        pstate = _dict(proom.get("progression"), f"{key}.progression")

        if pstate.get("physicalWritePerformed") is not False:
            raise ControlGateError(f"{key} V0.4 physicalWritePerformed must be false")

        baseline_current = _number(
            baseline.get("currentTargetTemperature_C"),
            f"{key}.baseline.currentTargetTemperature_C",
        )
        future_target = _number(
            baseline.get("targetTemperature_C"),
            f"{key}.baseline.targetTemperature_C",
        )
        opportunity_id = _opportunity_id(key, baseline)
        progression_opportunity_id = proom.get("opportunityId")
        raw_target = pstate.get("activeStepTarget_C")
        target = (
            float(raw_target)
            if isinstance(raw_target, (int, float)) and not isinstance(raw_target, bool)
            else None
        )

        previously_owned, previous_opportunity_id, previous_target = _previous_ownership(previous_room)
        same_previous_opportunity = previously_owned and previous_opportunity_id == opportunity_id
        step_bound = True
        if target is not None and same_previous_opportunity and previous_target is not None:
            delta = target - previous_target
            step_bound = -1e-9 <= delta <= MAX_STEP_C + 1e-9

        checks = {
            "sourcesFresh": sources_fresh,
            "sourceOrder": source_order,
            "progressionUpstreamSafe": progression_upstream_safe,
            "v04NoPhysicalWrite": progression.get("physicalWriteAllowed") is False,
            "preheatScope": hroom.get("preheatScope") is True and proom.get("preheatScope") is True,
            "opportunityAligned": isinstance(progression_opportunity_id, str) and progression_opportunity_id == opportunity_id,
            "baselineUp": baseline.get("direction") == "UP",
            "cvSafe": cv_safe,
            "heatingReady": hstate.get("state") == "PREHEAT_READY_FOR_GRANT" and eligibility.get("state") == "PREHEAT_READY_FOR_GRANT",
            "plannerGrant": planner.get("domainGrant") == "SHADOW_GRANT",
            "progressionState": pstate.get("state") in COMMANDABLE_PROGRESSION_STATES,
            "activeTargetNumeric": target is not None,
            "targetAboveBaseline": target is not None and target > baseline_current,
            "targetWithinFuture": target is not None and target <= future_target + 1e-9,
            "stepBound": step_bound,
        }
        safe = all(checks.values())
        failure_reason = _first_failure(checks)

        if previously_owned and previous_opportunity_id != opportunity_id:
            action, reason, command_target, would_own, rollback = (
                "WOULD_RESET_TO_SCHEDULE", "OPPORTUNITY_CHANGED_BEFORE_NEW_COMMAND", None, False, True
            )
        elif safe:
            same_target = (
                previously_owned and previous_opportunity_id == opportunity_id
                and previous_target is not None and target is not None
                and abs(previous_target - target) <= 1e-9
            )
            action = "WOULD_KEEP_TEMP" if same_target else "WOULD_SET_TEMP"
            reason, command_target, would_own, rollback = "GUARDS_PASS_ACTIVE_STEP", target, True, False
        elif previously_owned:
            action, reason, command_target, would_own, rollback = (
                "WOULD_RESET_TO_SCHEDULE", failure_reason, None, False, True
            )
        else:
            action, reason, command_target, would_own, rollback = (
                "HOLD", failure_reason, None, False, False
            )

        output_rooms.append({
            "key": key,
            "displayName": hroom.get("displayName") or key,
            "preheatScope": hroom.get("preheatScope") is True,
            "group": hroom.get("group"),
            "opportunityId": opportunity_id,
            "baseline": {
                "currentTarget_C": baseline_current,
                "futureTarget_C": future_target,
                "direction": baseline.get("direction"),
                "changeAt": baseline.get("changeAt"),
            },
            "source": {
                "heatingState": hstate.get("state"),
                "heatingReason": hstate.get("reason"),
                "plannerGrant": planner.get("domainGrant"),
                "priorityReason": planner.get("priorityReason"),
                "progressionState": pstate.get("state"),
                "progressionReason": pstate.get("reason"),
                "activeStepTarget_C": target,
            },
            "checks": checks,
            "command": {
                "action": action, "target_C": command_target,
                "reason": reason, "physicalWrite": False,
            },
            "shadowOwnership": {
                "wouldOwnOverride": would_own,
                "opportunityId": opportunity_id if would_own else None,
                "target_C": command_target if would_own else None,
                "previouslyOwned": previously_owned,
                "previousOpportunityId": previous_opportunity_id,
                "previousTarget_C": previous_target,
                "simulatedRollback": rollback,
                "physicalOwnershipProven": False,
            },
        })

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "generatedAt": _iso(now),
        "baselineAuthority": "HONEYWELL",
        "sourceSchemas": {"heating": HEATING_SCHEMA, "progression": PROGRESSION_SCHEMA},
        "sourceFreshness": {
            "heating": heating_freshness,
            "progression": progression_freshness,
            "progressionConsistentWithHeating": source_order,
            "progressionUpstreamSafe": progression_upstream_safe,
        },
        "failureReason": None,
        "policy": _policy(),
        "lifecycle": {
            "state": "COMMISSIONING_SHADOW",
            "promotion": "REPLACE_OR_PROMOTE_AFTER_HOMEY_EDGE_ACK_READBACK_VALIDATION",
        },
        "rooms": output_rooms,
    }

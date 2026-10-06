#!/usr/bin/env python3
"""Build read-only cross-domain flex priority shadow state.

This layer ranks Heating Preheat versus EV opportunity/deadline urgency. It does
not reserve watts, select physical setpoints, write devices, or replace the
production Dynamic Pi Planner. Realtime opportunistic energy use remains gated
by P1 and existing executor safety.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HEATING_SCHEMA = "EMS_HEATING_PREHEAT_SHADOW_V0.3"
EV_SCHEMA = "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2"
OUTPUT_SCHEMA = "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"

MAX_HEATING_AGE_SECONDS = 420
MAX_FUTURE_SKEW_SECONDS = 30


class PriorityError(ValueError):
    pass


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PriorityError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PriorityError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise PriorityError(f"{label} must be offset-aware")
    return dt.astimezone(timezone.utc)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PriorityError(f"{label} must be numeric")
    return float(value)


def _freshness(generated: datetime, now: datetime, max_age: int, label: str) -> dict[str, Any]:
    age = (now - generated).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return {"status": "INVALID", "reason": f"{label}_FROM_FUTURE", "ageSeconds": round(age, 1)}
    if age > max_age:
        return {"status": "STALE", "reason": f"{label}_STALE", "ageSeconds": round(age, 1)}
    return {"status": "OK", "reason": f"{label}_CURRENT", "ageSeconds": round(max(0.0, age), 1)}


def _ready_heating(heating: dict[str, Any]) -> list[dict[str, Any]]:
    rooms = heating.get("rooms")
    if not isinstance(rooms, list):
        raise PriorityError("heating.rooms must be an array")

    ready = []
    for room in rooms:
        if not isinstance(room, dict):
            raise PriorityError("heating room must be an object")
        shadow = room.get("shadow")
        candidate = room.get("candidate")
        if not isinstance(shadow, dict) or not isinstance(candidate, dict):
            raise PriorityError("heating room shadow/candidate missing")
        if shadow.get("state") != "PREHEAT_READY_FOR_GRANT":
            continue
        closes = _aware(candidate.get("opportunityClosesAt"), f"{room.get('key')}.opportunityClosesAt")
        ready.append({
            "key": room.get("key"),
            "group": room.get("group"),
            "opportunityClosesAt": closes,
        })
    return ready


def build_priority(
    heating_shadow: dict[str, Any],
    ev_deadline: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    if heating_shadow.get("schema") != HEATING_SCHEMA:
        raise PriorityError(f"unexpected heating schema: {heating_shadow.get('schema')}")
    if heating_shadow.get("mode") != "READ_ONLY" or heating_shadow.get("controlMode") != "SHADOW":
        raise PriorityError("heating shadow must be READ_ONLY / SHADOW")
    if heating_shadow.get("controlWrites") is not False:
        raise PriorityError("heating shadow must disallow control writes")
    if ev_deadline.get("schema") != EV_SCHEMA:
        raise PriorityError(f"unexpected EV schema: {ev_deadline.get('schema')}")
    if ev_deadline.get("readOnly") is not True or ev_deadline.get("controlWrites") is not False:
        raise PriorityError("EV deadline source must be read-only")

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise PriorityError("generated_at must be offset-aware")
    now = now.astimezone(timezone.utc)

    heating_generated = _aware(heating_shadow.get("generatedAt"), "heating.generatedAt")
    heating_freshness = _freshness(
        heating_generated,
        now,
        MAX_HEATING_AGE_SECONDS,
        "HEATING_SHADOW",
    )
    source_status = heating_shadow.get("sourceStatus")
    source_valid = (
        not isinstance(source_status, dict)
        or source_status.get("status") == "OK"
    )
    source_reason = (
        source_status.get("reason")
        if isinstance(source_status, dict)
        else "LEGACY_V03_WITHOUT_SOURCE_STATUS"
    )
    heating_current = heating_freshness["status"] == "OK" and source_valid

    ready = _ready_heating(heating_shadow) if heating_current else []
    ready.sort(key=lambda item: item["opportunityClosesAt"])
    earliest_close = ready[0]["opportunityClosesAt"] if ready else None

    ev_active = ev_deadline.get("active") is True
    remaining_raw = ev_deadline.get("remainingKWh")
    remaining = _number(remaining_raw, "ev.remainingKWh") if remaining_raw is not None else 0.0
    ev_has_requirement = ev_active and remaining > 1e-9

    deadline_at = None
    latest_start = None
    ev_state = "NONE"

    if ev_has_requirement:
        status = ev_deadline.get("status")
        if status not in {"TRACKING", "EXPIRED"}:
            ev_state = "INVALID_OR_UNCERTAIN"
        else:
            try:
                deadline_at = _aware(ev_deadline.get("deadlineAt"), "ev.deadlineAt")
                latest_start = _aware(ev_deadline.get("latestStartAt"), "ev.latestStartAt")
            except PriorityError:
                ev_state = "INVALID_OR_UNCERTAIN"
            else:
                if status == "EXPIRED" or deadline_at <= now or latest_start <= now:
                    ev_state = "MUST"
                else:
                    ev_state = "AVAILABLE_LATER"

    if ev_state == "INVALID_OR_UNCERTAIN":
        owner = "HOLD_UNKNOWN"
        heating_grant = "HOLD"
        ev_role = "SAFETY_HOLD"
        reason = "EV_DEADLINE_STATE_NOT_SAFE_TO_DEPRIORITIZE"
    elif ev_state == "MUST":
        owner = "EV"
        heating_grant = "HOLD"
        ev_role = "MUST"
        reason = "EV_DEADLINE_MUST"
    elif not source_valid:
        owner = "HOLD_UNKNOWN"
        heating_grant = "HOLD"
        ev_role = "PRIMARY_OPPORTUNITY"
        reason = source_reason or "HEATING_SOURCE_INVALID"
    elif not heating_current:
        owner = "HOLD_UNKNOWN"
        heating_grant = "HOLD"
        ev_role = "PRIMARY_OPPORTUNITY"
        reason = heating_freshness["reason"]
    elif ready:
        if ev_state == "AVAILABLE_LATER" and latest_start is not None and earliest_close is not None and latest_start < earliest_close:
            owner = "EV"
            heating_grant = "HOLD"
            ev_role = "PRIMARY_OPPORTUNITY"
            reason = "EV_SLACK_CLOSES_BEFORE_HEATING_WINDOW"
        else:
            owner = "HEATING"
            heating_grant = "SHADOW_GRANT"
            ev_role = "RESIDUAL_OPPORTUNITY"
            reason = (
                "HEATING_WINDOW_CLOSES_FIRST"
                if ev_state == "AVAILABLE_LATER"
                else "HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE"
            )
    else:
        owner = "EV"
        heating_grant = "HOLD"
        ev_role = "PRIMARY_OPPORTUNITY"
        reason = "NO_HEATING_PREHEAT_CANDIDATE"

    return {
        "schema": OUTPUT_SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "authority": "DYNAMIC_PI_PLANNER_SHADOW",
        "sourceFreshness": {
            "heating": heating_freshness,
            "heatingSourceStatus": {
                "status": "OK" if source_valid else "INVALID",
                "reason": source_reason,
            },
        },
        "policy": {
            "strategy": "CONSTRAINT_FIRST_THEN_EARLIEST_CLOSING_FLEX",
            "powerReservationW": 0,
            "realtimeOpportunityAuthority": "P1",
            "evDeadlineMustOverridesHeating": True,
            "heatingUsesScarceWindow": True,
            "evMayUseResidualWhenHeatingFirst": True,
            "intentionalGridImportForHeatingAllowed": False,
        },
        "heating": {
            "readyRooms": [item["key"] for item in ready],
            "earliestOpportunityClosesAt": (
                earliest_close.isoformat().replace("+00:00", "Z") if earliest_close else None
            ),
        },
        "ev": {
            "deadlineActive": ev_active,
            "remainingKWh": round(max(0.0, remaining), 6),
            "urgency": ev_state,
            "deadlineAt": deadline_at.isoformat().replace("+00:00", "Z") if deadline_at else ev_deadline.get("deadlineAt"),
            "latestSafeStartAt": latest_start.isoformat().replace("+00:00", "Z") if latest_start else ev_deadline.get("latestStartAt"),
        },
        "decision": {
            "priorityOwner": owner,
            "heatingShadowGrant": heating_grant,
            "evRole": ev_role,
            "reason": reason,
            "appliesOnlyWhenPvOpportunityExists": True,
            "physicalWriteAllowed": False,
        },
    }

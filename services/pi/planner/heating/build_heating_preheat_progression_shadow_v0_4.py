#!/usr/bin/env python3
"""Build stateful Heating Preheat V0.4 progression SHADOW.

V0.4 is downstream of:
- Heating Preheat V0.3 eligibility/safety;
- Flex Priority Shadow V0.1 cross-domain grant.

It persists only a shadow "would-command" step state. It never writes Honeywell,
Homey, Quatt, CV, Power Intent or another physical/control surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

HEATING_SCHEMA = "EMS_HEATING_PREHEAT_SHADOW_V0.3"
PRIORITY_SCHEMA = "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"
PREVIOUS_SCHEMA = "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4"
OUTPUT_SCHEMA = PREVIOUS_SCHEMA

MAX_HEATING_AGE_SECONDS = 420
MAX_PRIORITY_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 30
STEP_REACHED_TOLERANCE_C = 0.0
MAX_STEP_C = 0.5
STEP_HISTORY_RETENTION_HOURS = 48
MAX_STEP_HISTORY_ITEMS = 128
OPPORTUNITY_HISTORY_RETENTION_HOURS = 48
MAX_OPPORTUNITY_HISTORY_ITEMS = 64


class ProgressionError(ValueError):
    pass


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProgressionError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProgressionError(f"{label} must be numeric")
    return float(value)


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ProgressionError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProgressionError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ProgressionError(f"{label} must be offset-aware")
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_age(generated: datetime, now: datetime) -> float:
    return (now - generated).total_seconds()


def _freshness(generated: datetime, now: datetime, max_age: int, label: str) -> dict[str, Any]:
    age = _source_age(generated, now)
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return {"status": "INVALID", "reason": f"{label}_FROM_FUTURE", "ageSeconds": round(age, 1)}
    if age > max_age:
        return {"status": "STALE", "reason": f"{label}_STALE", "ageSeconds": round(age, 1)}
    return {"status": "OK", "reason": f"{label}_CURRENT", "ageSeconds": round(max(0.0, age), 1)}


def _opportunity_id(room: dict[str, Any]) -> str:
    baseline = _dict(room.get("baseline"), "room.baseline")
    key = room.get("key")
    close = baseline.get("changeAt")
    target = baseline.get("targetTemperature_C")
    if not isinstance(key, str) or not key:
        raise ProgressionError("room key missing")
    _aware(close, f"{key}.baseline.changeAt")
    target_n = _number(target, f"{key}.baseline.targetTemperature_C")
    return f"{key}|{close}|{target_n:.3f}"


def _previous_room_map(previous: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(previous, dict) or previous.get("schema") != PREVIOUS_SCHEMA:
        return {}
    if previous.get("mode") != "READ_ONLY" or previous.get("controlMode") != "SHADOW":
        return {}
    if previous.get("controlWrites") is not False:
        return {}
    result = {}
    for room in previous.get("rooms") or []:
        if isinstance(room, dict) and isinstance(room.get("key"), str):
            result[room["key"]] = room
    return result


def _completed(previous_progression: dict[str, Any] | None) -> list[float]:
    values = previous_progression.get("completedSteps_C") if isinstance(previous_progression, dict) else None
    if not isinstance(values, list):
        return []
    out: list[float] = []
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            n = float(value)
            if n not in out:
                out.append(n)
    return out


def _step_history(previous_room: dict[str, Any] | None, now: datetime) -> list[dict[str, Any]]:
    values = previous_room.get("stepHistory") if isinstance(previous_room, dict) else None
    if not isinstance(values, list):
        return []

    cutoff = now - timedelta(hours=STEP_HISTORY_RETENTION_HOURS)
    out: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        opportunity_id = item.get("opportunityId")
        target = item.get("target_C")
        started_at = item.get("startedAt")
        ended_at = item.get("endedAt")
        outcome = item.get("outcome")
        reason = item.get("reason")
        if not isinstance(opportunity_id, str) or not opportunity_id:
            continue
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            continue
        if not isinstance(outcome, str) or not outcome:
            continue
        try:
            started_dt = _aware(started_at, "stepHistory.startedAt")
            ended_dt = _aware(ended_at, "stepHistory.endedAt")
        except ProgressionError:
            continue
        if ended_dt < started_dt or ended_dt < cutoff:
            continue
        out.append({
            "opportunityId": opportunity_id,
            "target_C": float(target),
            "startedAt": _iso(started_dt),
            "endedAt": _iso(ended_dt),
            "outcome": outcome,
            "reason": reason if isinstance(reason, str) else None,
        })

    out.sort(key=lambda item: item["startedAt"])
    return out[-MAX_STEP_HISTORY_ITEMS:]


def _opportunity_history(previous_room: dict[str, Any] | None, now: datetime) -> list[dict[str, Any]]:
    values = previous_room.get("opportunityHistory") if isinstance(previous_room, dict) else None
    if not isinstance(values, list):
        return []

    cutoff = now - timedelta(hours=OPPORTUNITY_HISTORY_RETENTION_HOURS)
    out: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        opportunity_id = item.get("opportunityId")
        opens_at = item.get("opensAt")
        closes_at = item.get("closesAt")
        target = item.get("target_C")
        if not isinstance(opportunity_id, str) or not opportunity_id:
            continue
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            continue
        try:
            opens_dt = _aware(opens_at, "opportunityHistory.opensAt")
            closes_dt = _aware(closes_at, "opportunityHistory.closesAt")
        except ProgressionError:
            continue
        if closes_dt < opens_dt or closes_dt < cutoff:
            continue
        out.append({
            "opportunityId": opportunity_id,
            "opensAt": _iso(opens_dt),
            "closesAt": _iso(closes_dt),
            "target_C": float(target),
        })

    out.sort(key=lambda item: item["opensAt"])
    return out[-MAX_OPPORTUNITY_HISTORY_ITEMS:]


def _record_opportunity_window(history: list[dict[str, Any]], room: dict[str, Any]) -> None:
    baseline = _dict(room.get("baseline"), "room.baseline")
    if baseline.get("direction") != "UP":
        return

    candidate = _dict(room.get("candidate"), "room.candidate")
    opportunity_id = _opportunity_id(room)
    opens_dt = _aware(candidate.get("opportunityOpensAt"), "candidate.opportunityOpensAt")
    closes_dt = _aware(candidate.get("opportunityClosesAt"), "candidate.opportunityClosesAt")
    if closes_dt < opens_dt:
        raise ProgressionError("candidate opportunity closes before it opens")
    target = _number(baseline.get("targetTemperature_C"), "baseline.targetTemperature_C")

    if any(item.get("opportunityId") == opportunity_id for item in history):
        return

    history.append({
        "opportunityId": opportunity_id,
        "opensAt": _iso(opens_dt),
        "closesAt": _iso(closes_dt),
        "target_C": target,
    })
    history.sort(key=lambda item: item["opensAt"])
    if len(history) > MAX_OPPORTUNITY_HISTORY_ITEMS:
        del history[:-MAX_OPPORTUNITY_HISTORY_ITEMS]


def _close_step_interval(
    history: list[dict[str, Any]],
    *,
    opportunity_id: str | None,
    target: Any,
    started_at: Any,
    ended_at: datetime,
    outcome: str,
    reason: str | None,
) -> None:
    if not isinstance(opportunity_id, str) or not opportunity_id:
        return
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        return
    try:
        started_dt = _aware(started_at, "activeStepStartedAt")
    except ProgressionError:
        return
    if started_dt > ended_at:
        return

    normalized_started = _iso(started_dt)
    normalized_target = float(target)
    identity = (opportunity_id, normalized_target, normalized_started)
    if any(
        (
            item.get("opportunityId"),
            item.get("target_C"),
            item.get("startedAt"),
        ) == identity
        for item in history
    ):
        return

    history.append({
        "opportunityId": opportunity_id,
        "target_C": normalized_target,
        "startedAt": normalized_started,
        "endedAt": _iso(ended_at),
        "outcome": outcome,
        "reason": reason,
    })
    history.sort(key=lambda item: item["startedAt"])
    if len(history) > MAX_STEP_HISTORY_ITEMS:
        del history[:-MAX_STEP_HISTORY_ITEMS]


def _next_increment(active: float, future_target: float) -> float | None:
    if active >= future_target:
        return None
    return round(min(future_target, active + MAX_STEP_C), 3)


def build_progression(
    heating_shadow: dict[str, Any],
    flex_priority: dict[str, Any],
    previous: dict[str, Any] | None = None,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    if heating_shadow.get("schema") != HEATING_SCHEMA:
        raise ProgressionError(f"unexpected heating schema: {heating_shadow.get('schema')}")
    if heating_shadow.get("mode") != "READ_ONLY" or heating_shadow.get("controlMode") != "SHADOW":
        raise ProgressionError("heating source must be READ_ONLY / SHADOW")
    if heating_shadow.get("controlWrites") is not False:
        raise ProgressionError("heating source must disallow writes")
    if heating_shadow.get("baselineAuthority") != "HONEYWELL":
        raise ProgressionError("Honeywell must remain baseline authority")

    if flex_priority.get("schema") != PRIORITY_SCHEMA:
        raise ProgressionError(f"unexpected priority schema: {flex_priority.get('schema')}")
    if flex_priority.get("mode") != "READ_ONLY" or flex_priority.get("controlMode") != "SHADOW":
        raise ProgressionError("priority source must be READ_ONLY / SHADOW")
    if flex_priority.get("controlWrites") is not False:
        raise ProgressionError("priority source must disallow writes")

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ProgressionError("generated_at must be offset-aware")
    now = now.astimezone(timezone.utc)

    heating_generated = _aware(heating_shadow.get("generatedAt"), "heating.generatedAt")
    priority_generated = _aware(flex_priority.get("generatedAt"), "priority.generatedAt")
    heating_freshness = _freshness(heating_generated, now, MAX_HEATING_AGE_SECONDS, "HEATING_SHADOW")
    priority_freshness = _freshness(priority_generated, now, MAX_PRIORITY_AGE_SECONDS, "FLEX_PRIORITY")

    priority_consistent = priority_generated >= heating_generated
    priority_safe = (
        heating_freshness["status"] == "OK"
        and priority_freshness["status"] == "OK"
        and priority_consistent
    )

    decision = _dict(flex_priority.get("decision"), "priority.decision")
    heating_priority = _dict(flex_priority.get("heating"), "priority.heating")
    ready_rooms_raw = heating_priority.get("readyRooms")
    if not isinstance(ready_rooms_raw, list) or any(not isinstance(v, str) for v in ready_rooms_raw):
        raise ProgressionError("priority.heating.readyRooms must be a string array")
    ready_rooms = set(ready_rooms_raw)

    domain_grant = (
        priority_safe
        and decision.get("priorityOwner") == "HEATING"
        and decision.get("heatingShadowGrant") == "SHADOW_GRANT"
        and decision.get("physicalWriteAllowed") is False
    )

    previous_rooms = _previous_room_map(previous)
    contexts: list[dict[str, Any]] = []

    rooms_raw = heating_shadow.get("rooms")
    if not isinstance(rooms_raw, list) or not rooms_raw:
        raise ProgressionError("heating.rooms must be a non-empty array")

    for room in rooms_raw:
        room = _dict(room, "heating room")
        key = room.get("key")
        if not isinstance(key, str) or not key:
            raise ProgressionError("heating room key missing")
        current = _dict(room.get("current"), f"{key}.current")
        baseline = _dict(room.get("baseline"), f"{key}.baseline")
        candidate = _dict(room.get("candidate"), f"{key}.candidate")
        shadow = _dict(room.get("shadow"), f"{key}.shadow")

        actual = _number(current.get("temperature_C"), f"{key}.current.temperature_C")
        future_target = _number(baseline.get("targetTemperature_C"), f"{key}.baseline.targetTemperature_C")
        opportunity_id = _opportunity_id(room)

        prev_room = previous_rooms.get(key)
        history = _step_history(prev_room, now)
        opportunity_history = _opportunity_history(prev_room, now)
        _record_opportunity_window(opportunity_history, room)
        raw_prev_prog = prev_room.get("progression") if isinstance(prev_room, dict) else None
        same_opportunity = (
            isinstance(prev_room, dict)
            and prev_room.get("opportunityId") == opportunity_id
            and isinstance(raw_prev_prog, dict)
        )

        if not same_opportunity and isinstance(raw_prev_prog, dict):
            _close_step_interval(
                history,
                opportunity_id=prev_room.get("opportunityId"),
                target=raw_prev_prog.get("activeStepTarget_C"),
                started_at=raw_prev_prog.get("activeStepStartedAt"),
                ended_at=now,
                outcome="OPPORTUNITY_CHANGED",
                reason="HONEYWELL_OPPORTUNITY_CHANGED",
            )

        prev_prog = raw_prev_prog if same_opportunity else None

        active_prev = None
        if isinstance(prev_prog, dict):
            value = prev_prog.get("activeStepTarget_C")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                active_prev = float(value)

        active_reached = (
            active_prev is not None
            and actual >= active_prev - STEP_REACHED_TOLERANCE_C
        )

        can_receive_grant = (
            shadow.get("state") == "PREHEAT_READY_FOR_GRANT"
            and domain_grant
            and key in ready_rooms
        )

        contexts.append({
            "room": room,
            "key": key,
            "group": room.get("group"),
            "actual": actual,
            "futureTarget": future_target,
            "opportunityId": opportunity_id,
            "prev": prev_prog,
            "activePrev": active_prev,
            "activeReached": active_reached,
            "completed": _completed(prev_prog),
            "stepHistory": history,
            "opportunityHistory": opportunity_history,
            "canReceiveGrant": can_receive_grant,
            "heatingState": shadow.get("state"),
            "heatingReason": shadow.get("reason"),
            "candidateNext": shadow.get("nextStepTarget_C"),
        })

    # A grouped opportunity advances only after every currently selected member
    # has an active step and has reached it. "Selected" means currently granted
    # or already carrying an active shadow step for the same group.
    group_wait: dict[str, bool] = {}
    groups = {c["group"] for c in contexts if isinstance(c["group"], str) and c["group"]}
    for group in groups:
        selected = [
            c for c in contexts
            if c["group"] == group and (c["canReceiveGrant"] or c["activePrev"] is not None)
        ]
        group_wait[group] = bool(selected) and not all(
            c["activePrev"] is not None and c["activeReached"] for c in selected
        )

    output_rooms: list[dict[str, Any]] = []
    for c in contexts:
        room = c["room"]
        key = c["key"]
        prev = c["prev"]
        active = c["activePrev"]
        reached = c["activeReached"]
        completed = list(c["completed"])
        step_history = list(c["stepHistory"])
        opportunity_history = list(c["opportunityHistory"])
        state = "INACTIVE"
        reason = c["heatingReason"] or "HEATING_NOT_READY"
        transition = "NONE"
        started_at = prev.get("activeStepStartedAt") if isinstance(prev, dict) else None
        last_transition_at = prev.get("lastTransitionAt") if isinstance(prev, dict) else None

        # V0.3 is the safety/eligibility authority. V0.4 never bypasses it.
        if c["heatingState"] == "BASELINE_HEATING":
            state = "ENDED_BASELINE_HEATING"
            reason = "BASELINE_HEATING_IS_NOT_PREHEAT"
            active = None
            reached = None
            started_at = None
            transition = "ENDED"
        elif c["heatingState"] == "PREHEAT_BLOCKED_CV_ASSIST":
            state = "BLOCKED_CV_ASSIST"
            reason = "CV_ASSIST_DURING_PURE_PREHEAT"
            transition = "BLOCKED"
        elif c["heatingState"] == "PREHEAT_BLOCKED_CV_STATUS_UNKNOWN":
            state = "BLOCKED_CV_STATUS_UNKNOWN"
            reason = c["heatingReason"] or "CV_STATUS_UNKNOWN"
            transition = "BLOCKED"
        elif c["heatingState"] != "PREHEAT_READY_FOR_GRANT":
            # If this opportunity became satisfied by measured temperature,
            # retain an explicit completion outcome rather than calling it a
            # generic inactive candidate.
            if (
                active is not None
                and c["actual"] >= c["futureTarget"] - STEP_REACHED_TOLERANCE_C
            ):
                if active not in completed:
                    completed.append(active)
                state = "COMPLETE_TARGET_REACHED"
                reason = "FUTURE_HONEYWELL_TARGET_REACHED"
                active = None
                reached = True
                started_at = None
                transition = "COMPLETED"
            else:
                state = "INACTIVE"
                reason = c["heatingReason"] or "HEATING_NOT_READY"
                active = None
                reached = None
                started_at = None
                transition = "RESET"
        elif not priority_safe:
            state = "STEP_HOLD_PRIORITY_UNKNOWN" if active is not None else "WAITING_FOR_FRESH_PRIORITY"
            reason = (
                "PRIORITY_PRE_DATES_HEATING_STATE"
                if priority_freshness["status"] == "OK"
                and heating_freshness["status"] == "OK"
                and not priority_consistent
                else priority_freshness["reason"]
                if priority_freshness["status"] != "OK"
                else heating_freshness["reason"]
            )
            transition = "HOLD"
        elif not c["canReceiveGrant"]:
            state = "STEP_HOLD_NO_GRANT" if active is not None else "WAITING_FOR_GRANT"
            reason = decision.get("reason") or "HEATING_NOT_GRANTED"
            transition = "HOLD"
        elif active is None:
            candidate_next = c["candidateNext"]
            if not isinstance(candidate_next, (int, float)) or isinstance(candidate_next, bool):
                state = "COMPLETE_NO_NEXT_STEP"
                reason = "NO_NEXT_THERMALLY_LEGAL_STEP"
                reached = None
                transition = "COMPLETED"
            else:
                active = float(candidate_next)
                reached = c["actual"] >= active - STEP_REACHED_TOLERANCE_C
                state = "STEP_REACHED" if reached else "STEP_WAIT"
                reason = "SHADOW_STEP_STARTED"
                started_at = _iso(now)
                transition = "STARTED_STEP"
        elif not reached:
            state = "STEP_WAIT"
            reason = "WAITING_FOR_MEASURED_TEMPERATURE"
            transition = "NONE"
        elif isinstance(c["group"], str) and c["group"] and group_wait.get(c["group"], False):
            state = "STEP_REACHED_GROUP_WAIT"
            reason = "WAITING_FOR_SELECTED_GROUP_ROOMS"
            transition = "HOLD"
        else:
            if active not in completed:
                completed.append(active)
            next_target = _next_increment(active, c["futureTarget"])
            if next_target is None:
                state = "COMPLETE_TARGET_REACHED"
                reason = "FUTURE_HONEYWELL_TARGET_REACHED"
                active = None
                reached = True
                started_at = None
                transition = "COMPLETED"
            else:
                active = next_target
                reached = c["actual"] >= active - STEP_REACHED_TOLERANCE_C
                state = "STEP_REACHED" if reached else "STEP_WAIT"
                reason = "ADVANCED_AFTER_MEASURED_STEP_COMPLETION"
                started_at = _iso(now)
                transition = "ADVANCED_STEP"

        previous_state = prev.get("state") if isinstance(prev, dict) else None
        previous_reason = prev.get("reason") if isinstance(prev, dict) else None
        previous_target = prev.get("activeStepTarget_C") if isinstance(prev, dict) else None
        previous_started_at = prev.get("activeStepStartedAt") if isinstance(prev, dict) else None
        previous_reached = prev.get("activeStepReached") if isinstance(prev, dict) else None
        previous_completed = _completed(prev)

        if (
            isinstance(previous_target, (int, float))
            and not isinstance(previous_target, bool)
            and previous_started_at
            and active != float(previous_target)
        ):
            interval_outcome = (
                "ADVANCED_STEP"
                if transition == "ADVANCED_STEP"
                else "TARGET_REACHED"
                if state == "COMPLETE_TARGET_REACHED"
                else "BASELINE_TAKEOVER"
                if state == "ENDED_BASELINE_HEATING"
                else "ENDED"
            )
            _close_step_interval(
                step_history,
                opportunity_id=c["opportunityId"],
                target=previous_target,
                started_at=previous_started_at,
                ended_at=now,
                outcome=interval_outcome,
                reason=reason,
            )

        progression_changed = (
            not isinstance(prev, dict)
            or state != previous_state
            or reason != previous_reason
            or active != previous_target
            or reached != previous_reached
            or completed != previous_completed
        )

        if progression_changed:
            if transition == "NONE":
                transition = "STATE_CHANGED"
            last_transition_at = _iso(now)
        elif isinstance(prev, dict):
            # lastTransition is event history, not an every-iteration status.
            # Keep the previous event/time when progression did not change.
            transition = prev.get("lastTransition") or "NONE"
            last_transition_at = prev.get("lastTransitionAt")

        next_after_active = None
        if active is not None:
            next_after_active = _next_increment(active, c["futureTarget"])

        output_rooms.append({
            "key": key,
            "displayName": room.get("displayName") or key,
            "preheatScope": room.get("preheatScope") is True,
            "group": c["group"],
            "opportunityId": c["opportunityId"],
            "currentTemperature_C": c["actual"],
            "futureHoneywellTarget_C": c["futureTarget"],
            "opportunityClosesAt": room.get("candidate", {}).get("opportunityClosesAt"),
            "heatingEligibility": {
                "state": c["heatingState"],
                "reason": c["heatingReason"],
            },
            "planner": {
                "domainGrant": "SHADOW_GRANT" if c["canReceiveGrant"] else "HOLD",
                "priorityReason": decision.get("reason"),
            },
            "opportunityHistory": opportunity_history,
            "stepHistory": step_history,
            "progression": {
                "state": state,
                "reason": reason,
                "activeStepTarget_C": active,
                "activeStepReached": reached,
                "activeStepStartedAt": started_at,
                "nextStepTarget_C": next_after_active,
                "completedSteps_C": completed,
                "lastTransition": transition,
                "lastTransitionAt": last_transition_at,
                "physicalWritePerformed": False,
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
        "eligibilityAuthority": HEATING_SCHEMA,
        "allocationAuthority": PRIORITY_SCHEMA,
        "sourceFreshness": {
            "heating": heating_freshness,
            "priority": priority_freshness,
            "priorityConsistentWithHeating": priority_consistent,
        },
        "policy": {
            "maxStep_C": MAX_STEP_C,
            "stepReachedTolerance_C": STEP_REACHED_TOLERANCE_C,
            "advanceOnlyAfterMeasuredStepReached": True,
            "groupAdvanceRequiresAllSelectedRoomsReached": True,
            "plannerGrantRequiredForStartAndAdvance": True,
            "cvGuardInheritedEveryIterationFromV03": True,
            "baselineDemandGuardInheritedFromV03": True,
            "intentionalGridImportAllowed": False,
            "rollbackBehavior": "NOT_DEFINED_SHADOW_ONLY",
            "statePersistence": "LOCAL_SHADOW_ARTIFACT",
            "stepHistoryRetentionHours": STEP_HISTORY_RETENTION_HOURS,
            "opportunityHistoryRetentionHours": OPPORTUNITY_HISTORY_RETENTION_HOURS,
        },
        "rooms": output_rooms,
    }

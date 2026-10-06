#!/usr/bin/env python3
"""Build the authoritative Dynamic Pi Planner Heating grant V0.1.

This module does not create a second planner or a separate PV pot. It projects
one explicit Heating grant from the already-existing Dynamic Pi Planner slot,
Heating V0.3 eligibility and Flex Priority arbitration.

Forecast and realtime truth deliberately remain separate:
- planner slot / evResidualExportW describes shared forward-looking opportunity
  after non-EV planned flex (WW/Quooker) and before EV residual consumption;
- canonical Pi P1 state is retained only as advisory observation in this artifact;
- fresh P1 import/export must be re-evaluated at the Homey execution edge before
  any physical Heating start or progression increment;
- Honeywell remains comfort/schedule authority.

The result is a planner grant only. It cannot write Homey or Honeywell and
physicalWriteAllowed is always false in V0.1.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

DYNAMIC_SCHEMA = "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3"
HEATING_SCHEMA = "EMS_HEATING_PREHEAT_SHADOW_V0.3"
PRIORITY_SCHEMA = "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"
OUTPUT_SCHEMA = "EMS_PI_DYNAMIC_HEATING_GRANT_V0.1"

SLOT_MINUTES = 15
MAX_HEATING_AGE_SECONDS = 420
MAX_PRIORITY_AGE_SECONDS = 120
MAX_P1_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 30


class HeatingGrantError(ValueError):
    pass


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HeatingGrantError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HeatingGrantError(f"{label} must be numeric")
    return float(value)


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise HeatingGrantError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HeatingGrantError(f"{label} invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise HeatingGrantError(f"{label} must be offset-aware")
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


def _document_time(doc: dict[str, Any], label: str) -> datetime:
    for key in ("generatedAt", "generated_at", "updatedAt", "createdAt"):
        if doc.get(key):
            return _aware(doc.get(key), f"{label}.{key}")
    meta = doc.get("meta")
    if isinstance(meta, dict):
        for key in ("generatedAt", "generated_at", "heartbeat_at", "source_sample_at"):
            if meta.get(key):
                return _aware(meta.get(key), f"{label}.meta.{key}")
    raise HeatingGrantError(f"{label} missing document timestamp")


def _validate_contracts(
    dynamic_plan: dict[str, Any],
    heating_shadow: dict[str, Any],
    flex_priority: dict[str, Any],
) -> None:
    if dynamic_plan.get("schema") != DYNAMIC_SCHEMA:
        raise HeatingGrantError(f"unexpected dynamic planner schema: {dynamic_plan.get('schema')}")
    if dynamic_plan.get("plannerOwner") != "PI":
        raise HeatingGrantError("Dynamic Pi Planner must remain plannerOwner=PI")
    if dynamic_plan.get("mode") != "PURE_SHADOW":
        raise HeatingGrantError("Dynamic Pi Planner V0.3 must remain PURE_SHADOW")
    if dynamic_plan.get("readOnly") is not True or dynamic_plan.get("control_writes") is not False:
        raise HeatingGrantError("Dynamic Pi Planner write contract invalid")

    if heating_shadow.get("schema") != HEATING_SCHEMA:
        raise HeatingGrantError(f"unexpected Heating V0.3 schema: {heating_shadow.get('schema')}")
    if heating_shadow.get("mode") != "READ_ONLY" or heating_shadow.get("controlMode") != "SHADOW":
        raise HeatingGrantError("Heating V0.3 must remain READ_ONLY / SHADOW")
    if heating_shadow.get("controlWrites") is not False:
        raise HeatingGrantError("Heating V0.3 must disallow writes")
    if heating_shadow.get("baselineAuthority") != "HONEYWELL":
        raise HeatingGrantError("Honeywell must remain baseline authority")

    if flex_priority.get("schema") != PRIORITY_SCHEMA:
        raise HeatingGrantError(f"unexpected Flex Priority schema: {flex_priority.get('schema')}")
    if flex_priority.get("mode") != "READ_ONLY" or flex_priority.get("controlMode") != "SHADOW":
        raise HeatingGrantError("Flex Priority must remain READ_ONLY / SHADOW")
    if flex_priority.get("controlWrites") is not False:
        raise HeatingGrantError("Flex Priority must disallow writes")

    decision = _dict(flex_priority.get("decision"), "flexPriority.decision")
    if decision.get("physicalWriteAllowed") is not False:
        raise HeatingGrantError("Flex Priority physicalWriteAllowed must be false")


def _current_slot(dynamic_plan: dict[str, Any], now: datetime) -> tuple[dict[str, Any], datetime, datetime] | None:
    candidate = None
    candidate_start = None
    for slot in dynamic_plan.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        raw_start = slot.get("slot_start_utc") or slot.get("start")
        if not raw_start:
            continue
        start = _aware(raw_start, "dynamicPlan.slot.start")
        end = start + timedelta(minutes=SLOT_MINUTES)
        if start <= now < end and (candidate_start is None or start > candidate_start):
            candidate = slot
            candidate_start = start
    if candidate is None or candidate_start is None:
        return None
    return candidate, candidate_start, candidate_start + timedelta(minutes=SLOT_MINUTES)


def _ready_rooms(heating_shadow: dict[str, Any], flex_priority: dict[str, Any]) -> list[str]:
    rooms = heating_shadow.get("rooms")
    if not isinstance(rooms, list):
        raise HeatingGrantError("heating.rooms must be an array")

    priority_heating = _dict(flex_priority.get("heating"), "flexPriority.heating")
    granted = priority_heating.get("readyRooms")
    if not isinstance(granted, list) or any(not isinstance(x, str) for x in granted):
        raise HeatingGrantError("flexPriority.heating.readyRooms must be a string array")
    granted_set = set(granted)

    ready: list[str] = []
    for room in rooms:
        room = _dict(room, "heating.room")
        key = room.get("key")
        if not isinstance(key, str) or not key:
            raise HeatingGrantError("heating room key missing")
        shadow = _dict(room.get("shadow"), f"{key}.shadow")
        if shadow.get("state") == "PREHEAT_READY_FOR_GRANT" and key in granted_set:
            ready.append(key)
    return sorted(ready)


def _revision(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "heatgrant-" + hashlib.sha256(raw).hexdigest()[:16]


def build_heating_grant(
    dynamic_plan: dict[str, Any],
    heating_shadow: dict[str, Any],
    flex_priority: dict[str, Any],
    energy_state: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    _validate_contracts(dynamic_plan, heating_shadow, flex_priority)

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise HeatingGrantError("generated_at must be offset-aware")
    now = now.astimezone(timezone.utc)

    plan_generated = _document_time(dynamic_plan, "dynamicPlan")
    plan_valid_until = _aware(dynamic_plan.get("validUntil"), "dynamicPlan.validUntil")
    heating_generated = _document_time(heating_shadow, "heating")
    priority_generated = _document_time(flex_priority, "flexPriority")
    p1_generated = _document_time(energy_state, "energyState")

    heating_freshness = _freshness(heating_generated, now, MAX_HEATING_AGE_SECONDS, "HEATING_SHADOW")
    priority_freshness = _freshness(priority_generated, now, MAX_PRIORITY_AGE_SECONDS, "FLEX_PRIORITY")
    p1_freshness = _freshness(p1_generated, now, MAX_P1_AGE_SECONDS, "P1_STATE")
    planner_current = plan_generated <= now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS) and now < plan_valid_until
    source_order = priority_generated >= heating_generated

    slot_info = _current_slot(dynamic_plan, now)
    current_slot = slot_info[0] if slot_info else None
    slot_start = slot_info[1] if slot_info else None
    slot_end = slot_info[2] if slot_info else None

    ready_rooms = _ready_rooms(heating_shadow, flex_priority)
    decision = _dict(flex_priority.get("decision"), "flexPriority.decision")
    priority_grants_heating = (
        decision.get("priorityOwner") == "HEATING"
        and decision.get("heatingShadowGrant") == "SHADOW_GRANT"
        and decision.get("physicalWriteAllowed") is False
        and bool(ready_rooms)
    )

    shared_residual_w = 0.0
    export_after_existing_flex_w = 0.0
    ev_planned_w = 0.0
    if current_slot is not None:
        shared_residual_w = max(
            0.0,
            _number(current_slot.get("evResidualExportW") or 0, "slot.evResidualExportW"),
        )
        export_after_existing_flex_w = max(
            0.0,
            _number(current_slot.get("gridExportAfterFlexW") or 0, "slot.gridExportAfterFlexW"),
        )
        ev_planned_w = max(
            0.0,
            _number(current_slot.get("evPlanW") or 0, "slot.evPlanW"),
        )

    grid = _dict(energy_state.get("grid"), "energyState.grid")
    p1_export_w = max(0.0, _number(grid.get("export_w") or 0, "energyState.grid.export_w"))
    p1_import_w = max(0.0, _number(grid.get("import_w") or 0, "energyState.grid.import_w"))
    realtime_allowed = (
        p1_freshness["status"] == "OK"
        and p1_export_w > 0.0
        and p1_import_w <= 0.0
    )

    sources_safe = (
        planner_current
        and heating_freshness["status"] == "OK"
        and priority_freshness["status"] == "OK"
        and source_order
        and current_slot is not None
    )

    # Planner/Flex authority only. Realtime P1 is enforced at the Homey execution edge.
    grant = sources_safe and priority_grants_heating

    if not planner_current:
        reason = "DYNAMIC_PLAN_STALE_OR_NOT_CURRENT"
    elif current_slot is None:
        reason = "NO_CURRENT_DYNAMIC_PLAN_SLOT"
    elif heating_freshness["status"] != "OK":
        reason = heating_freshness["reason"]
    elif priority_freshness["status"] != "OK":
        reason = priority_freshness["reason"]
    elif not source_order:
        reason = "FLEX_PRIORITY_PRE_DATES_HEATING"
    elif not ready_rooms:
        reason = "NO_HEATING_PREHEAT_CANDIDATE"
    elif not priority_grants_heating:
        reason = str(decision.get("reason") or "FLEX_PRIORITY_DID_NOT_GRANT_HEATING")
    elif shared_residual_w > 0.0:
        reason = "PRODUCTION_GRANT_PLANNED_SHARED_PV_OPPORTUNITY"
    else:
        reason = "PRODUCTION_GRANT_HEATING_PRIORITY_REALTIME_P1_REQUIRED"

    validity_candidates = [
        plan_valid_until,
        heating_generated + timedelta(seconds=MAX_HEATING_AGE_SECONDS),
        priority_generated + timedelta(seconds=MAX_PRIORITY_AGE_SECONDS),
    ]
    if slot_end is not None:
        validity_candidates.append(slot_end)
    valid_until = min(validity_candidates)

    revision_basis = {
        "schema": OUTPUT_SCHEMA,
        "planGeneratedAt": _iso(plan_generated),
        "slotStart": _iso(slot_start) if slot_start else None,
        "heatingGeneratedAt": _iso(heating_generated),
        "priorityGeneratedAt": _iso(priority_generated),
        "readyRooms": ready_rooms,
        "priorityOwner": decision.get("priorityOwner"),
        "priorityReason": decision.get("reason"),
        "sharedResidualBeforeEvW": round(shared_residual_w),
        "grant": grant,
    }

    return {
        "schema": OUTPUT_SCHEMA,
        "generatedAt": _iso(now),
        "validUntil": _iso(valid_until),
        "grantRevision": _revision(revision_basis),
        "mode": "PRODUCTION_PLANNER_GRANT",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "allocationAuthority": "DYNAMIC_PI_PLANNER",
        "realtimeAuthority": "P1_AT_HOMEY_EXECUTION_EDGE",
        "baselineAuthority": "HONEYWELL",
        "sourceSchemas": {
            "dynamicPlan": DYNAMIC_SCHEMA,
            "heating": HEATING_SCHEMA,
            "flexPriority": PRIORITY_SCHEMA,
        },
        "sourceFreshness": {
            "dynamicPlan": {
                "status": "OK" if planner_current else "STALE",
                "generatedAt": _iso(plan_generated),
                "validUntil": _iso(plan_valid_until),
            },
            "heating": heating_freshness,
            "flexPriority": priority_freshness,
            "p1": p1_freshness,
            "priorityConsistentWithHeating": source_order,
        },
        "forecastOpportunity": {
            "currentSlotStart": _iso(slot_start) if slot_start else None,
            "currentSlotEnd": _iso(slot_end) if slot_end else None,
            "sharedResidualBeforeEvW": round(shared_residual_w),
            "evPlannedW": round(ev_planned_w),
            "exportAfterExistingFlexW": round(export_after_existing_flex_w),
            "plannedOpportunityPresent": shared_residual_w > 0.0,
            "roleOfEvWhenHeatingFirst": "RESIDUAL_OPPORTUNITY",
            "powerReservationW": 0,
        },
        "p1Observation": {
            "advisoryOnly": True,
            "freshness": p1_freshness,
            "p1ExportW": round(p1_export_w),
            "p1ImportW": round(p1_import_w),
            "wouldAllowAtObservedSample": realtime_allowed,
        },
        "executionGuard": {
            "required": True,
            "authority": "P1_AT_HOMEY_EXECUTION_EDGE",
            "evaluatedByPiGrant": False,
            "freshRealtimeP1Required": True,
            "mustShowExport": True,
            "mustShowNoImport": True,
            "intentionalGridImportAllowed": False,
        },
        "heating": {
            "readyRooms": ready_rooms,
            "grant": "PRODUCTION_GRANT" if grant else "HOLD",
            "reason": reason,
            "priorityReason": decision.get("reason"),
            "priorityOwner": decision.get("priorityOwner"),
        },
        "policy": {
            "plannerGrantDoesNotAuthorizePhysicalExecution": True,
            "realtimeP1MustAuthorizeAtExecutionEdge": True,
            "heatingGetsFirstClaimOnlyWhenFlexPriorityGrants": True,
            "evUsesResidualWhenHeatingFirst": True,
            "noSeparatePvPot": True,
            "physicalWriteAllowed": False,
        },
    }

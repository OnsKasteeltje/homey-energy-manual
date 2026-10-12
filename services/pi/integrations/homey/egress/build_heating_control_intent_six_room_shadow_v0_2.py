#!/usr/bin/env python3
"""Build six-room Homey Heating SHADOW V0.2 intent from local JSON only.

No network, Logic publisher, Homey calls, runtime writes or actuator actions.
The proven V0.1 Homey chain is deliberately NOT modified or activated.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DATA = Path("/home/jeroen/ems/data")
SOURCE = DATA / "heating-control-gate-shadow-v0.5.json"
HONEYWELL = Path("/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json")

SOURCE_SCHEMA = "EMS_HEATING_CONTROL_GATE_SHADOW_V0.5"
OUTPUT_SCHEMA = "EMS_HEATING_CONTROL_INTENT_V0.2"
VENDOR_SCHEMA = "EMS_HONEYWELL_STATE_V0.2"
MAX_SOURCE_AGE_SECONDS = 120
MAX_VENDOR_AGE_SECONDS = 420
INTENT_VALID_SECONDS = 120

ROOM_DEVICES = {
    "woonkamer": "6a79bb86-8c02-43db-be22-6f51e01efc6d",
    "eetkamer": "dd7ef4a3-ed9f-4e4d-92bb-090502068421",
    "keuken": "b7aec05b-953f-41e1-a7b4-ad09c9bf911e",
    "serre": "13625cb2-8fb5-4466-a21f-7addd8d72a88",
    "douwe_slaapkamer": "f74252a1-2879-4967-ba2d-41f56364e39b",
    "erker_douwe": "f9db36cd-8c0f-4beb-aa28-0127597652cf",
}
ALLOWED_ROOM_KEYS = set(ROOM_DEVICES)
ACTION_MAP = {
    "HOLD": "HOLD",
    "WOULD_SET_TEMP": "SET_TEMP",
    "WOULD_KEEP_TEMP": "KEEP_TEMP",
    "WOULD_RESET_TO_SCHEDULE": "RESET_TO_SCHEDULE",
}


class IntentError(ValueError):
    pass


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise IntentError(f"{label} missing")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntentError(f"{label} invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise IntentError(f"{label} must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntentError(f"{label} must be numeric")
    return float(value)


def _semantic_revision(commands: list[dict[str, Any]]) -> str:
    semantic = json.dumps(
        commands,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "hcs2-" + hashlib.sha256(semantic).hexdigest()[:24]


def _fail_closed(reason: str, now: datetime, source_generated_at=None) -> dict[str, Any]:
    return {
        "schema": OUTPUT_SCHEMA,
        "generatedAt": _iso(now),
        "validUntil": _iso(now + timedelta(seconds=INTENT_VALID_SECONDS)),
        "sourceGeneratedAt": source_generated_at,
        "controlRevision": _semantic_revision([]),
        "valid": False,
        "status": "FAIL_CLOSED",
        "reason": reason,
        "readOnly": True,
        "controlMode": "SHADOW",
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "liveExecutionAllowed": False,
        "plannerAuthority": "SHADOW_ONLY",
        "executor": "HOMEY_SHADOW",
        "baselineAuthority": "HONEYWELL",
        "commands": [],
        "roomCount": 0,
        "safety": {
            "failClosed": True,
            "logicOnly": True,
            "noDeviceWrites": True,
            "singlePhysicalWriterRequired": True,
            "liveExecutionAllowed": False,
            "productionPlannerHeatingGrantPresent": False,
            "physicalOwnershipProven": False,
        },
        "livePromotionBlockedBy": [
            "PRODUCTION_DYNAMIC_PLANNER_HEATING_GRANT",
            "HOMEY_ACTUATOR_ACK_AND_HONEYWELL_READBACK",
        ],
    }


def _vendor_map(payload: dict[str, Any], now: datetime) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("schema") != VENDOR_SCHEMA:
        raise IntentError("Honeywell vendor schema invalid")
    if payload.get("mode") != "READ_ONLY":
        raise IntentError("Honeywell vendor must remain READ_ONLY")
    observed = _aware(payload.get("generatedAt"), "honeywell.generatedAt")
    age = (now - observed).total_seconds()
    if age < -30 or age > MAX_VENDOR_AGE_SECONDS:
        raise IntentError("Honeywell vendor snapshot not fresh")
    zones = payload.get("zones")
    if not isinstance(zones, list):
        raise IntentError("Honeywell zones missing")
    mapping = {}
    for zone in zones:
        if not isinstance(zone, dict) or not isinstance(zone.get("key"), str):
            raise IntentError("Honeywell zone invalid")
        key = zone["key"]
        if key in mapping:
            raise IntentError("Honeywell duplicate zone " + key)
        mapping[key] = zone
    if set(mapping) != ALLOWED_ROOM_KEYS:
        raise IntentError("Honeywell six-room key set mismatch")
    for key, zone in mapping.items():
        if zone.get("homeyDeviceId") != ROOM_DEVICES[key]:
            raise IntentError("Honeywell device ID mismatch for " + key)
    return mapping


def build_intent(source: dict[str, Any], honeywell: dict[str, Any], *, generated_at=None) -> dict[str, Any]:
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise IntentError("generated_at must be timezone-aware")
    now = now.astimezone(timezone.utc)

    source_generated_raw = source.get("generatedAt") if isinstance(source, dict) else None
    try:
        if not isinstance(source, dict):
            raise IntentError("source must be object")
        if source.get("schema") != SOURCE_SCHEMA:
            raise IntentError("source schema invalid")
        if source.get("mode") != "READ_ONLY" or source.get("controlMode") != "SHADOW":
            raise IntentError("source must remain READ_ONLY/SHADOW")
        if source.get("controlWrites") is not False:
            raise IntentError("source controlWrites boundary invalid")
        if source.get("physicalWriteAllowed") is not False:
            raise IntentError("source physicalWriteAllowed boundary invalid")
        if source.get("baselineAuthority") != "HONEYWELL":
            raise IntentError("source baseline authority invalid")

        source_generated = _aware(source_generated_raw, "source.generatedAt")
        source_age = (now - source_generated).total_seconds()
        if source_age < -30:
            raise IntentError("source generatedAt from future")
        if source_age > MAX_SOURCE_AGE_SECONDS:
            raise IntentError("source stale")

        freshness = source.get("sourceFreshness")
        if not isinstance(freshness, dict):
            raise IntentError("source freshness missing")
        if (freshness.get("heating") or {}).get("status") != "OK":
            raise IntentError("source heating freshness invalid")
        if (freshness.get("progression") or {}).get("status") != "OK":
            raise IntentError("source progression freshness invalid")
        if freshness.get("progressionConsistentWithHeating") is not True:
            raise IntentError("source ordering invalid")
        if freshness.get("progressionUpstreamSafe") is not True:
            raise IntentError("source upstream safety invalid")

        vendor = _vendor_map(honeywell, now)
        commands = []
        seen = set()
        for room in source.get("rooms") or []:
            if not isinstance(room, dict) or room.get("preheatScope") is not True:
                continue
            key = room.get("key")
            if key not in ALLOWED_ROOM_KEYS or key in seen:
                raise IntentError(f"invalid or duplicate room key: {key}")
            seen.add(key)

            command = room.get("command")
            baseline = room.get("baseline")
            ownership = room.get("shadowOwnership")
            if not isinstance(command, dict) or not isinstance(baseline, dict):
                raise IntentError(f"{key} command/baseline invalid")
            if command.get("physicalWrite") is not False:
                raise IntentError(f"{key} physicalWrite must remain false")
            if not isinstance(ownership, dict) or ownership.get("physicalOwnershipProven") is not False:
                raise IntentError(f"{key} physical ownership must remain unproven")

            source_action = command.get("action")
            action = ACTION_MAP.get(source_action)
            if action is None:
                raise IntentError(f"{key} source action unsupported: {source_action}")
            if action in {"SET_TEMP", "KEEP_TEMP"}:
                if ownership.get("wouldOwnOverride") is not True:
                    raise IntentError(f"{key} set/keep requires shadow ownership")
                if ownership.get("simulatedRollback") is not False:
                    raise IntentError(f"{key} set/keep cannot be rollback")
            elif action == "RESET_TO_SCHEDULE":
                if ownership.get("simulatedRollback") is not True:
                    raise IntentError(f"{key} reset requires simulated rollback ownership")
                if ownership.get("wouldOwnOverride") is not False:
                    raise IntentError(f"{key} reset cannot retain shadow ownership")

            current_target = _number(
                baseline.get("currentTarget_C"), f"{key}.baseline.currentTarget_C"
            )
            future_target = _number(
                baseline.get("futureTarget_C"), f"{key}.baseline.futureTarget_C"
            )
            schedule_change_at = baseline.get("changeAt")
            if schedule_change_at is not None:
                _aware(schedule_change_at, f"{key}.baseline.changeAt")

            raw_target = command.get("target_C")
            if action in {"SET_TEMP", "KEEP_TEMP"}:
                target = _number(raw_target, f"{key}.command.target_C")
                if not (target > current_target and target <= future_target + 1e-9):
                    raise IntentError(f"{key} target outside Honeywell baseline/future bounds")
            else:
                if raw_target is not None:
                    raise IntentError(f"{key} non-set action must not carry target")
                target = None

            zone = vendor[key]
            vendor_mode = str(zone.get("setpointMode") or "").lower()
            vendor_target = _number(zone.get("targetTemperature_C"), key + ".honeywell.targetTemperature_C")
            override_until = zone.get("overrideUntil")
            # Human authority wins over any hypothetical V0.5 SET, KEEP or RESET.
            # A stale/mismatched target is also a HOLD, never an inferred write.
            hold_reason = None
            if vendor_mode in {"permanent_override", "temporary_override"}:
                hold_reason = "HONEYWELL_OVERRIDE_ACTIVE"
            elif vendor_mode != "follow_schedule":
                hold_reason = "HONEYWELL_MODE_UNKNOWN"
            elif override_until not in (None, ""):
                hold_reason = "HONEYWELL_OVERRIDE_UNTIL_UNEXPECTED"
            elif abs(vendor_target - current_target) > 0.01:
                hold_reason = "HONEYWELL_TARGET_MISMATCH"

            candidate_action = action
            if hold_reason is not None:
                action = "HOLD"
                target = None

            commands.append({
                "roomKey": key,
                "homeyDeviceId": ROOM_DEVICES[key],
                "displayName": room.get("displayName") or key,
                "group": room.get("group"),
                "opportunityId": room.get("opportunityId"),
                "action": action,
                "sourceShadowAction": candidate_action,
                "target_C": target,
                "baselineCurrentTarget_C": current_target,
                "futureHoneywellTarget_C": future_target,
                "scheduleChangeAt": schedule_change_at,
                "reason": hold_reason or command.get("reason"),
                "holdReason": hold_reason,
                "vendorSetpointMode": vendor_mode,
                "vendorTarget_C": vendor_target,
                "vendorOverrideUntil": override_until,
                "wouldWrite": hold_reason is None and action in {"SET_TEMP", "RESET_TO_SCHEDULE"},
                "physicalWrite": False,
                "shadowOwnership": {
                    "wouldOwnOverride": hold_reason is None and ownership.get("wouldOwnOverride") is True,
                    "simulatedRollback": hold_reason is None and ownership.get("simulatedRollback") is True,
                    "physicalOwnershipProven": False,
                },
            })

        missing = ALLOWED_ROOM_KEYS - seen
        if missing:
            raise IntentError("missing preheat rooms: " + ",".join(sorted(missing)))

        revision = _semantic_revision(commands)
        return {
            "schema": OUTPUT_SCHEMA,
            "generatedAt": _iso(now),
            "validUntil": _iso(now + timedelta(seconds=INTENT_VALID_SECONDS)),
            "sourceGeneratedAt": source_generated_raw,
            "vendorGeneratedAt": honeywell.get("generatedAt"),
            "sourceAgeSeconds": round(max(0.0, source_age), 1),
            "controlRevision": revision,
            "valid": True,
            "status": "OK",
            "reason": "V0_5_SHADOW_CONTRACT_VALID",
            "readOnly": True,
            "controlMode": "SHADOW",
            "deviceWrites": False,
            "physicalWriteAllowed": False,
            "liveExecutionAllowed": False,
            "plannerAuthority": "SHADOW_ONLY",
            "executor": "HOMEY_SHADOW",
            "baselineAuthority": "HONEYWELL",
            "commands": commands,
            "roomCount": len(commands),
            "safety": {
                "failClosed": True,
                "logicOnly": True,
                "noDeviceWrites": True,
                "singlePhysicalWriterRequired": True,
                "liveExecutionAllowed": False,
                "productionPlannerHeatingGrantPresent": False,
                "physicalOwnershipProven": False,
            },
            "livePromotionBlockedBy": [
                "PRODUCTION_DYNAMIC_PLANNER_HEATING_GRANT",
                "HOMEY_ACTUATOR_ACK_AND_HONEYWELL_READBACK",
            ],
        }
    except IntentError as exc:
        return _fail_closed(
            f"V0_5_SOURCE_INVALID_{str(exc).upper().replace(' ', '_')}",
            now,
            source_generated_raw,
        )



def main() -> None:
    # Manual on-Pi validation only; print to stdout, no publisher or disk writes.
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--honeywell", type=Path, default=HONEYWELL)
    args = parser.parse_args()
    try:
        source = json.loads(args.source.read_text(encoding="utf-8"))
        honeywell = json.loads(args.honeywell.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result = _fail_closed("SOURCE_UNAVAILABLE_" + type(exc).__name__, datetime.now(timezone.utc))
    else:
        result = build_intent(source, honeywell)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

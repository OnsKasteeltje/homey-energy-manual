#!/usr/bin/env python3
"""Publish Heating Control Gate V0.5 to a dedicated Homey SHADOW intent bus."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DATA = Path("/home/jeroen/ems/data")
SOURCE = DATA / "heating-control-gate-shadow-v0.5.json"
CONFIG = DATA / "heating-control-homey-shadow-config.json"
STATUS = DATA / "heating-control-homey-shadow-publish-status.json"

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"

SOURCE_SCHEMA = "EMS_HEATING_CONTROL_GATE_SHADOW_V0.5"
OUTPUT_SCHEMA = "EMS_HEATING_CONTROL_INTENT_V0.1"
CONFIG_SCHEMA = "EMS_HEATING_HOMEY_SHADOW_CONFIG_V0.1"
MAX_SOURCE_AGE_SECONDS = 120
INTENT_VALID_SECONDS = 120

ALLOWED_ROOM_KEYS = {"woonkamer", "eetkamer", "keuken", "serre"}
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
    return "hcs1-" + hashlib.sha256(semantic).hexdigest()[:24]


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
        "plannerAuthority": "SHADOW_ONLY",
        "executor": "HOMEY_SHADOW",
        "baselineAuthority": "HONEYWELL",
        "commands": [],
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


def build_intent(source: dict[str, Any], *, generated_at=None) -> dict[str, Any]:
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

            commands.append({
                "roomKey": key,
                "displayName": room.get("displayName") or key,
                "group": room.get("group"),
                "opportunityId": room.get("opportunityId"),
                "action": action,
                "target_C": target,
                "baselineCurrentTarget_C": current_target,
                "futureHoneywellTarget_C": future_target,
                "scheduleChangeAt": schedule_change_at,
                "reason": command.get("reason"),
                "wouldWrite": action in {"SET_TEMP", "RESET_TO_SCHEDULE"},
                "physicalWrite": False,
                "shadowOwnership": {
                    "wouldOwnOverride": ownership.get("wouldOwnOverride") is True,
                    "simulatedRollback": ownership.get("simulatedRollback") is True,
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
            "sourceAgeSeconds": round(max(0.0, source_age), 1),
            "controlRevision": revision,
            "valid": True,
            "status": "OK",
            "reason": "V0_5_SHADOW_CONTRACT_VALID",
            "readOnly": True,
            "controlMode": "SHADOW",
            "deviceWrites": False,
            "physicalWriteAllowed": False,
            "plannerAuthority": "SHADOW_ONLY",
            "executor": "HOMEY_SHADOW",
            "baselineAuthority": "HONEYWELL",
            "commands": commands,
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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_homey(args: list[str]) -> str:
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")
    proc = subprocess.run(
        [str(HOMEY_CLI)] + args,
        cwd=HOMEY_PROJECT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        if "too many requests" in message.lower() or "429" in message:
            raise RuntimeError("HOMEY_RATE_LIMIT_429_NO_RETRY")
        raise RuntimeError("HOMEY_CLI_FAILED:" + message[:800])
    return proc.stdout


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _publish_logic(var_id: str, intent: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".heating-intent-", suffix=".json", dir=DATA, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {"value": json.dumps(intent, separators=(",", ":"), ensure_ascii=False)},
                handle,
                separators=(",", ":"),
            )
            handle.write("\n")
        _run_homey([
            "api", "logic", "update-variable",
            "--id", var_id,
            "--body", f"@{tmp}",
            "--json",
        ])
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def main() -> int:
    now = datetime.now(timezone.utc)
    try:
        config = _load_json(CONFIG)
    except Exception as exc:
        raise SystemExit(f"FAIL_CLOSED: Homey Heating SHADOW config unavailable: {exc}")

    if config.get("schema") != CONFIG_SCHEMA:
        raise SystemExit("FAIL_CLOSED: Homey Heating SHADOW config schema invalid")
    intent_var_id = ((config.get("logic") or {}).get("intent") or {}).get("id")
    if not isinstance(intent_var_id, str) or not intent_var_id:
        raise SystemExit("FAIL_CLOSED: Homey Heating intent variable ID missing")

    try:
        source = _load_json(SOURCE)
    except Exception as exc:
        source = {}
        source_error = f"SOURCE_UNAVAILABLE_{type(exc).__name__}"
    else:
        source_error = None

    intent = build_intent(source, generated_at=now)
    if source_error:
        intent = _fail_closed(source_error, now, None)

    status = {
        "schema": "EMS_HEATING_HOMEY_SHADOW_PUBLISH_STATUS_V0.1",
        "generatedAt": _iso(now),
        "sourceGeneratedAt": intent.get("sourceGeneratedAt"),
        "controlRevision": intent.get("controlRevision"),
        "intentValid": intent.get("valid"),
        "intentStatus": intent.get("status"),
        "intentReason": intent.get("reason"),
        "homeyLogicWrite": False,
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "targetVariableId": intent_var_id,
    }

    try:
        _publish_logic(intent_var_id, intent)
        status["homeyLogicWrite"] = True
        status["publishStatus"] = "OK"
        _atomic_json(STATUS, status)
    except Exception as exc:
        status["publishStatus"] = "FAILED"
        status["error"] = str(exc)[:500]
        _atomic_json(STATUS, status)
        raise SystemExit(f"FAIL_CLOSED: Heating SHADOW intent publish failed: {exc}")

    print(
        "PASS: Heating V0.5 -> Homey SHADOW intent "
        f"valid={intent['valid']} revision={intent['controlRevision']}"
    )
    for command in intent.get("commands") or []:
        print(command["roomKey"], command["action"], command["target_C"], command["reason"])
    print("deviceWrites: false")
    print("physicalWriteAllowed: false")
    return 0


if __name__ == "__main__":
    sys.exit(main())

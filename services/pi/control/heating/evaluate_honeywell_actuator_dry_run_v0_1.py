#!/usr/bin/env python3
"""Six-room Honeywell actuation DRY-RUN V0.1. Local JSON in, stdout JSON out.

No network, Homey access, Honeywell API access, device write, or runtime timer.
A prospective candidate is not a physical permission or ownership proof.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "EMS_HEATING_HONEYWELL_ACTUATOR_DRY_RUN_V0.1"
ROOM_IDS = {
    "woonkamer": "6a79bb86-8c02-43db-be22-6f51e01efc6d",
    "eetkamer": "dd7ef4a3-ed9f-4e4d-92bb-090502068421",
    "keuken": "b7aec05b-953f-41e1-a7b4-ad09c9bf911e",
    "serre": "13625cb2-8fb5-4466-a21f-7addd8d72a88",
    "douwe_slaapkamer": "f74252a1-2879-4967-ba2d-41f56364e39b",
    "erker_douwe": "f9db36cd-8c0f-4beb-aa28-0127597652cf",
}
# The 4-room SHADOW Homey bridge is deliberately NOT touched by this evaluator.
DATA = Path("/home/jeroen/ems/data")
DEFAULTS = {
    "heating": DATA / "heating-preheat-shadow-v0.3.json",
    "gate": DATA / "heating-control-gate-shadow-v0.5.json",
    "grant": DATA / "heating-production-grant-v0.1.json",
    "honeywell": Path("/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json"),
    "p1": DATA / "energy-state-v2.json",
}
# Evidence-check horizons, not settings of any live actuator.
MAX_AGE = {"heating": 420, "gate": 120, "grant": 120, "honeywell": 420, "p1": 120}
FUTURE_SKEW_SECONDS = 30


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def room_map(items: Any) -> dict[str, dict] | None:
    if not isinstance(items, list):
        return None
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            return None
        if item["key"] in result:
            return None
        result[item["key"]] = item
    return result


def fresh(value: Any, now: datetime, max_age_seconds: int) -> bool:
    at = timestamp(value)
    return at is not None and -FUTURE_SKEW_SECONDS <= (now - at).total_seconds() <= max_age_seconds


def check_source(name: str, data: dict, now: datetime) -> str | None:
    requirements = {
        "heating": ("EMS_HEATING_PREHEAT_SHADOW_V0.3", "READ_ONLY", "SHADOW"),
        "gate": ("EMS_HEATING_CONTROL_GATE_SHADOW_V0.5", "READ_ONLY", "SHADOW"),
        "grant": ("EMS_PI_DYNAMIC_HEATING_GRANT_V0.1", "PRODUCTION_PLANNER_GRANT", None),
        "honeywell": ("EMS_HONEYWELL_STATE_V0.2", "READ_ONLY", None),
        "p1": (None, None, None),
    }
    schema, mode, control_mode = requirements[name]
    if schema and data.get("schema") != schema:
        return f"{name.upper()}_SCHEMA_INVALID"
    if mode and data.get("mode") != mode:
        return f"{name.upper()}_MODE_INVALID"
    if control_mode and data.get("controlMode") != control_mode:
        return f"{name.upper()}_CONTROL_MODE_INVALID"
    if name in ("heating", "gate") and data.get("controlWrites") is not False:
        return f"{name.upper()}_WRITE_GUARD_INVALID"
    if name in ("gate", "grant") and data.get("physicalWriteAllowed") is not False:
        return f"{name.upper()}_WRITE_GUARD_INVALID"
    if name in ("heating", "gate", "grant") and data.get("baselineAuthority") != "HONEYWELL":
        return f"{name.upper()}_BASELINE_AUTHORITY_INVALID"
    if name == "grant" and data.get("allocationAuthority") != "DYNAMIC_PI_PLANNER":
        return "GRANT_PLANNER_AUTHORITY_INVALID"
    # For P1 use the actual P1 measurement timestamp, not a republished snapshot time.
    at = obj(data.get("meta")).get("source_sample_at") if name == "p1" else data.get("generatedAt")
    if not fresh(at, now, MAX_AGE[name]):
        return f"{name.upper()}_SOURCE_STALE_OR_UNTIMED"
    return None


def evaluate(docs: dict[str, Any], *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include UTC offset")
    now = now.astimezone(timezone.utc)
    iso = now.isoformat().replace("+00:00", "Z")
    data = {name: obj(docs.get(name)) for name in DEFAULTS}
    global_reasons = [reason for name, document in data.items()
                      if (reason := check_source(name, document, now))]
    if timestamp(data["grant"].get("validUntil")) is None or timestamp(data["grant"].get("validUntil")) <= now:
        global_reasons.append("GRANT_EXPIRED")
    if obj(data["grant"].get("heating")).get("grant") != "PRODUCTION_GRANT":
        global_reasons.append("NO_PRODUCTION_HEATING_GRANT")
    for name in ("heating", "gate", "grant"):
        age = timestamp(data[name].get("generatedAt"))
        if age and age > now.replace(tzinfo=timezone.utc):
            # Recent future skew permitted by freshness check, but never physical execution.
            global_reasons.append(f"{name.upper()}_FROM_FUTURE")
    heat, gate, vendor = (room_map(data[k].get("rooms" if k != "honeywell" else "zones"))
                          for k in ("heating", "gate", "honeywell"))
    if any(x is None for x in (heat, gate, vendor)):
        global_reasons.append("DUPLICATE_OR_INVALID_ROOM_KEYS")
    if not isinstance(obj(data["grant"].get("heating")).get("readyRooms"), list):
        global_reasons.append("GRANT_ROOM_LIST_INVALID")
    p1 = obj(data["p1"].get("grid"))
    export_w = numeric(p1.get("export_w"))
    import_w = numeric(p1.get("import_w"))
    if export_w is None or import_w is None or export_w < 0 or import_w < 0:
        global_reasons.append("P1_GRID_POWER_INVALID")
    elif export_w <= 0 or import_w > 0:
        global_reasons.append("P1_NOT_EXPORTING_WITHOUT_IMPORT")
    if data["gate"].get("sourceFreshness") and (
        obj(obj(data["gate"]["sourceFreshness"]).get("heating")).get("status") != "OK"
        or obj(obj(data["gate"]["sourceFreshness"]).get("progression")).get("status") != "OK"
        or obj(data["gate"]["sourceFreshness"]).get("progressionConsistentWithHeating") is not True
        or obj(data["gate"]["sourceFreshness"]).get("progressionUpstreamSafe") is not True
    ):
        global_reasons.append("V05_UPSTREAM_NOT_SAFE")
    if data["gate"].get("sourceFreshness") is None:
        global_reasons.append("V05_SOURCE_EVIDENCE_MISSING")
    results = []
    for key, device_id in ROOM_IDS.items():
        h = (heat or {}).get(key)
        g = (gate or {}).get(key)
        v = (vendor or {}).get(key)
        reasons = list(dict.fromkeys(global_reasons))
        if not h or not g or not v:
            reasons.append("ROOM_SOURCE_MISSING")
        if v and v.get("homeyDeviceId") != device_id:
            reasons.append("HONEYWELL_DEVICE_ID_MISMATCH")
        vendor_mode = str(v.get("setpointMode") or "").lower() if v else None
        effective = obj(h.get("effective")) if h else {}
        effective_mode = str(effective.get("setpointMode") or "").lower()
        if v and vendor_mode != "follow_schedule":
            reasons.append("HONEYWELL_OVERRIDE_ACTIVE" if vendor_mode in ("permanent_override", "temporary_override")
                           else "HONEYWELL_MODE_UNKNOWN")
        if h and effective_mode != "follow_schedule":
            reasons.append("UPSTREAM_HONEYWELL_OVERRIDE_OR_MODE")
        if h and effective.get("preheatAdvanceAllowed") is not True:
            reasons.append("HONEYWELL_PREHEAT_NOT_ALLOWED")
        if h and v:
            actual = numeric(v.get("targetTemperature_C"))
            upstream = numeric(effective.get("currentTargetTemperature_C"))
            if actual is None or upstream is None or abs(actual - upstream) > 0.01:
                reasons.append("HONEYWELL_TARGET_MISMATCH")
            if effective.get("systemMode") != obj(data["honeywell"].get("location")).get("systemMode"):
                reasons.append("HONEYWELL_SYSTEM_MODE_MISMATCH")
        # Existing preheatScope indicates the 4-room SHADOW migration state, NOT permanent eligibility.
        if h and h.get("preheatScope") is not True:
            reasons.append("UPSTREAM_SIX_ROOM_SCOPE_MIGRATION_REQUIRED")
        if g and g.get("preheatScope") is not True:
            reasons.append("V05_SIX_ROOM_SCOPE_MIGRATION_REQUIRED")
        if g and obj(g.get("command")).get("action") not in ("WOULD_SET_TEMP", "WOULD_KEEP_TEMP"):
            reasons.append("V05_NO_SET_OR_KEEP_CANDIDATE")
        if g and (not isinstance(g.get("checks"), dict) or not all(val is True for val in g["checks"].values())):
            reasons.append("V05_ROOM_CHECKS_NOT_ALL_TRUE")
        if g and obj(g.get("command")).get("physicalWrite") is not False:
            reasons.append("V05_COMMAND_WRITE_CONTRACT_INVALID")
        ready = obj(data["grant"].get("heating")).get("readyRooms")
        if not isinstance(ready, list) or key not in ready:
            reasons.append("ROOM_NOT_IN_PRODUCTION_GRANT")
        target, end = None, None
        if g:
            baseline, cmd = obj(g.get("baseline")), obj(g.get("command"))
            current = numeric(baseline.get("currentTarget_C"))
            future = numeric(baseline.get("futureTarget_C"))
            target = numeric(cmd.get("target_C"))
            end = timestamp(baseline.get("changeAt"))
            if baseline.get("direction") != "UP":
                reasons.append("NO_SCHEDULED_UP")
            if target is None or current is None or future is None or not(current < target <= future):
                reasons.append("TARGET_OUTSIDE_UP_BOUNDS")
            elif target > current + 0.5 + 0.00001:
                # The actual incremental bound must be enforced by the planner;
                # absent physical ownership proof, never infer a larger first step.
                reasons.append("INITIAL_STEP_EXCEEDS_0_5C")
            if end is None or end <= now:
                reasons.append("SCHEDULED_UP_EXPIRED")
        reasons = list(dict.fromkeys(reasons))
        candidate = len(reasons) == 0
        results.append({
            "key": key, "homeyDeviceId": device_id,
            "observedMode": vendor_mode,
            "simulatedAction": "WOULD_SET_TEMP" if candidate else "HOLD",
            "status": "CANDIDATE_ONLY" if candidate else "BLOCKED",
            "simulatedTarget_C": target if candidate else None,
            "simulatedExpiryAt": end.isoformat().replace("+00:00", "Z") if candidate else None,
            "denialReasons": reasons,
            "liveExecutionAllowed": False,
            "physicalWrite": False,
            "physicalOwnershipProven": False,
        })
    return {
        "schema": SCHEMA, "generatedAt": iso,
        "mode": "READ_ONLY", "controlMode": "DRY_RUN",
        "liveExecutionAllowed": False, "physicalWriteAllowed": False,
        "physicalWrites": 0, "deviceReads": 0, "networkCalls": 0,
        "rooms": results, "roomCount": len(results),
        "globalDenialReasons": list(dict.fromkeys(global_reasons)),
        "edgeProofMissing": ["SUSTAINED_P1_EXPORT_UNPROVEN", "HOMEY_EDGE_READ_UNPROVEN",
                             "TEMPORARY_OVERRIDE_ACK_UNPROVEN", "INDEPENDENT_HONEYWELL_READBACK_UNPROVEN",
                             "PHYSICAL_OWNERSHIP_UNPROVEN"],
        "source": "PI_LOCAL_JSON_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, default in DEFAULTS.items():
        parser.add_argument(f"--{key}", type=Path, default=default)
    args = parser.parse_args()
    docs = {}
    for key in DEFAULTS:
        try:
            docs[key] = json.loads(getattr(args, key).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            docs[key] = {}
            print(f"WARN: {key}: {type(error).__name__}", file=__import__("sys").stderr)
    print(json.dumps(evaluate(docs), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build read-only Pi shadow state for Tesla deadline ownership migration.

This component performs no Homey calls, no device writes and no control writes.
It combines the existing website command-transfer artifact with canonical
Homey->Pi telemetry. Until tesla.meter_kwh is deployed, it reports
WAITING_FOR_METER_TELEMETRY and never claims deadline authority.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

COMMAND_FILE = Path("/home/jeroen/ems/repo/homey-energy-manual/docs/data/tesla-deadline-command.json")
ENERGY_STATE_FILE = Path("/home/jeroen/ems/data/energy-state-v2.json")
STATE_FILE = Path("/home/jeroen/ems/data/ev-deadline-shadow-state.json")
TZ = ZoneInfo("Europe/Amsterdam")
EV_W_PER_A = 690
MIN_A = 6
MAX_A = 16


def load(path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {} if default is None else default


def parse_deadline_local(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def finite_number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def previous_for_request(previous, request_id):
    return previous if previous.get("requestId") == request_id else {}


def build(command, energy_state, previous, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    tesla = energy_state.get("tesla") or {}
    request_id = command.get("requestId")
    same = previous_for_request(previous, request_id)

    out = {
        "schema": "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.1",
        "generatedAt": now_utc.isoformat().replace("+00:00", "Z"),
        "mode": "PURE_SHADOW",
        "readOnly": True,
        "controlWrites": False,
        "authority": "HOMEY_CURRENT_PI_SHADOW",
        "requestId": request_id,
        "requestedAt": command.get("requestedAt"),
        "active": command.get("active") is True,
        "deadlineCommandLocal": command.get("deadline"),
        "deadlineAt": None,
        "currentSocCommandOnly": command.get("currentSoc"),
        "targetSocCommandOnly": command.get("targetSoc"),
        "calibrationKWhPerPercent": command.get("calibrationKWhPerPercent"),
        "goalKWh": finite_number(command.get("goalKWh")),
        "maxA": finite_number(command.get("maxA")),
        "meterKWh": finite_number(tesla.get("meter_kwh")),
        "baselineMeterKWh": same.get("baselineMeterKWh"),
        "baselineCapturedAt": same.get("baselineCapturedAt"),
        "deliveredKWh": same.get("deliveredKWh", 0.0),
        "remainingKWh": same.get("remainingKWh"),
        "latestStartAt": same.get("latestStartAt"),
        "status": "INIT",
        "diagnostics": [],
    }

    deadline = parse_deadline_local(command.get("deadline"))
    if deadline:
        out["deadlineAt"] = deadline.isoformat().replace("+00:00", "Z")
    else:
        out["status"] = "INVALID_DEADLINE"
        out["diagnostics"].append("DEADLINE_PARSE_FAILED")
        return out

    if not request_id:
        out["status"] = "INVALID_COMMAND"
        out["diagnostics"].append("REQUEST_ID_MISSING")
        return out
    if not out["active"]:
        out["status"] = "INACTIVE"
        return out
    if out["goalKWh"] is None or out["goalKWh"] < 0:
        out["status"] = "INVALID_COMMAND"
        out["diagnostics"].append("GOAL_KWH_INVALID")
        return out
    if out["maxA"] is None or out["maxA"] < MIN_A or out["maxA"] > MAX_A:
        out["status"] = "INVALID_COMMAND"
        out["diagnostics"].append("MAX_A_INVALID")
        return out
    if deadline <= now_utc:
        out["status"] = "EXPIRED"
        return out

    meter = out["meterKWh"]
    if meter is None:
        if out["baselineMeterKWh"] is None:
            out["status"] = "WAITING_FOR_METER_TELEMETRY"
        else:
            out["status"] = "METER_TELEMETRY_UNAVAILABLE"
            out["diagnostics"].append("RETAINING_PREVIOUS_PROGRESS_FAIL_CLOSED")
        return out

    baseline = finite_number(out["baselineMeterKWh"])
    if baseline is None:
        baseline = meter
        out["baselineMeterKWh"] = round(baseline, 6)
        out["baselineCapturedAt"] = out["generatedAt"]

    if meter + 1e-6 < baseline:
        out["status"] = "METER_RESET_SUSPECTED"
        out["diagnostics"].append("CURRENT_METER_BELOW_IMMUTABLE_BASELINE")
        return out

    delivered = max(0.0, meter - baseline)
    remaining = max(0.0, out["goalKWh"] - delivered)
    out["deliveredKWh"] = round(delivered, 6)
    out["remainingKWh"] = round(remaining, 6)

    max_kw = out["maxA"] * EV_W_PER_A / 1000
    hours_needed = remaining / max_kw if max_kw > 0 else None
    if hours_needed is None:
        out["status"] = "FAIL_CLOSED"
        return out

    latest = deadline.timestamp() - hours_needed * 3600
    out["latestStartAt"] = datetime.fromtimestamp(latest, timezone.utc).isoformat().replace("+00:00", "Z")
    out["status"] = "GOAL_COMPLETE" if remaining <= 1e-9 else "TRACKING"
    return out


def main():
    command = load(COMMAND_FILE, {})
    energy_state = load(ENERGY_STATE_FILE, {})
    previous = load(STATE_FILE, {})
    payload = build(command, energy_state, previous)

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    tmp.replace(STATE_FILE)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

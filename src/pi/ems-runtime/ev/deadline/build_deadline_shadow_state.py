#!/usr/bin/env python3
"""Build read-only Pi shadow state for Tesla deadline ownership migration.

Realtime deadline progress is derived from canonical Homey Core measured power.
The Easee cumulative meter is deliberately only a session checkpoint: observed
runtime behaviour shows that it can remain unchanged while charging and jump
only after the session stops. This component performs no Homey calls, device
writes or control writes.
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
MAX_INTEGRATION_GAP_S = 420
MIN_CHARGE_POWER_W = 100


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


def parse_utc(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
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
    meta = energy_state.get("meta") or {}
    request_id = command.get("requestId")
    same = previous_for_request(previous, request_id)

    meter = finite_number(tesla.get("meter_kwh"))
    power_w = finite_number(tesla.get("power_w"))
    telemetry_at = parse_utc(meta.get("generated_at"))
    charging = tesla.get("charging") is True

    out = {
        "schema": "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2",
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
        "charging": charging,
        "powerW": power_w,
        "telemetryAt": telemetry_at.isoformat().replace("+00:00", "Z") if telemetry_at else None,
        "lastTelemetryAt": same.get("lastTelemetryAt"),
        "lastPowerW": finite_number(same.get("lastPowerW")),
        "meterKWh": meter,
        "baselineMeterKWh": same.get("baselineMeterKWh"),
        "baselineCapturedAt": same.get("baselineCapturedAt"),
        "lastMeterCheckpointKWh": same.get("lastMeterCheckpointKWh"),
        "lastMeterCheckpointObservedAt": same.get("lastMeterCheckpointObservedAt"),
        "meterDeliveredKWh": same.get("meterDeliveredKWh"),
        "deliveredKWh": finite_number(same.get("deliveredKWh")) or 0.0,
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

    baseline = finite_number(out["baselineMeterKWh"])
    if baseline is None and meter is not None:
        baseline = meter
        out["baselineMeterKWh"] = round(baseline, 6)
        out["baselineCapturedAt"] = out["generatedAt"]
        out["lastMeterCheckpointKWh"] = round(meter, 6)
        out["lastMeterCheckpointObservedAt"] = out["telemetryAt"] or out["generatedAt"]

    # Realtime progress: integrate the PREVIOUS measured power over the bounded
    # interval to the current canonical telemetry timestamp. The 420 s bound matches\n    # the intentional 5-minute canonical Homey Core cadence with 2 minutes of\n    # transport/scheduling margin. This avoids using
    # the new sample retroactively and never integrates across long/stale gaps.
    delivered = finite_number(out["deliveredKWh"]) or 0.0
    previous_at = parse_utc(same.get("lastTelemetryAt"))
    previous_power = finite_number(same.get("lastPowerW"))
    if telemetry_at and previous_at:
        dt_s = (telemetry_at - previous_at).total_seconds()
        if dt_s < 0:
            out["diagnostics"].append("TELEMETRY_TIME_MOVED_BACKWARDS")
        elif dt_s == 0:
            pass
        elif dt_s > MAX_INTEGRATION_GAP_S:
            out["diagnostics"].append("TELEMETRY_GAP_NOT_INTEGRATED")
        elif same.get("charging") is True and previous_power is not None and previous_power >= MIN_CHARGE_POWER_W:
            delivered += previous_power * dt_s / 3_600_000.0
    elif same and telemetry_at and not previous_at:
        out["diagnostics"].append("PREVIOUS_TELEMETRY_TIMESTAMP_MISSING")

    out["deliveredKWh"] = round(max(0.0, delivered), 6)

    # Easee meter is checkpoint-only. An unchanged value has no effect. A new
    # value is recorded for validation, never used to pull realtime progress
    # backwards or added to the power integral (which would double count).
    if baseline is not None and meter is not None:
        if meter + 1e-6 < baseline:
            out["diagnostics"].append("METER_RESET_SUSPECTED_IGNORED_FOR_REALTIME_PROGRESS")
        else:
            meter_delivered = max(0.0, meter - baseline)
            out["meterDeliveredKWh"] = round(meter_delivered, 6)
            prior_checkpoint = finite_number(same.get("lastMeterCheckpointKWh"))
            if prior_checkpoint is None or abs(meter - prior_checkpoint) > 1e-6:
                out["lastMeterCheckpointKWh"] = round(meter, 6)
                out["lastMeterCheckpointObservedAt"] = out["telemetryAt"] or out["generatedAt"]
                if charging:
                    out["diagnostics"].append("METER_CHANGED_DURING_ACTIVE_CHARGE")
                else:
                    out["diagnostics"].append("SESSION_END_METER_CHECKPOINT_OBSERVED")

    # Persist the canonical sample for the next invocation.
    if telemetry_at:
        out["lastTelemetryAt"] = out["telemetryAt"]
        out["lastPowerW"] = power_w

    remaining = max(0.0, out["goalKWh"] - out["deliveredKWh"])
    out["remainingKWh"] = round(remaining, 6)

    max_kw = out["maxA"] * EV_W_PER_A / 1000
    hours_needed = remaining / max_kw if max_kw > 0 else None
    if hours_needed is None:
        out["status"] = "FAIL_CLOSED"
        return out

    latest = deadline.timestamp() - hours_needed * 3600
    out["latestStartAt"] = datetime.fromtimestamp(latest, timezone.utc).isoformat().replace("+00:00", "Z")

    if remaining <= 1e-9:
        out["status"] = "GOAL_COMPLETE"
    elif deadline <= now_utc:
        out["status"] = "EXPIRED"
    elif telemetry_at is None:
        out["status"] = "WAITING_FOR_CANONICAL_TELEMETRY"
    else:
        out["status"] = "TRACKING"
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

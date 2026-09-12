#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def intval(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _field(device, dict_key, attr_name=None, default=None):
    if isinstance(device, dict):
        return device.get(dict_key, default)
    return getattr(device, attr_name or dict_key, default)


def _status_list(device):
    if isinstance(device, dict):
        return device.get("statusList", {}) or {}
    return getattr(device, "status_list", {}) or {}


def build_state(device):
    s = _status_list(device)

    status = intval(s.get("Status"))
    pre_status = intval(s.get("Step_pre_bake_status"))
    current_step = intval(s.get("Current_baking_step"), 0)

    active = status == 2

    if not active:
        state = "IDLE"
    elif pre_status == 2:
        state = "PREHEATING"
    else:
        state = "RUNNING"

    measured = intval(s.get("Oven_measured_temperature"))
    setpoint = intval(
        s.get("Step_pre_bake_set_temperature")
        if state == "PREHEATING"
        else s.get("Step_1_set_temperature")
    )

    return {
        "schema": "EMS_OVEN_STATE_V0.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "CONNECTLIFE",
        "device": _field(device, "deviceFeatureCode", "device_feature_code"),
        "deviceName": _field(device, "deviceNickName", "device_nickname"),
        "online": _field(device, "offlineState", "offline_state") == 1,
        "active": active,
        "state": state,
        "setpoint_C": setpoint,
        "measured_C": measured,
        "currentStep": current_step,
        "elapsed_s": intval(s.get("Total_passed_time_seconds"), 0),
        "readOnly": True,
    }


def load_device(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <connectlife-json>", file=sys.stderr)
        return 2

    device = load_device(Path(sys.argv[1]))
    print(json.dumps(build_state(device), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

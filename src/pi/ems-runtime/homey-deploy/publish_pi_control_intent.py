#!/usr/bin/env python3

"""Publish the current hardened Pi planner slot to Homey EM2_Power_Intent.

The Pi remains the sole planner authority. Homey remains executor/safety only.
This process never writes devices directly; it updates the existing
EM2_POWER_INTENT_V0.2 compatibility bus so the validated Homey adapters/gates
and actuators can execute the Pi decision.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"
CONTROL_URL = "http://127.0.0.1:3100/control/current"
STATE_VAR_ID = "8e1efbb0-7999-494c-9429-7d274afacd79"
INTENT_VAR_ID = "04b57041-dd7f-41f7-a00a-f023afb1ccee"
TMP = Path("/home/jeroen/ems/data/pi-power-intent-update.json")


def homey(args):
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")
    r = subprocess.run(
        [str(HOMEY_CLI)] + args,
        cwd=HOMEY_PROJECT,
        env=env,
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:1200])
    return r.stdout


def read_homey_variable(var_id):
    return json.loads(homey(["api", "logic", "get-variable", "--id", var_id, "--json"]))


def publish_homey_value(var_id, value):
    TMP.parent.mkdir(parents=True, exist_ok=True)
    TMP.write_text(json.dumps({"value": value}, separators=(",", ":")) + "\n", encoding="utf-8")
    try:
        return homey(["api", "logic", "update-variable", "--id", var_id, "--body", f"@{TMP}", "--json"])
    finally:
        try:
            TMP.unlink()
        except FileNotFoundError:
            pass


def fetch_control():
    req = urllib.request.Request(CONTROL_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def parse_json(value):
    try:
        return json.loads(str(value or ""))
    except Exception:
        return None


def main():
    state_var = read_homey_variable(STATE_VAR_ID)
    state = parse_json(state_var.get("value")) or {}
    revision = state.get("revision")
    if revision is None:
        raise SystemExit("FAIL_CLOSED: Homey state revision missing")

    try:
        cmd = fetch_control()
    except Exception as exc:
        raise SystemExit(f"FAIL_CLOSED: Pi control endpoint unavailable: {exc}")

    contract = cmd.get("contract") or {}
    targets = cmd.get("targets") or {}
    valid = (
        cmd.get("schema") == "EMS_PI_CONTROL_COMMAND_V0.1"
        and cmd.get("plannerOwner") == "PI"
        and cmd.get("executor") == "HOMEY"
        and contract.get("mode") == "FIXED"
        and contract.get("id") == "ENGIE_3Y_2026_2029"
    )
    if not valid:
        raise SystemExit("FAIL_CLOSED: Pi control contract invalid")

    ev = targets.get("ev") or {}
    ww = targets.get("ww") or {}
    ev_w = max(0, int(round(float(ev.get("target_W") or 0))))
    ww_on = ww.get("target_on")
    if not isinstance(ww_on, bool):
        raise SystemExit("FAIL_CLOSED: WW target_on invalid")

    out = {
        "schema": "EM2_POWER_INTENT_V0.2",
        "policyRevision": "PI_DYNAMIC_PLANNER_PUSH_V1.0",
        "engineVersion": "PI_DYNAMIC_PLANNER_V0.3_LIVE_PUSH",
        "generatedAt": cmd.get("generatedAt"),
        "sourceRevision": revision,
        "readOnly": True,
        "controlMode": "SHADOW",
        "deviceWrites": False,
        "valid": True,
        "status": "OK",
        "inputSemanticKey": json.dumps({
            "stateRevision": revision,
            "plannerGeneratedAt": cmd.get("plannerGeneratedAt"),
            "commandValidUntil": cmd.get("validUntil"),
            "evW": ev_w,
            "wwOn": ww_on,
        }, separators=(",", ":"), sort_keys=True),
        "inputRevisions": {
            "state": revision,
            "planner": cmd.get("plannerGeneratedAt"),
        },
        "policyProjection": {
            "plannerOwner": "PI",
            "executor": "HOMEY",
            "contractMode": "FIXED",
            "contractId": "ENGIE_3Y_2026_2029",
            "commandValidUntil": cmd.get("validUntil"),
            "slot": cmd.get("slot"),
        },
        "targets": {
            "ev": {
                "target_W": ev_w,
                "status": "PI_NUMERIC_TARGET" if ev_w > 0 else "IDLE",
                "source": "PI_DYNAMIC_PLANNER_V0.3",
            },
            "ww": {
                "target_W": None,
                "target_on": ww_on,
                "status": "PI_BINARY_TARGET",
                "sourceAction": "BOILER_ON" if ww_on else "BOILER_OFF",
            },
            "battery": {"target_W": 0, "status": "NOT_INTEGRATED"},
        },
        "safety": {
            "logicOnly": True,
            "noDeviceWrites": True,
            "plannerOwner": "PI",
            "homeyRole": "EXECUTOR_SAFETY",
            "fixedContractEnforced": True,
            "failClosed": True,
            "staleCommandRejectedByPiEndpoint": True,
            "legacyHomeyPlannerAuthority": False,
        },
    }

    current = read_homey_variable(INTENT_VAR_ID)
    value = json.dumps(out, separators=(",", ":"))
    if current.get("value") == value:
        print("PASS: Pi control intent unchanged")
        return 0

    publish_homey_value(INTENT_VAR_ID, value)
    print("PASS: Pi control intent published to Homey")
    print("revision:", revision)
    print("evTargetW:", ev_w)
    print("wwTargetOn:", ww_on)
    print("validUntil:", cmd.get("validUntil"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

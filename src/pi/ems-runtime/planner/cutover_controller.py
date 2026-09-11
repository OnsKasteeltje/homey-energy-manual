#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path("/home/jeroen/ems/runtime/planner")
AUTHORITY = RUNTIME / "control-authority.json"
SELECTOR = RUNTIME / "authority-selector-policy.json"
COMMAND = RUNTIME / "authority-command.json"
PREFLIGHT = RUNTIME / "validate_authority_preflight.py"

ALLOWED = {"HOMEY", "PI"}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path):
    return json.loads(Path(path).read_text())


def atomic_write(path, obj):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n")
    tmp.replace(path)


def run_preflight():
    p = subprocess.run([sys.executable, str(PREFLIGHT)], text=True, capture_output=True)
    output = (p.stdout or "") + (p.stderr or "")
    return p.returncode == 0 and "CUTOVER_PREP: PASS" in output, output.strip()


def default_command():
    return {
        "schema": "EMS_AUTHORITY_COMMAND_V0.1",
        "requestedAuthority": "HOMEY",
        "state": "DISARMED",
        "armed": False,
        "requestedAt": None,
        "requestedBy": None,
        "preflightPassedAt": None,
        "executeAllowed": False,
        "consumed": False,
        "notes": [
            "This file is a staging command only.",
            "No Homey flow, device, or canonical Power Intent is changed by this script.",
            "PI authority requires a fresh PASS preflight at arm time and an explicit later execution step."
        ]
    }


def status():
    a = load(AUTHORITY)
    s = load(SELECTOR)
    c = load(COMMAND) if COMMAND.exists() else default_command()
    print("AUTHORITY")
    print(" plannerOwner:", a.get("plannerOwner"))
    print(" cutoverState:", a.get("cutoverState"))
    print(" piBridgeEnabled:", a.get("piBridgeEnabled"))
    print(" manualCutoverAuthorized:", a.get("manualCutoverAuthorized"))
    print("SELECTOR")
    print(" currentAuthority:", s.get("currentAuthority"))
    print(" selectorMode:", s.get("selectorMode"))
    print("COMMAND")
    print(" state:", c.get("state"))
    print(" requestedAuthority:", c.get("requestedAuthority"))
    print(" armed:", c.get("armed"))
    print(" executeAllowed:", c.get("executeAllowed"))
    print(" consumed:", c.get("consumed"))
    return 0


def disarm(requested_by):
    c = default_command()
    c["requestedAt"] = utc_now()
    c["requestedBy"] = requested_by
    atomic_write(COMMAND, c)
    print("DISARMED: command reset to HOMEY-safe staging state.")
    print("No Homey or device write performed.")
    return 0


def arm(target, requested_by):
    if target not in ALLOWED:
        raise SystemExit(f"invalid target {target}")
    if target == "HOMEY":
        c = default_command()
        c.update({
            "requestedAuthority": "HOMEY",
            "state": "ARMED_ROLLBACK_HOMEY",
            "armed": True,
            "requestedAt": utc_now(),
            "requestedBy": requested_by,
            "executeAllowed": False,
        })
        atomic_write(COMMAND, c)
        print("ARMED_ROLLBACK_HOMEY")
        print("Staging only; no Homey or device write performed.")
        return 0

    ok, output = run_preflight()
    print(output)
    if not ok:
        print("REFUSED: PI arm requires CUTOVER_PREP: PASS.")
        return 2
    a = load(AUTHORITY)
    s = load(SELECTOR)
    safe_baseline = (
        a.get("plannerOwner") == "HOMEY"
        and a.get("manualCutoverAuthorized") is False
        and a.get("piBridgeEnabled") is False
        and s.get("currentAuthority") == "HOMEY"
    )
    if not safe_baseline:
        print("REFUSED: authority baseline is not HOMEY-safe.")
        return 3
    now = utc_now()
    c = default_command()
    c.update({
        "requestedAuthority": "PI",
        "state": "ARMED_PI_CANARY",
        "armed": True,
        "requestedAt": now,
        "requestedBy": requested_by,
        "preflightPassedAt": now,
        "executeAllowed": False,
    })
    atomic_write(COMMAND, c)
    print("ARMED_PI_CANARY")
    print("Staging only; executeAllowed remains false.")
    print("No Homey flow, device, or canonical Power Intent was changed.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Safe staging layer for EMS planner authority cutover.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_arm = sub.add_parser("arm")
    p_arm.add_argument("target", choices=["HOMEY", "PI"])
    p_arm.add_argument("--requested-by", default="manual")
    p_disarm = sub.add_parser("disarm")
    p_disarm.add_argument("--requested-by", default="manual")
    args = ap.parse_args()
    if args.cmd == "status":
        return status()
    if args.cmd == "arm":
        return arm(args.target, args.requested_by)
    if args.cmd == "disarm":
        return disarm(args.requested_by)
    return 1


if __name__ == "__main__":
    sys.exit(main())

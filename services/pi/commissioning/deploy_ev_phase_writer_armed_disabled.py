#!/usr/bin/env python3
"""
Deploy EV phase writer v0.4.0 in ARMED-DISABLED mode to the existing actuator flow.

This script MUST NOT enable physical phase execution.
It verifies PHASE_EXECUTION_ENABLED=false in source before updating Homey,
triggers one candidate run, and verifies the published actuator status remains
phaseExecutionEnabled=false and physicalWritePerformed=false.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOMEY = "/home/jeroen/ems-homey-adapter/node_modules/.bin/homey"
FLOW_ID = "fea23193-a03f-49dd-9780-7e72ee48747d"
SCRIPT_CARD = "10a00000-0000-4000-8000-000000000002"
STATUS_ID = "ea1f8a44-2f6c-490e-9b86-bae761886cf9"
CHARGER_ID = "4d0b6913-d940-474e-95d6-b43f194c4119"
SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.0.phase-writer.js"
FLOW_NAME = "EM v2 | 60 Actuator | EV Power v0.4.0 PHASE-WRITER [ARMED-DISABLED]"


def run(*args):
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    delays = (0, 3, 6, 12)
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        cp = subprocess.run(
            [HOMEY, *args],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        if cp.returncode == 0:
            return cp.stdout
        msg = (cp.stderr or cp.stdout or "").strip()
        if "too many requests" not in msg.lower() or attempt == len(delays) - 1:
            raise RuntimeError(f"HOMEY_CLI_FAILED:{' '.join(args)}:{msg[:500]}")
    raise RuntimeError("HOMEY_CLI_FAILED")


def jrun(*args):
    raw = run(*args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"HOMEY_JSON_INVALID:{' '.join(args)}:"
            f"line={exc.lineno}:col={exc.colno}:chars={len(raw)}"
        ) from exc


def body_file(payload):
    fd, path = tempfile.mkstemp(prefix="ems-homey-writer-", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
        return path
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def unwrap_flow(raw):
    if isinstance(raw, dict) and isinstance(raw.get("advancedFlow"), dict):
        return raw["advancedFlow"]
    return raw


def cap(device, name):
    obj = (device.get("capabilitiesObj") or {}).get(name)
    return obj.get("value") if isinstance(obj, dict) else None


def main():
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "const PHASE_EXECUTION_ENABLED=false",
        "const canWrite=PHASE_EXECUTION_ENABLED&&liveEnabled",
        "physicalWritePerformed",
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"ARMED_DISABLED_MARKER_MISSING:{marker}")

    print("=== DEPLOY ARMED-DISABLED WRITER ===")
    raw = jrun("api", "flow", "get-advanced-flow", "--id", FLOW_ID, "--json")
    flow = unwrap_flow(raw)
    cards = flow.get("cards") if isinstance(flow, dict) else None
    if not isinstance(cards, dict):
        raise RuntimeError("ACTUATOR_FLOW_CARDS_INVALID")
    card = cards.get(SCRIPT_CARD)
    if not isinstance(card, dict) or card.get("type") != "action":
        raise RuntimeError("ACTUATOR_SCRIPT_CARD_INVALID")

    # Keep the minimal candidate topology: start + gate trigger + script + note.
    card.setdefault("args", {})["code"] = source
    note = cards.get("10a00000-0000-4000-8000-000000000003")
    if isinstance(note, dict) and note.get("type") == "note":
        note["value"] = (
            "v0.4.0 PHASE-WRITER ARMED-DISABLED: physical writer code present, "
            "but PHASE_EXECUTION_ENABLED=false. No physical execution."
        )

    body = {"name": FLOW_NAME, "enabled": True, "cards": cards}
    path = body_file(body)
    try:
        run(
            "api", "flow", "update-advanced-flow",
            "--id", FLOW_ID,
            "--body", f"@{path}",
        )
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    print(f"PASS: {FLOW_NAME}")

    print()
    print("=== TRIGGER ONE ARMED-DISABLED RUN ===")
    run("api", "flow", "trigger-advanced-flow", "--id", FLOW_ID)
    time.sleep(3)

    status_var = jrun("api", "logic", "get-variable", "--id", STATUS_ID, "--json")
    status_raw = status_var.get("value") if isinstance(status_var, dict) else None
    status = json.loads(status_raw) if isinstance(status_raw, str) else {}

    public_status = {
        "schema": status.get("schema"),
        "status": status.get("status"),
        "reason": status.get("reason"),
        "targetA": status.get("targetA"),
        "phaseMode": status.get("phaseMode"),
        "candidateAction": status.get("candidateAction"),
        "confirmedMode": status.get("confirmedMode"),
        "phaseExecutionEnabled": status.get("phaseExecutionEnabled"),
        "physicalWritePerformed": status.get("physicalWritePerformed"),
    }
    print(json.dumps(public_status, indent=2))

    if status.get("schema") != "EM2_EV_ACTUATOR_V0.4.0_PHASE_WRITER":
        raise RuntimeError("WRITER_SCHEMA_NOT_ACTIVE")
    if status.get("phaseExecutionEnabled") is not False:
        raise RuntimeError("PHASE_EXECUTION_NOT_DISABLED")
    if status.get("physicalWritePerformed") is not False:
        raise RuntimeError("UNEXPECTED_PHYSICAL_WRITE")

    print()
    print("=== EASEE READBACK ===")
    charger = jrun("api", "devices", "get-device", "--id", CHARGER_ID, "--json")
    physical = {
        "chargeState": cap(charger, "evcharger_charging_state"),
        "charging": cap(charger, "evcharger_charging"),
        "targetA": cap(charger, "target_charger_current"),
        "offeredA": cap(charger, "measure_current.offered"),
        "powerW": cap(charger, "measure_power"),
        "circuitTargetA": cap(charger, "target_circuit_current"),
    }
    print(json.dumps(physical, indent=2))

    print()
    print("PASS: writer v0.4.0 deployed ARMED-DISABLED; no physical execution enabled")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

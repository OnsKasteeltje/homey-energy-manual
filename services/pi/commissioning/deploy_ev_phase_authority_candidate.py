#!/usr/bin/env python3
"""
Deploy the phase-authority control-chain candidate to the existing Homey flow IDs.

Safety:
- Bridge/Adapter/Gate remain logic-only.
- Actuator v0.3.1 is hard no-write (PHASE_EXECUTION_ENABLED=false).
- No Easee device action cards are added.
- Existing flow IDs are reused; no second writer is created.

Run from the repository root on the EMS Pi.
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

FLOWS = {
    "bridge": {
        "id": "8bf53fdb-76f4-47db-8ccb-773ac515f06e",
        "name": "EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.0 PHASE-AUTHORITY [READY]",
        "card": "44444444-eeee-4444-8444-444444444444",
        "source": ROOT / "src/homey/power-intent/pi-dynamic-planner-bridge-v1.5.0.phase-authority.js",
    },
    "adapter": {
        "id": "953e9b18-3576-4557-b940-ed4a64eb2516",
        "name": "EM v2 | 60 Adapter | EV Power v0.2.0 PHASE-AWARE",
        "card": "33333333-aaaa-4333-8333-333333333333",
        "source": ROOT / "src/homey/adapters/ev-power/ev-power-v0.2.0.phase-aware.js",
    },
    "gate": {
        "id": "ec5e5d34-8205-4cf0-a661-7bf744feb6e0",
        "name": "EM v2 | 80 Validation | EV Gate v0.3.0 PHASE-AWARE",
        "card": "a0e10000-0000-4000-8000-000000000004",
        "source": ROOT / "src/homey/validation/ev-power-adapter-gate-v0.3.0.phase-aware.js",
    },
    "actuator": {
        "id": "fea23193-a03f-49dd-9780-7e72ee48747d",
        "name": "EM v2 | 60 Actuator | EV Power v0.3.1 PHASE-AUTHORITY-CANDIDATE [NO-WRITE]",
        "card": "10a00000-0000-4000-8000-000000000002",
        "source": ROOT / "src/homey/actuators/ev-power/ev-power-v0.3.1.phase-authority-candidate.js",
    },
}

ACTUATOR_STATUS_ID = "ea1f8a44-2f6c-490e-9b86-bae761886cf9"
CHARGER_ID = "4d0b6913-d940-474e-95d6-b43f194c4119"


def run(*args, capture=True):
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    cp = subprocess.run(
        [HOMEY, *args],
        text=True,
        capture_output=capture,
        env=env,
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError(
            f"HOMEY_CLI_FAILED:{' '.join(args)}:"
            f"{(cp.stderr or cp.stdout or '').strip()[:500]}"
        )
    return cp.stdout if capture else ""


def jrun(*args):
    raw = run(*args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"HOMEY_JSON_INVALID:{' '.join(args)}:"
            f"line={exc.lineno}:col={exc.colno}:chars={len(raw)}"
        ) from exc


def unwrap_flow(raw):
    if isinstance(raw, dict) and isinstance(raw.get("advancedFlow"), dict):
        return raw["advancedFlow"]
    return raw


def body_file(payload):
    fd, path = tempfile.mkstemp(prefix="ems-homey-flow-", suffix=".json")
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


def update_flow(spec):
    raw = jrun("api", "flow", "get-advanced-flow", "--id", spec["id"], "--json")
    flow = unwrap_flow(raw)
    if not isinstance(flow, dict):
        raise RuntimeError(f"FLOW_INVALID:{spec['id']}")

    cards = flow.get("cards")
    if not isinstance(cards, dict):
        raise RuntimeError(f"FLOW_CARDS_INVALID:{spec['id']}")

    card = cards.get(spec["card"])
    if not isinstance(card, dict) or card.get("type") != "action":
        raise RuntimeError(f"SCRIPT_CARD_INVALID:{spec['id']}:{spec['card']}")

    source = spec["source"].read_text(encoding="utf-8")
    if spec["id"] == FLOWS["actuator"]["id"]:
        required = (
            "const PHASE_EXECUTION_ENABLED=false",
            "physicalWritePerformed:false",
        )
        for marker in required:
            if marker not in source:
                raise RuntimeError(f"ACTUATOR_NO_WRITE_MARKER_MISSING:{marker}")

    card.setdefault("args", {})["code"] = source

    body = {
        "name": spec["name"],
        "enabled": True,
        "cards": cards,
    }

    path = body_file(body)
    try:
        run(
            "api", "flow", "update-advanced-flow",
            "--id", spec["id"],
            "--body", f"@{path}",
        )
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    return spec["name"]


def parse_capabilities(device):
    caps = device.get("capabilitiesObj") or {}
    def value(name):
        obj = caps.get(name)
        return obj.get("value") if isinstance(obj, dict) else None
    return {
        "chargeState": value("evcharger_charging_state"),
        "charging": value("evcharger_charging"),
        "targetA": value("target_charger_current"),
        "offeredA": value("measure_current.offered"),
        "powerW": value("measure_power"),
        "circuitTargetA": value("target_circuit_current"),
    }


def main():
    print("=== PHASE AUTHORITY CANDIDATE DEPLOY ===")
    for key in ("bridge", "adapter", "gate", "actuator"):
        name = update_flow(FLOWS[key])
        print(f"PASS: {key}: {name}")

    print()
    print("=== TRIGGER BRIDGE ===")
    run(
        "api", "flow", "trigger-advanced-flow",
        "--id", FLOWS["bridge"]["id"],
    )
    time.sleep(5)

    print()
    print("=== ACTUATOR STATUS ===")
    status_var = jrun(
        "api", "logic", "get-variable",
        "--id", ACTUATOR_STATUS_ID,
        "--json",
    )
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
        "controlRevisionPresent": bool(status.get("controlRevision")),
    }
    print(json.dumps(public_status, indent=2))

    print()
    print("=== EASEE PHYSICAL STATE ===")
    charger = jrun(
        "api", "devices", "get-device",
        "--id", CHARGER_ID,
        "--json",
    )
    print(json.dumps(parse_capabilities(charger), indent=2))

    print()
    if status.get("phaseExecutionEnabled") is not False:
        raise RuntimeError("PHASE_EXECUTION_NOT_HARD_DISABLED")
    if status.get("physicalWritePerformed") is not False:
        raise RuntimeError("UNEXPECTED_PHYSICAL_WRITE_FLAG")
    print("PASS: phase-authority chain deployed with hard no-write actuator")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

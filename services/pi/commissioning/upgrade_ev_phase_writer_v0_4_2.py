#!/usr/bin/env python3
"""
Guarded in-place upgrade of the sole LIVE EV phase writer from v0.4.1 to v0.4.2.

The upgrade is source-only: no second writer is created. It requires the
current actuator status to be STABLE before replacing the HomeyScript body.
After deployment it triggers one normal writer evaluation and verifies that
v0.4.2 is active and has not failed. Any deployment/validation exception
restores the exact previous Advanced Flow body.
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
NOTE_CARD = "10a00000-0000-4000-8000-000000000003"
STATUS_ID = "ea1f8a44-2f6c-490e-9b86-bae761886cf9"

SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.2.phase-writer-live.js"
FLOW_NAME = "EM v2 | 60 Actuator | EV Power v0.4.2 PHASE-WRITER [LIVE]"
EXPECTED_SCHEMA = "EM2_EV_ACTUATOR_V0.4.2_PHASE_WRITER"
ALLOWED_PREVIOUS_SCHEMAS = {
    "EM2_EV_ACTUATOR_V0.4.1_PHASE_WRITER",
    EXPECTED_SCHEMA,
}


def run(*args):
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    delays = (0, 2, 4, 8)
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


def unwrap_flow(raw):
    if isinstance(raw, dict) and isinstance(raw.get("advancedFlow"), dict):
        return raw["advancedFlow"]
    return raw


def writable_flow(flow):
    return {
        "name": flow["name"],
        "enabled": flow["enabled"],
        "cards": flow["cards"],
    }


def body_file(payload):
    fd, path = tempfile.mkstemp(prefix="ems-homey-ev-v042-", suffix=".json")
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


def push(body):
    path = body_file(body)
    try:
        run("api", "flow", "update-advanced-flow", "--id", FLOW_ID, "--body", f"@{path}")
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def status():
    v = jrun("api", "logic", "get-variable", "--id", STATUS_ID, "--json")
    raw = v.get("value") if isinstance(v, dict) else None
    return json.loads(raw) if isinstance(raw, str) else {}


def main():
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "EM2_EV_ACTUATOR_V0.4.2_PHASE_WRITER",
        "const PHASE_EXECUTION_ENABLED=true",
        "PHASE_OBSERVATION_ID=38",
        "EASEE_CLOUD_OBSERVATION_38",
        "ELECTRICAL_TELEMETRY",
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"SOURCE_MARKER_MISSING:{marker}")

    before_status = status()
    print("=== PRE-UPGRADE STATUS ===")
    print(json.dumps({
        "schema": before_status.get("schema"),
        "status": before_status.get("status"),
        "reason": before_status.get("reason"),
        "phaseMode": before_status.get("phaseMode"),
        "confirmedMode": before_status.get("confirmedMode"),
        "transitionStage": (before_status.get("transition") or {}).get("stage"),
    }, indent=2))

    if before_status.get("schema") not in ALLOWED_PREVIOUS_SCHEMAS:
        raise RuntimeError("UNEXPECTED_CURRENT_WRITER_SCHEMA")
    if before_status.get("status") != "STABLE":
        raise RuntimeError("CURRENT_WRITER_NOT_STABLE")
    if (before_status.get("transition") or {}).get("stage") != "STABLE":
        raise RuntimeError("CURRENT_TRANSITION_NOT_STABLE")
    if before_status.get("live") is not True:
        raise RuntimeError("CURRENT_WRITER_NOT_LIVE")

    raw = jrun("api", "flow", "get-advanced-flow", "--id", FLOW_ID, "--json")
    flow = unwrap_flow(raw)
    if not isinstance(flow, dict):
        raise RuntimeError("FLOW_INVALID")
    backup = writable_flow(flow)

    cards = json.loads(json.dumps(flow.get("cards") or {}))
    card = cards.get(SCRIPT_CARD)
    if not isinstance(card, dict) or card.get("type") != "action":
        raise RuntimeError("ACTUATOR_SCRIPT_CARD_INVALID")
    card.setdefault("args", {})["code"] = source

    note = cards.get(NOTE_CARD)
    if isinstance(note, dict) and note.get("type") == "note":
        note["value"] = (
            "v0.4.2 LIVE: electrical phase proof prevents stale same-phase pauses; "
            "Easee observation 38 confirms true phase transitions."
        )

    candidate = {"name": FLOW_NAME, "enabled": True, "cards": cards}

    try:
        print()
        print("=== DEPLOY V0.4.2 ===")
        push(candidate)
        run("api", "flow", "trigger-advanced-flow", "--id", FLOW_ID)
        time.sleep(4)

        after = status()
        print(json.dumps({
            "schema": after.get("schema"),
            "status": after.get("status"),
            "reason": after.get("reason"),
            "phaseMode": after.get("phaseMode"),
            "confirmedMode": after.get("confirmedMode"),
            "phaseConfirmationSource": (after.get("observed") or {}).get("phaseConfirmationSource"),
            "transitionStage": (after.get("transition") or {}).get("stage"),
            "transitionSlow": after.get("transitionSlow"),
        }, indent=2))

        if after.get("schema") != EXPECTED_SCHEMA:
            raise RuntimeError("V042_SCHEMA_NOT_ACTIVE")
        if after.get("live") is not True:
            raise RuntimeError("V042_NOT_LIVE")
        if after.get("phaseExecutionEnabled") is not True:
            raise RuntimeError("V042_EXECUTION_NOT_ENABLED")
        if after.get("status") == "FAILED":
            raise RuntimeError("V042_FAILED:" + str(after.get("reason")))

        print()
        print("PASS: v0.4.2 active; sole EV writer preserved")
    except Exception:
        print("ROLLBACK: restoring exact previous EV Advanced Flow", file=sys.stderr)
        push(backup)
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

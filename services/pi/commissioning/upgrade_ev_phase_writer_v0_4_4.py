#!/usr/bin/env python3
"""
Guarded in-place upgrade of the sole LIVE EV phase writer from v0.4.3 to v0.4.4.

v0.4.4 replaces inter-invocation self-retrigger transitions with one bounded
HomeyScript transaction. Deployment safety is deliberately minimal: never
replace the sole writer while a bounded transition is RUNNING, and never replace
it while an EV transition circuit cap (6..16 A) may still be active.

Runtime phase, charging, PV and pause state are not deployment prerequisites.
On a true deployment/source-validation failure the exact previous Advanced Flow
body is restored. Runtime actuator failures after the new source starts remain
runtime failures and do not roll back a successfully installed source.
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
CHARGER_ID = "4d0b6913-d940-474e-95d6-b43f194c4119"

EV_MAX_TRANSITION_CAP_A = 16

SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.4.phase-writer-live.js"
FLOW_NAME = "EM v2 | 60 Actuator | EV Power v0.4.4 BOUNDED-PHASE-WRITER [LIVE]"
EXPECTED_SCHEMA = "EM2_EV_ACTUATOR_V0.4.4_PHASE_WRITER"
ALLOWED_PREVIOUS_SCHEMAS = {
    "EM2_EV_ACTUATOR_V0.4.3_PHASE_WRITER",
    EXPECTED_SCHEMA,
}


def run(*args, retry_throttle=True):
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    delays = (0, 2, 4, 8) if retry_throttle else (0,)
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
    fd, path = tempfile.mkstemp(prefix="ems-homey-ev-v044-", suffix=".json")
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


def current_writable_flow():
    raw = jrun("api", "flow", "get-advanced-flow", "--id", FLOW_ID, "--json")
    flow = unwrap_flow(raw)
    if not isinstance(flow, dict):
        raise RuntimeError("FLOW_INVALID")
    return writable_flow(flow)


def push(body):
    path = body_file(body)
    try:
        try:
            # Writes are not blindly retried: Homey can apply a write and still
            # return a throttle response. Repeating it only increases pressure.
            run(
                "api", "flow", "update-advanced-flow",
                "--id", FLOW_ID, "--body", f"@{path}",
                retry_throttle=False,
            )
        except RuntimeError as exc:
            if "too many requests" not in str(exc).lower():
                raise
            # HOMEY_WRITE_429_READBACK: resolve ambiguous 429 by reading the
            # canonical flow back once. Exact match means the write did apply.
            if current_writable_flow() == body:
                print("NOTE: Homey returned 429 after write; exact readback confirms write applied")
                return
            raise
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def status():
    v = jrun("api", "logic", "get-variable", "--id", STATUS_ID, "--json")
    raw = v.get("value") if isinstance(v, dict) else None
    return json.loads(raw) if isinstance(raw, str) else {}


def cap(device, name):
    obj = (device.get("capabilitiesObj") or {}).get(name)
    return obj.get("value") if isinstance(obj, dict) else None


def charger_state():
    d = jrun("api", "devices", "get-device", "--id", CHARGER_ID, "--json")
    return {
        "chargeState": cap(d, "evcharger_charging_state"),
        "charging": cap(d, "evcharger_charging"),
        "offeredA": cap(d, "measure_current.offered"),
        "powerW": cap(d, "measure_power"),
        "circuitTargetA": cap(d, "target_circuit_current"),
        "chargerTargetA": cap(d, "target_charger_current"),
    }


def deploy_guard(st, charger):
    transition = st.get("transition") or {}
    circuit_target = charger.get("circuitTargetA")
    return {
        "schema": st.get("schema") in ALLOWED_PREVIOUS_SCHEMAS,
        "noActiveTransition":
            st.get("status") != "RUNNING"
            and transition.get("stage") != "RUNNING",
        # A temporary EV transition cap is always within the executable EV
        # range 6..16 A. A value above 16 A therefore proves that no temporary
        # transition cap is active without hard-coding the household baseline.
        "normalCircuitBaseline":
            isinstance(circuit_target, (int, float))
            and circuit_target > EV_MAX_TRANSITION_CAP_A,
    }

def all_true(checks):
    return all(checks.values())


def main():
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "EM2_EV_ACTUATOR_V0.4.4_PHASE_WRITER",
        "const PHASE_EXECUTION_ENABLED=true",
        "BOUNDED_TRANSITION_START",
        "BOUNDED_TRANSITION_COMPLETE",
        "selfRetriggerUsed:false",
        "const sleep=ms=>wait(ms);",
        "FINAL_PAUSE_READ_AFTER_TIMEOUT",
        "triggerAdvancedFlow",
    )
    for marker in required[:-1]:
        if marker not in source:
            raise RuntimeError(f"SOURCE_MARKER_MISSING:{marker}")
    if required[-1] in source:
        raise RuntimeError("SOURCE_SELF_RETRIGGER_STILL_PRESENT")
    if "setTimeout(" in source:
        raise RuntimeError("SOURCE_UNSUPPORTED_HOMEYSCRIPT_TIMER")

    before_status = status()
    before_charger = charger_state()
    guards = deploy_guard(before_status, before_charger)

    print("=== PRE-UPGRADE STATUS ===")
    print(json.dumps({
        "schema": before_status.get("schema"),
        "status": before_status.get("status"),
        "reason": before_status.get("reason"),
        "phaseMode": before_status.get("phaseMode"),
        "confirmedMode": before_status.get("confirmedMode"),
        "targetA": before_status.get("targetA"),
        "transition": before_status.get("transition"),
        "charger": before_charger,
        "guards": guards,
    }, indent=2))

    if not all_true(guards):
        raise RuntimeError("PRE_UPGRADE_UNSAFE_ACTIVE_TRANSITION_OR_CIRCUIT_CAP")

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
            "v0.4.4 LIVE: one bounded physical phase transaction per invocation; "
            "no inter-stage self-retrigger. Failure pauses and restores circuit baseline."
        )

    candidate = {"name": FLOW_NAME, "enabled": True, "cards": cards}

    # Recheck only the two deployment safety invariants immediately before
    # replacing the sole writer. Normal realtime current/phase/charge changes do
    # not block source deployment.
    final_status = status()
    final_charger = charger_state()
    final_guards = deploy_guard(final_status, final_charger)
    if not all_true(final_guards):
        print("finalGuards:", json.dumps(final_guards, indent=2))
        raise RuntimeError("PRE_UPGRADE_UNSAFE_BEFORE_PUSH")

    try:
        print()
        print("=== DEPLOY V0.4.4 ===")
        push(candidate)

        # Verify the sole Advanced Flow now contains the exact repository source
        # before executing it.
        deployed_raw = jrun("api", "flow", "get-advanced-flow", "--id", FLOW_ID, "--json")
        deployed_flow = unwrap_flow(deployed_raw)
        deployed_card = ((deployed_flow.get("cards") or {}).get(SCRIPT_CARD) or {})
        deployed_source = (deployed_card.get("args") or {}).get("code")
        if deployed_source != source:
            raise RuntimeError("DEPLOYED_SOURCE_MISMATCH")

        before_trigger_at = before_status.get("at")
        try:
            run(
                "api", "flow", "trigger-advanced-flow",
                "--id", FLOW_ID,
                retry_throttle=False,
            )
        except RuntimeError as exc:
            # A trigger 429 is also ambiguous. Do not issue duplicate triggers;
            # status readback below decides whether this invocation ran.
            if "too many requests" not in str(exc).lower():
                raise
            print("NOTE: Homey returned 429 for validation trigger; checking status readback")
        time.sleep(5)

        after = status()
        after_charger = charger_state()
        print(json.dumps({
            "schema": after.get("schema"),
            "status": after.get("status"),
            "reason": after.get("reason"),
            "phaseMode": after.get("phaseMode"),
            "confirmedMode": after.get("confirmedMode"),
            "targetA": after.get("targetA"),
            "boundedTransition": after.get("boundedTransition"),
            "transition": after.get("transition"),
            "charger": after_charger,
        }, indent=2))

        if after.get("schema") != EXPECTED_SCHEMA:
            raise RuntimeError("V044_SCHEMA_NOT_ACTIVE")
        if after.get("live") is not True:
            raise RuntimeError("V044_NOT_LIVE")
        if after.get("phaseExecutionEnabled") is not True:
            raise RuntimeError("V044_EXECUTION_NOT_ENABLED")
        if after.get("boundedTransition") is not True:
            raise RuntimeError("V044_BOUNDED_FLAG_MISSING")
        if after.get("at") == before_trigger_at:
            raise RuntimeError("V044_VALIDATION_TRIGGER_DID_NOT_UPDATE_STATUS")

        print()
        print("PASS: v0.4.4 source installed and validation trigger executed")
        if after.get("status") == "FAILED":
            print(
                "NOTE: writer reported runtime FAILED after deployment; "
                "source remains installed because this is not a deployment failure: "
                + str(after.get("reason"))
            )
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

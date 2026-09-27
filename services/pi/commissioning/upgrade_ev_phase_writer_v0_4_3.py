#!/usr/bin/env python3
"""
Guarded in-place upgrade of the sole LIVE EV phase writer from v0.4.2 to v0.4.3.

The upgrade is source-only: no second writer is created. It supports either a
normal STABLE/quiescent writer or the specifically diagnosed orphaned temporary
circuit-cap incident from 2026-09-27.

For the orphaned-cap case this script deliberately does NOT guess or restore a
circuit baseline. It deploys v0.4.3 only while the session is safely paused and
zero-load, then verifies that v0.4.3 remains fail-closed with
CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE. The operator must restore the proven
pre-transition baseline separately; v0.4.3 will then accept it only when the
observed circuit limit is above the executable EV range.
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
QUIESCENCE_SEC = 10
MIN_NORMAL_CIRCUIT_A = 16
MAX_EV_A = 16

SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.3.phase-writer-live.js"
FLOW_NAME = "EM v2 | 60 Actuator | EV Power v0.4.3 PHASE-WRITER [LIVE]"
EXPECTED_SCHEMA = "EM2_EV_ACTUATOR_V0.4.3_PHASE_WRITER"
ALLOWED_PREVIOUS_SCHEMAS = {
    "EM2_EV_ACTUATOR_V0.4.2_PHASE_WRITER",
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
    fd, path = tempfile.mkstemp(prefix="ems-homey-ev-v043-", suffix=".json")
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
    }


def stable_guard(st, charger):
    observed = st.get("observed") or {}
    target_a = st.get("targetA")
    positive_target = isinstance(target_a, (int, float)) and target_a >= 6
    offered_a = charger.get("offeredA")
    power_w = charger.get("powerW")
    physically_running = (
        charger.get("chargeState") == "plugged_in_charging"
        and charger.get("charging") is True
        and isinstance(offered_a, (int, float))
        and abs(offered_a - target_a) <= 0.5
        and isinstance(power_w, (int, float))
        and power_w > 500
    )
    return {
        "schema": st.get("schema") in ALLOWED_PREVIOUS_SCHEMAS,
        "statusStable": st.get("status") == "STABLE",
        "transitionStable": (st.get("transition") or {}).get("stage") == "STABLE",
        "live": st.get("live") is True,
        "phaseAligned": st.get("phaseMode") == st.get("confirmedMode"),
        "normalCircuitCap": isinstance(charger.get("circuitTargetA"), (int, float))
        and charger.get("circuitTargetA") >= MIN_NORMAL_CIRCUIT_A,
        "positiveTargetPhysicallyRunning": (not positive_target) or physically_running,
        "observedCircuitConsistent": observed.get("circuitTargetA")
        in (None, charger.get("circuitTargetA")),
    }


def orphaned_cap_guard(st, charger):
    transition = st.get("transition") or {}
    offered_a = charger.get("offeredA")
    power_w = charger.get("powerW")
    circuit_a = charger.get("circuitTargetA")
    return {
        "schema": st.get("schema") in ALLOWED_PREVIOUS_SCHEMAS,
        "failed": st.get("status") == "FAILED",
        "knownReason": st.get("reason")
        in ("CIRCUIT_LIMIT_BELOW_REQUEST", "CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE"),
        "transitionFailed": transition.get("stage") == "FAILED",
        "originalCircuitLost": transition.get("originalCircuitA") is None,
        "live": st.get("live") is True,
        "paused": charger.get("chargeState") == "plugged_in_paused"
        and charger.get("charging") is not True,
        "offeredZero": isinstance(offered_a, (int, float)) and offered_a <= 1,
        "powerZero": isinstance(power_w, (int, float)) and power_w <= 250,
        "temporaryCapRange": isinstance(circuit_a, (int, float))
        and 6 <= circuit_a <= MAX_EV_A,
    }


def all_true(checks):
    return all(checks.values())


def classify(st, charger):
    stable = stable_guard(st, charger)
    orphan = orphaned_cap_guard(st, charger)
    if all_true(stable):
        return "STABLE", stable
    if all_true(orphan):
        return "ORPHANED_CAP", orphan
    return "INVALID", {"stable": stable, "orphanedCap": orphan}


def main():
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "EM2_EV_ACTUATOR_V0.4.3_PHASE_WRITER",
        "const PHASE_EXECUTION_ENABLED=true",
        "RECOVERING_CIRCUIT_CAP",
        "RESTORE_FAILED_TRANSITION_CIRCUIT_CAP",
        "CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE",
        "ORPHAN_CIRCUIT_BASELINE_CONFIRMED",
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"SOURCE_MARKER_MISSING:{marker}")

    before_status = status()
    before_charger = charger_state()
    mode, guards1 = classify(before_status, before_charger)

    print("=== PRE-UPGRADE STATUS ===")
    print(json.dumps({
        "mode": mode,
        "schema": before_status.get("schema"),
        "status": before_status.get("status"),
        "reason": before_status.get("reason"),
        "phaseMode": before_status.get("phaseMode"),
        "confirmedMode": before_status.get("confirmedMode"),
        "transition": before_status.get("transition"),
        "targetA": before_status.get("targetA"),
        "charger": before_charger,
        "guards": guards1,
    }, indent=2))

    if mode == "INVALID":
        raise RuntimeError("PRE_UPGRADE_UNSAFE_OR_UNKNOWN_STATE")

    print(f"QUIESCENCE: waiting {QUIESCENCE_SEC}s and rechecking {mode}")
    time.sleep(QUIESCENCE_SEC)
    confirm_status = status()
    confirm_charger = charger_state()
    mode2, guards2 = classify(confirm_status, confirm_charger)
    guards2 = dict(guards2)
    guards2.update({
        "sameMode": mode2 == mode,
        "sameControlRevision": confirm_status.get("controlRevision")
        == before_status.get("controlRevision"),
        "samePhaseMode": confirm_status.get("phaseMode") == before_status.get("phaseMode"),
        "sameTargetA": confirm_status.get("targetA") == before_status.get("targetA"),
        "sameCircuitTargetA": confirm_charger.get("circuitTargetA")
        == before_charger.get("circuitTargetA"),
    })
    print("quiescenceGuards:", json.dumps(guards2, indent=2))
    if not all_true(guards2):
        raise RuntimeError("PRE_UPGRADE_CHANGED_DURING_QUIESCENCE")

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
            "v0.4.3 LIVE: failed phase transitions restore the captured circuit "
            "baseline before normal control resumes; orphaned caps fail closed."
        )

    candidate = {"name": FLOW_NAME, "enabled": True, "cards": cards}

    final_status = status()
    final_charger = charger_state()
    final_mode, final_guards = classify(final_status, final_charger)
    final_guards = dict(final_guards)
    final_guards.update({
        "sameMode": final_mode == mode,
        "sameControlRevision": final_status.get("controlRevision")
        == confirm_status.get("controlRevision"),
        "samePhaseMode": final_status.get("phaseMode") == confirm_status.get("phaseMode"),
        "sameTargetA": final_status.get("targetA") == confirm_status.get("targetA"),
        "sameCircuitTargetA": final_charger.get("circuitTargetA")
        == confirm_charger.get("circuitTargetA"),
    })
    if not all_true(final_guards):
        print("finalGuards:", json.dumps(final_guards, indent=2))
        raise RuntimeError("PRE_UPGRADE_CHANGED_BEFORE_PUSH")

    try:
        print()
        print("=== DEPLOY V0.4.3 ===")
        push(candidate)
        run("api", "flow", "trigger-advanced-flow", "--id", FLOW_ID)
        time.sleep(4)

        after = status()

        # On first v0.4.3 invocation an inherited v0.4.2 status is intentionally
        # not reused. In the diagnosed orphan case the new writer therefore
        # first re-observes CIRCUIT_LIMIT_BELOW_REQUEST from a clean STABLE
        # state. A second evaluation must convert that into the explicit
        # orphan-recovery fail-closed reason without any physical write.
        if (
            mode == "ORPHANED_CAP"
            and after.get("status") == "FAILED"
            and after.get("reason") == "CIRCUIT_LIMIT_BELOW_REQUEST"
        ):
            run("api", "flow", "trigger-advanced-flow", "--id", FLOW_ID)
            time.sleep(2)
            after = status()

        print(json.dumps({
            "schema": after.get("schema"),
            "status": after.get("status"),
            "reason": after.get("reason"),
            "phaseMode": after.get("phaseMode"),
            "confirmedMode": after.get("confirmedMode"),
            "transition": after.get("transition"),
            "transitionSlow": after.get("transitionSlow"),
        }, indent=2))

        if after.get("schema") != EXPECTED_SCHEMA:
            raise RuntimeError("V043_SCHEMA_NOT_ACTIVE")
        if after.get("live") is not True:
            raise RuntimeError("V043_NOT_LIVE")
        if after.get("phaseExecutionEnabled") is not True:
            raise RuntimeError("V043_EXECUTION_NOT_ENABLED")

        if mode == "STABLE":
            if after.get("status") == "FAILED":
                raise RuntimeError("V043_FAILED:" + str(after.get("reason")))
        else:
            if after.get("status") != "FAILED":
                raise RuntimeError("V043_ORPHAN_EXPECTED_FAIL_CLOSED")
            if after.get("reason") != "CIRCUIT_RECOVERY_REQUIRES_KNOWN_BASELINE":
                raise RuntimeError("V043_ORPHAN_REASON:" + str(after.get("reason")))

        print()
        print("PASS: v0.4.3 active; sole EV writer preserved")
        if mode == "ORPHANED_CAP":
            print(
                "NEXT: restore the independently proven pre-transition circuit "
                "baseline while the session remains paused. Do not guess it."
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

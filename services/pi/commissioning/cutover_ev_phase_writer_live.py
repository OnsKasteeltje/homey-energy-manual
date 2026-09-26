#!/usr/bin/env python3
"""
Guarded LIVE cutover for EV phase writer v0.4.1.

LIVE guard requires:
- current armed-disabled writer v0.4.0 is active;
- authoritative target is 1P or 3P at >=6A;
- Easee phase readback is confirmed as locked 1P or locked 3P;
- charger is plugged_in_paused, 0A offered, <=250W;
- circuit target is known and >= requested current;
- P1 export is sufficient for the requested mode/current load.

If target mode differs from confirmed mode, v0.4 performs the full guarded
phase-change path before resume.

Then the existing sole actuator flow is updated in-place to v0.4.1 LIVE and
driven step-by-step until STABLE. No second writer is created.
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

ACTUATOR_FLOW_ID = "fea23193-a03f-49dd-9780-7e72ee48747d"
BRIDGE_FLOW_ID = "8bf53fdb-76f4-47db-8ccb-773ac515f06e"
SCRIPT_CARD = "10a00000-0000-4000-8000-000000000002"
STATUS_ID = "ea1f8a44-2f6c-490e-9b86-bae761886cf9"
CHARGER_ID = "4d0b6913-d940-474e-95d6-b43f194c4119"
P1_ID = "7a696d77-15fb-4b68-9bce-f1e39bff5045"

LIVE_SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.1.phase-writer-live.js"
ARMED_SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.0.phase-writer.js"

LIVE_NAME = "EM v2 | 60 Actuator | EV Power v0.4.1 PHASE-WRITER [LIVE]"
ARMED_NAME = "EM v2 | 60 Actuator | EV Power v0.4.0 PHASE-WRITER [ARMED-DISABLED]"

P1_MARGIN_W = 250
MAX_STEPS = 18


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


def body_file(payload):
    fd, path = tempfile.mkstemp(prefix="ems-homey-live-writer-", suffix=".json")
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


def cap(device, name):
    obj = (device.get("capabilitiesObj") or {}).get(name)
    return obj.get("value") if isinstance(obj, dict) else None


def get_status():
    v = jrun("api", "logic", "get-variable", "--id", STATUS_ID, "--json")
    raw = v.get("value") if isinstance(v, dict) else None
    return json.loads(raw) if isinstance(raw, str) else {}


def get_device(device_id):
    return jrun("api", "devices", "get-device", "--id", device_id, "--json")


def charger_state():
    d = get_device(CHARGER_ID)
    return {
        "chargeState": cap(d, "evcharger_charging_state"),
        "charging": cap(d, "evcharger_charging"),
        "targetA": cap(d, "target_charger_current"),
        "offeredA": cap(d, "measure_current.offered"),
        "powerW": cap(d, "measure_power"),
        "circuitTargetA": cap(d, "target_circuit_current"),
    }


def p1_power():
    d = get_device(P1_ID)
    return cap(d, "measure_power")


def update_writer(source_path, flow_name):
    source = source_path.read_text(encoding="utf-8")
    raw = jrun("api", "flow", "get-advanced-flow", "--id", ACTUATOR_FLOW_ID, "--json")
    flow = unwrap_flow(raw)
    cards = flow.get("cards") if isinstance(flow, dict) else None
    if not isinstance(cards, dict):
        raise RuntimeError("ACTUATOR_FLOW_CARDS_INVALID")
    card = cards.get(SCRIPT_CARD)
    if not isinstance(card, dict) or card.get("type") != "action":
        raise RuntimeError("ACTUATOR_SCRIPT_CARD_INVALID")
    card.setdefault("args", {})["code"] = source

    note = cards.get("10a00000-0000-4000-8000-000000000003")
    if isinstance(note, dict) and note.get("type") == "note":
        note["value"] = (
            "v0.4.1 PHASE-WRITER LIVE: sole EV writer; native Homey Easee "
            "pause/resume/current/circuit actions; Easee Cloud only for phase mode."
            if "PHASE_EXECUTION_ENABLED=true" in source
            else
            "v0.4.0 PHASE-WRITER ARMED-DISABLED: no physical execution."
        )

    body = {"name": flow_name, "enabled": True, "cards": cards}
    path = body_file(body)
    try:
        run(
            "api", "flow", "update-advanced-flow",
            "--id", ACTUATOR_FLOW_ID,
            "--body", f"@{path}",
        )
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def trigger(flow_id):
    run("api", "flow", "trigger-advanced-flow", "--id", flow_id)


def rollback_armed():
    try:
        update_writer(ARMED_SOURCE, ARMED_NAME)
        print("ROLLBACK: actuator source returned to ARMED-DISABLED")
    except Exception as exc:
        print(f"ROLLBACK WARNING: {exc}", file=sys.stderr)


def main():
    live_source = LIVE_SOURCE.read_text(encoding="utf-8")
    armed_source = ARMED_SOURCE.read_text(encoding="utf-8")
    if "const PHASE_EXECUTION_ENABLED=true" not in live_source:
        raise RuntimeError("LIVE_SOURCE_NOT_ENABLED")
    if "const PHASE_EXECUTION_ENABLED=false" not in armed_source:
        raise RuntimeError("ARMED_SOURCE_NOT_DISABLED")

    print("=== REFRESH AUTHORITATIVE CONTROL ===")
    trigger(BRIDGE_FLOW_ID)
    time.sleep(5)

    status = get_status()
    charger = charger_state()
    p1w = p1_power()

    print("=== PRE-CUTOVER ===")
    print(json.dumps({
        "actuator": {
            "schema": status.get("schema"),
            "status": status.get("status"),
            "targetA": status.get("targetA"),
            "phaseMode": status.get("phaseMode"),
            "confirmedMode": status.get("confirmedMode"),
            "phaseExecutionEnabled": status.get("phaseExecutionEnabled"),
            "physicalWritePerformed": status.get("physicalWritePerformed"),
        },
        "easee": charger,
        "p1W": p1w,
    }, indent=2))

    target_a = status.get("targetA")
    phase_mode = status.get("phaseMode")
    confirmed = status.get("confirmedMode")

    guards = {
        "armedSchema": status.get("schema") == "EM2_EV_ACTUATOR_V0.4.0_PHASE_WRITER",
        "armedDisabled": status.get("phaseExecutionEnabled") is False,
        "noPriorWrite": status.get("physicalWritePerformed") is False,
        "targetMode": phase_mode in ("1P", "3P"),
        "confirmedMode": confirmed in ("1P", "3P"),
        "targetA": isinstance(target_a, int) and 6 <= target_a <= 16,
        "paused": charger.get("chargeState") == "plugged_in_paused" and charger.get("charging") is False,
        "offeredZero": isinstance(charger.get("offeredA"), (int, float)) and charger.get("offeredA") <= 1,
        "powerZero": isinstance(charger.get("powerW"), (int, float)) and charger.get("powerW") <= 250,
        "circuitKnown": isinstance(charger.get("circuitTargetA"), (int, float)),
    }
    if guards["targetA"] and guards["circuitKnown"]:
        guards["circuitEnough"] = charger["circuitTargetA"] >= target_a
        watts_per_amp = 230 if phase_mode == "1P" else 690
        required_w = target_a * watts_per_amp
        guards["p1ExportEnough"] = (
            isinstance(p1w, (int, float)) and
            p1w <= -(required_w - P1_MARGIN_W)
        )
    else:
        guards["circuitEnough"] = False
        guards["p1ExportEnough"] = False

    failed = [k for k, ok in guards.items() if not ok]
    print("guards:", json.dumps(guards, indent=2))
    if failed:
        raise RuntimeError("PRE_CUTOVER_GUARD_FAILED:" + ",".join(failed))

    original_circuit = charger["circuitTargetA"]

    print()
    print("=== PROMOTE SOLE ACTUATOR TO LIVE ===")
    update_writer(LIVE_SOURCE, LIVE_NAME)
    print(f"PASS: {LIVE_NAME}")

    try:
        trigger(ACTUATOR_FLOW_ID)
        last_at = None
        stagnant_polls = 0

        for step in range(1, MAX_STEPS + 1):
            time.sleep(2)

            status = get_status()
            charger = charger_state()
            public = {
                "step": step,
                "status": status.get("status"),
                "reason": status.get("reason"),
                "targetA": status.get("targetA"),
                "phaseMode": status.get("phaseMode"),
                "candidateAction": status.get("candidateAction"),
                "confirmedMode": status.get("confirmedMode"),
                "phaseExecutionEnabled": status.get("phaseExecutionEnabled"),
                "physicalWritePerformed": status.get("physicalWritePerformed"),
                "transitionStage": (status.get("transition") or {}).get("stage"),
                "easee": charger,
            }
            print(json.dumps(public, indent=2))

            if status.get("phaseExecutionEnabled") is not True:
                raise RuntimeError("LIVE_STATUS_NOT_ENABLED")

            if status.get("status") == "FAILED":
                raise RuntimeError("WRITER_FAILED:" + str(status.get("reason")))

            stable = (
                status.get("status") == "STABLE" and
                (status.get("transition") or {}).get("stage") == "STABLE" and
                charger.get("chargeState") == "plugged_in_charging" and
                charger.get("charging") is True and
                isinstance(charger.get("targetA"), (int, float)) and
                charger.get("targetA") >= 6 and
                isinstance(charger.get("offeredA"), (int, float)) and
                charger.get("offeredA") >= 5.5 and
                isinstance(charger.get("powerW"), (int, float)) and
                charger.get("powerW") > 1000 and
                charger.get("circuitTargetA") == original_circuit
            )
            if stable:
                print()
                print("PASS: LIVE writer stable; Tesla charging and circuit limit restored")
                return

            current_at = status.get("at")
            if current_at and current_at == last_at:
                stagnant_polls += 1
            else:
                stagnant_polls = 0
                last_at = current_at

            # Self-trigger is the normal path. Only poke the flow if its
            # persisted status has not changed for ~4 seconds.
            if stagnant_polls >= 2:
                print("fallback: actuator status stalled; issuing one external trigger")
                trigger(ACTUATOR_FLOW_ID)
                stagnant_polls = 0

        raise RuntimeError("LIVE_CUTOVER_TIMEOUT")
    except Exception:
        rollback_armed()
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        rollback_armed()
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

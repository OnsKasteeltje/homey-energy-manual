#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"
ADVISOR = Path("/home/jeroen/ems/runtime/planner/warm-water/seasonal_source_advisor.py")
OUTPUT = Path("/home/jeroen/ems/data/ww-seasonal-advisor.json")
NOTIFY_STATE = Path("/home/jeroen/ems/data/ww-seasonal-notify-state.json")
MODE_VARIABLE_NAME = "WW_Boilermodus"
MODE_VARIABLE_ID = "f9d885a4-fca2-4aea-a5a9-a5c05da90835"


def run_homey(args):
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
        msg = (r.stderr or r.stdout).strip()
        raise RuntimeError(msg[:800])
    return r.stdout


def current_mode():
    raw = run_homey([
        "api", "logic", "get-variable",
        "--id", MODE_VARIABLE_ID,
        "--json",
    ])
    variable = json.loads(raw)
    if not isinstance(variable, dict):
        raise RuntimeError(f"Unexpected Homey response for {MODE_VARIABLE_NAME!r}")

    returned_name = variable.get("name")
    if returned_name and returned_name != MODE_VARIABLE_NAME:
        raise RuntimeError(
            f"Homey variable id {MODE_VARIABLE_ID} resolved to {returned_name!r}, "
            f"expected {MODE_VARIABLE_NAME!r}"
        )

    value = variable.get("value")
    if isinstance(value, bool):
        return "BOILER" if value else "CV"

    normalized = str(value).strip().lower()
    if normalized in {"ja", "yes", "true", "1", "boiler", "aan", "on"}:
        return "BOILER"
    if normalized in {"nee", "no", "false", "0", "cv", "uit", "off"}:
        return "CV"

    raise RuntimeError(f"Unsupported {MODE_VARIABLE_NAME} value: {value!r}")


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, separators=(",", ":")) + "\n")
    tmp.replace(path)


def send_notification(advice, result):
    analysis = result.get("analysis", {})
    boiler = analysis.get("boilerCostEurPerUsableKWh")
    cv = analysis.get("cvCostEurPerUsableKWh")
    pv_share = analysis.get("pvOpportunityShare")
    target = "CV" if advice == "ADVISE_SWITCH_TO_CV" else "elektrische boiler"

    parts = [f"Warmwateradvies: schakel handmatig naar {target}."]
    if isinstance(boiler, (int, float)) and isinstance(cv, (int, float)):
        parts.append(f"Boiler €{boiler:.3f} vs CV €{cv:.3f} per bruikbare kWh.")
    if isinstance(pv_share, (int, float)):
        parts.append(f"PV-opportunity {pv_share * 100:.0f}%.")
    parts.append("WW_Boilermodus is niet automatisch gewijzigd.")
    message = " ".join(parts)

    run_homey([
        "api", "notifications", "create-notification",
        "--excerpt", message,
        "--json",
    ])
    return message


def maybe_notify(mode):
    result = load_json(OUTPUT)
    if result.get("status") != "OK":
        print(f"notification: skipped status={result.get('status')}")
        return

    advice = result.get("advice")
    state = load_json(NOTIFY_STATE)
    last = state.get("lastNotifiedAdvice")

    # Once the user has manually followed the previous advice, clear the claim
    # so a future reverse-season switch can be notified once.
    if (last == "ADVISE_SWITCH_TO_CV" and mode == "CV") or (
        last == "ADVISE_SWITCH_TO_BOILER" and mode == "BOILER"
    ):
        last = None
        state = {}
        save_json(NOTIFY_STATE, state)

    if advice not in {"ADVISE_SWITCH_TO_CV", "ADVISE_SWITCH_TO_BOILER"}:
        print("notification: no confirmed switch advice")
        return
    if last == advice:
        print(f"notification: already sent for {advice}")
        return

    message = send_notification(advice, result)
    save_json(NOTIFY_STATE, {
        "lastNotifiedAdvice": advice,
        "lastNotifiedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "message": message,
    })
    print(f"notification: sent {advice}")


def main():
    try:
        mode = current_mode()
    except Exception as exc:
        print(f"FAIL: cannot resolve current WW mode from Homey: {exc}", file=sys.stderr)
        return 2

    print(f"WW current mode: {mode}")
    result = subprocess.run([
        "/usr/bin/python3",
        str(ADVISOR),
        "--mode",
        mode,
    ])
    if result.returncode != 0:
        return result.returncode

    try:
        maybe_notify(mode)
    except Exception as exc:
        # Advisor result remains valid even if the notification transport fails.
        # Do not claim the advice as notified on failure.
        print(f"FAIL: Homey notification failed: {exc}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

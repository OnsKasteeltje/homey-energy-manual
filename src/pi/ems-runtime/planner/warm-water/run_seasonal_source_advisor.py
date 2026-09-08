#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_BIN = "/opt/node-v24.20.0/bin"
MODE_VARIABLE_ID = "f9d885a4-fca2-4aea-a5a9-a5c05da90835"
MODE_VARIABLE_NAME = "WW_Boilermodus"

ADVISOR = Path("/home/jeroen/ems/runtime/planner/warm-water/seasonal_source_advisor.py")
OUTPUT = Path("/home/jeroen/ems/data/ww-seasonal-advisor.json")
NOTIFY_STATE = Path("/home/jeroen/ems/data/ww-seasonal-notify-state.json")
CONTRACT_POLICY = Path("/home/jeroen/ems/runtime/planner/contract-policy.json")

HOMEY_WEBHOOK_BASE = os.environ.get("HOMEY_WEBHOOK_BASE", "").rstrip("/")
HOMEY_WEBHOOK_EVENT = "ww_seasonal_advice"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def validate_contract_policy():
    """Fail closed: production WW economics are fixed-contract only."""
    policy = load_json(CONTRACT_POLICY, None)
    if not isinstance(policy, dict):
        raise RuntimeError("CONTRACT_CONFIG_ERROR: contract-policy.json missing or invalid")
    if policy.get("productionContractMode") != "FIXED":
        raise RuntimeError("CONTRACT_CONFIG_ERROR: productionContractMode must remain FIXED")
    if policy.get("productionContractId") != "ENGIE_3Y_2026_2029":
        raise RuntimeError("CONTRACT_CONFIG_ERROR: unexpected production fixed contract")
    dynamic = policy.get("dynamicPricing") or {}
    if dynamic.get("enabledForProduction") is not False:
        raise RuntimeError("CONTRACT_CONFIG_ERROR: dynamic pricing must be disabled for production")
    if dynamic.get("automaticFallbackAllowed") is not False:
        raise RuntimeError("CONTRACT_CONFIG_ERROR: dynamic fallback must be disabled")
    safety = policy.get("safety") or {}
    if safety.get("failClosed") is not True:
        raise RuntimeError("CONTRACT_CONFIG_ERROR: contract policy must fail closed")
    if safety.get("automaticContractModeSwitchAllowed") is not False:
        raise RuntimeError("CONTRACT_CONFIG_ERROR: automatic contract switching is forbidden")


def run_homey(args):
    env = os.environ.copy()
    env["PATH"] = f"{NODE_BIN}:{env.get('PATH', '')}"
    proc = subprocess.run(
        [str(HOMEY_CLI), *args], cwd=str(HOMEY_PROJECT), env=env,
        text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"homey exit {proc.returncode}")
    return proc.stdout


def resolve_current_mode():
    raw = run_homey(["api", "logic", "get-variable", "--id", MODE_VARIABLE_ID, "--json"])
    variable = json.loads(raw)
    if variable.get("name") and variable.get("name") != MODE_VARIABLE_NAME:
        raise RuntimeError(f"logic variable ID mismatch: expected {MODE_VARIABLE_NAME}, got {variable.get('name')}")
    value = variable.get("value")
    if isinstance(value, bool):
        return "BOILER" if value else "CV"
    normalized = str(value).strip().lower()
    if normalized in {"ja", "yes", "true", "1", "boiler", "aan", "on"}:
        return "BOILER"
    if normalized in {"nee", "no", "false", "0", "cv", "uit", "off"}:
        return "CV"
    raise RuntimeError(f"unsupported {MODE_VARIABLE_NAME} value: {value!r}")


def save_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def target_mode_for_advice(advice):
    if advice == "ADVISE_SWITCH_TO_CV": return "CV"
    if advice == "ADVISE_SWITCH_TO_BOILER": return "BOILER"
    return None


def build_notification_message(payload, target):
    analysis = payload.get("analysis") or {}
    reason = payload.get("reason") or "economische vergelijking"
    pv_share = analysis.get("pvOpportunityShare")
    extra = f" Gemeten PV-opportunity aandeel {pv_share * 100:.1f}%." if isinstance(pv_share, (int, float)) else ""
    return f"Warmwater seizoensadvies: schakel handmatig naar {target}. {reason}.{extra} WW_Boilermodus is niet automatisch gewijzigd."


def send_homey_webhook(message):
    if not HOMEY_WEBHOOK_BASE:
        raise RuntimeError("HOMEY_WEBHOOK_BASE is not configured")
    url = f"{HOMEY_WEBHOOK_BASE}/webhook?event={quote(HOMEY_WEBHOOK_EVENT, safe='')}&tag={quote(message, safe='')}"
    with urlopen(url, timeout=10) as response:
        status = getattr(response, "status", 200)
        if status < 200 or status >= 300:
            raise RuntimeError(f"Homey webhook returned HTTP {status}")


def maybe_notify(payload, current_mode):
    if payload.get("status") != "OK":
        print(f"notification: skipped status={payload.get('status')}")
        return
    advice = payload.get("advice")
    target = target_mode_for_advice(advice)
    if not target:
        print(f"notification: skipped advice={advice}")
        return
    state = load_json(NOTIFY_STATE, {})
    last_advice = state.get("lastNotifiedAdvice")
    previous_target = target_mode_for_advice(last_advice)
    if previous_target and current_mode == previous_target:
        last_advice = None
        state["lastNotifiedAdvice"] = None
        save_json_atomic(NOTIFY_STATE, state)
    if advice == last_advice:
        print(f"notification: skipped duplicate advice={advice}")
        return
    send_homey_webhook(build_notification_message(payload, target))
    state.update({
        "lastNotifiedAdvice": advice,
        "lastNotifiedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "targetMode": target, "transport": "HOMEY_LOCAL_WEBHOOK", "event": HOMEY_WEBHOOK_EVENT,
    })
    save_json_atomic(NOTIFY_STATE, state)
    print(f"notification: sent webhook event={HOMEY_WEBHOOK_EVENT} target={target}")


def main():
    try:
        validate_contract_policy()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 4
    try:
        current_mode = resolve_current_mode()
    except Exception as exc:
        print(f"FAIL: cannot resolve current WW mode from Homey: {exc}", file=sys.stderr)
        return 2
    print(f"WW current mode: {current_mode}")
    proc = subprocess.run([sys.executable, str(ADVISOR), "--mode", current_mode], check=False)
    if proc.returncode != 0:
        return proc.returncode
    try:
        payload = json.loads(OUTPUT.read_text())
        maybe_notify(payload, current_mode)
    except Exception as exc:
        print(f"FAIL: notification handling failed: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

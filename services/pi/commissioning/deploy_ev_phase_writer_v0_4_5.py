#!/usr/bin/env python3
"""
Deploy EV phase writer v0.4.5 to the existing single production writer flow.

Safety:
- Reuses the existing actuator flow ID; never creates a second physical writer.
- Preserves all existing trigger/start/note cards and only replaces the
  HomeyScript action source plus the flow name.
- Requires LIVE phase execution and the v0.4.5 auth-alert markers in source.
- Does not manually trigger charging or change Easee capabilities.
- The existing Gate variable-change trigger will invoke the writer naturally.

Run from repository root on the EMS Pi after GitHub main is updated.
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
SCRIPT_CARD_ID = "10a00000-0000-4000-8000-000000000002"
FLOW_NAME = "EM v2 | 60 Actuator | EV Power v0.4.5 AUTH-ALERT [LIVE]"
SOURCE = ROOT / "src/homey/actuators/ev-power/ev-power-v0.4.5.phase-writer-live.js"
STATUS_ID = "ea1f8a44-2f6c-490e-9b86-bae761886cf9"
LIVE_ID = "8d47e98d-e4bc-4f47-8c02-c2aca7f7a978"


def run(*args):
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    delays = (0, 3, 6, 12)
    last = None
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
        last = cp
        if cp.returncode == 0:
            return cp.stdout
        msg = (cp.stderr or cp.stdout or "").strip()
        if "too many requests" not in msg.lower() or attempt == len(delays) - 1:
            raise RuntimeError(f"HOMEY_CLI_FAILED:{' '.join(args)}:{msg[:500]}")
    raise RuntimeError(
        f"HOMEY_CLI_FAILED:{' '.join(args)}:"
        f"{((last.stderr or last.stdout) if last else '')[:500]}"
    )


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
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
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


def main():
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "EM2_EV_ACTUATOR_V0.4.5_PHASE_WRITER",
        "const PHASE_EXECUTION_ENABLED=true",
        "EASEE_PHASE_COMMAND_RETRY",
        "EM2_EV_AUTH_ALERT_V0.1",
        "homey:manager:mobile:push_text",
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"SOURCE_MARKER_MISSING:{marker}")

    raw = jrun("api", "flow", "get-advanced-flow", "--id", FLOW_ID, "--json")
    flow = unwrap_flow(raw)
    if not isinstance(flow, dict):
        raise RuntimeError("FLOW_INVALID")

    cards = flow.get("cards")
    if not isinstance(cards, dict):
        raise RuntimeError("FLOW_CARDS_INVALID")

    card = cards.get(SCRIPT_CARD_ID)
    if not isinstance(card, dict) or card.get("type") != "action":
        raise RuntimeError("SCRIPT_CARD_INVALID")

    card.setdefault("args", {})["code"] = source
    body = {
        "name": FLOW_NAME,
        "enabled": True,
        "cards": cards,
    }

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

    verify = unwrap_flow(
        jrun("api", "flow", "get-advanced-flow", "--id", FLOW_ID, "--json")
    )
    if verify.get("name") != FLOW_NAME or verify.get("enabled") is not True:
        raise RuntimeError("DEPLOY_VERIFY_FLOW_METADATA_FAILED")
    deployed = ((verify.get("cards") or {}).get(SCRIPT_CARD_ID) or {}).get("args", {}).get("code", "")
    for marker in required:
        if marker not in deployed:
            raise RuntimeError(f"DEPLOY_VERIFY_MARKER_MISSING:{marker}")

    live = jrun("api", "logic", "get-variable", "--id", LIVE_ID, "--json")
    if live.get("value") is not True:
        raise RuntimeError("EV_WRITER_LIVE_FLAG_NOT_TRUE")

    status_var = jrun("api", "logic", "get-variable", "--id", STATUS_ID, "--json")
    status_raw = status_var.get("value")
    try:
        status = json.loads(status_raw) if isinstance(status_raw, str) else {}
    except json.JSONDecodeError:
        status = {}

    print("PASS: EV writer v0.4.5 source deployed to existing single writer flow.")
    print("Flow:", FLOW_NAME)
    print("Live flag: true")
    print("No manual EV action was triggered by this deploy.")
    print("Current actuator status before next natural Gate trigger:")
    print(json.dumps({
        "schema": status.get("schema"),
        "status": status.get("status"),
        "reason": status.get("reason"),
        "targetA": status.get("targetA"),
        "phaseMode": status.get("phaseMode"),
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

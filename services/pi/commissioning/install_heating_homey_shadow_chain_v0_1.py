#!/usr/bin/env python3
"""Controlled first commissioning of the Heating Pi -> Homey SHADOW chain.

Default is DRY-RUN. --apply is required for Homey Logic/Advanced Flow writes
and for enabling the Pi publisher timer. No Honeywell/device write is present
in this installer or in the rendered Homey sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"
DATA = Path("/home/jeroen/ems/data")
CONFIG = DATA / "heating-control-homey-shadow-config.json"
BACKUP_DIR = Path("/home/jeroen/ems/backups/homey-flows")

ADAPTER_SOURCE = ROOT / "src/homey/adapters/heating-control/heating-control-v0.1.shadow.js"
GATE_SOURCE = ROOT / "src/homey/validation/heating-control-adapter-gate-v0.1.shadow.js"
PUBLISHER_SOURCE = ROOT / "services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py"
SERVICE_SOURCE = ROOT / "deploy/systemd/ems-heating-homey-shadow-publish.service"
TIMER_SOURCE = ROOT / "deploy/systemd/ems-heating-homey-shadow-publish.timer"

CONFIG_SCHEMA = "EMS_HEATING_HOMEY_SHADOW_CONFIG_V0.1"
PLACEHOLDER_ASSIGNMENT = "const IDS=__EMS_HEATING_IDS__;"
WRITE_SPACING_SECONDS = 3
READ_SPACING_SECONDS = 5
POST_PUBLISH_SETTLE_SECONDS = 8

LOGIC_NAMES = {
    "intent": "EM2_Heating_Control_Intent",
    "adapter": "EM2_Heating_Control_Adapter",
    "gate": "EM2_Heating_Control_Gate",
}
FLOW_NAMES = {
    "adapter": "EM v2 | 60 Adapter | Heating Control v0.1 SHADOW",
    "gate": "EM v2 | 80 Validation | Heating Control Gate v0.1 SHADOW",
}


def run_homey(*args: str) -> str:
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")
    cp = subprocess.run(
        [str(HOMEY_CLI), *args],
        cwd=HOMEY_PROJECT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "").strip()
        if "too many requests" in msg.lower() or "429" in msg:
            raise RuntimeError("HOMEY_RATE_LIMIT_429_STOP_NO_RETRY")
        raise RuntimeError(f"HOMEY_CLI_FAILED:{' '.join(args)}:{msg[:700]}")
    return cp.stdout


def jrun(*args: str):
    raw = run_homey(*args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"HOMEY_JSON_INVALID:{' '.join(args)}:"
            f"chars={len(raw)}:line={exc.lineno}:col={exc.colno}"
        ) from exc


def body_file(payload: dict[str, Any]) -> str:
    fd, path = tempfile.mkstemp(prefix="ems-heating-homey-", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
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


def _base_config():
    return {
        "schema": CONFIG_SCHEMA,
        "mode": "SHADOW",
        "state": "COMMISSIONING",
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "pendingOperation": None,
        "logic": {},
        "flows": {},
    }


def load_config():
    if not CONFIG.exists():
        return _base_config()
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"LOCAL_CONFIG_INVALID:{exc}") from exc
    if config.get("schema") != CONFIG_SCHEMA:
        raise RuntimeError("LOCAL_CONFIG_SCHEMA_INVALID")
    if config.get("mode") != "SHADOW":
        raise RuntimeError("LOCAL_CONFIG_MODE_INVALID")
    if config.get("deviceWrites") is not False:
        raise RuntimeError("LOCAL_CONFIG_DEVICE_WRITE_BOUNDARY_INVALID")
    if config.get("physicalWriteAllowed") is not False:
        raise RuntimeError("LOCAL_CONFIG_PHYSICAL_WRITE_BOUNDARY_INVALID")
    config.setdefault("logic", {})
    config.setdefault("flows", {})
    config.setdefault("pendingOperation", None)
    return config


def save_config(config):
    DATA.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(
        prefix=".heating-control-homey-shadow-config.",
        dir=DATA,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, CONFIG)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def get_variable(var_id: str):
    raw = jrun(
        "api", "raw",
        "--path", f"/api/manager/logic/variable/{var_id}",
    )
    if isinstance(raw, dict) and isinstance(raw.get("variable"), dict):
        raw = raw["variable"]
    if not isinstance(raw, dict) or raw.get("id") != var_id:
        raise RuntimeError(f"TARGETED_LOGIC_READBACK_INVALID:{var_id}")
    return raw


def get_flow(flow_id: str):
    raw = jrun("api", "flow", "get-advanced-flow", "--id", flow_id, "--json")
    if isinstance(raw, dict) and isinstance(raw.get("advancedFlow"), dict):
        return raw["advancedFlow"]
    return raw


def writable_flow(flow):
    return {
        "name": flow["name"],
        "enabled": bool(flow["enabled"]),
        "cards": flow["cards"],
    }


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def backup_flow(flow, label):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BACKUP_DIR / f"{flow['id']}.{stamp}.{label}.json"
    path.write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def create_variable(name: str):
    payload = {"name": name, "type": "string", "value": "{}"}
    path = body_file(payload)
    try:
        return jrun("api", "logic", "create-variable", "--body", f"@{path}", "--json")
    finally:
        os.unlink(path)


def ensure_logic_variables(config, apply: bool):
    result = dict(config.get("logic") or {})

    # Existing commissioned IDs are always validated by targeted readback.
    for key, meta in list(result.items()):
        if key not in LOGIC_NAMES:
            continue
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
            raise RuntimeError(f"LOCAL_LOGIC_METADATA_INVALID:{key}")
        live = get_variable(meta["id"])
        if live.get("name") != LOGIC_NAMES[key]:
            raise RuntimeError(f"TARGETED_LOGIC_NAME_MISMATCH:{key}")
        if live.get("type") != "string":
            raise RuntimeError(f"TARGETED_LOGIC_TYPE_INVALID:{key}")

    missing = [(key, name) for key, name in LOGIC_NAMES.items() if key not in result]
    if missing and not apply:
        print("DRY-RUN: Logic variables to create:")
        for _, name in missing:
            print("  CREATE", name)
        return None

    for key, name in missing:
        # Write-ahead marker prevents an ambiguous retry from creating a
        # duplicate if Homey accepted the create but the response was lost.
        config["pendingOperation"] = {
            "kind": "CREATE_LOGIC",
            "key": key,
            "name": name,
            "startedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        save_config(config)

        created = create_variable(name)
        if isinstance(created, dict) and isinstance(created.get("variable"), dict):
            created = created["variable"]
        if not isinstance(created, dict) or not created.get("id"):
            raise RuntimeError(f"CREATE_LOGIC_VARIABLE_INVALID_RESPONSE:{name}")

        live = get_variable(created["id"])
        if live.get("name") != name or live.get("type") != "string":
            raise RuntimeError(f"CREATE_LOGIC_VARIABLE_READBACK_INVALID:{name}")

        result[key] = {"id": created["id"], "name": name}
        config["logic"] = result
        config["pendingOperation"] = None
        save_config(config)
        print("created Logic:", name, created["id"])
        time.sleep(WRITE_SPACING_SECONDS)

    return result


def render(source_path: Path, ids: dict[str, Any]):
    source = source_path.read_text(encoding="utf-8")
    if source.count(PLACEHOLDER_ASSIGNMENT) != 1:
        raise RuntimeError(f"PLACEHOLDER_ASSIGNMENT_COUNT_INVALID:{source_path}")
    rendered = source.replace(
        PLACEHOLDER_ASSIGNMENT,
        "const IDS=" + json.dumps(ids, separators=(",", ":")) + ";",
    )
    if PLACEHOLDER_ASSIGNMENT in rendered:
        raise RuntimeError(f"PLACEHOLDER_RENDER_FAILED:{source_path}")
    return rendered


def adapter_flow(logic, source):
    return {
        "name": FLOW_NAMES["adapter"],
        "enabled": True,
        "cards": {
            "a1000000-0000-4000-8000-000000000001": {
                "type": "trigger",
                "id": "homey:manager:logic:variable_changed",
                "x": 0,
                "y": 0,
                "args": {"variable": logic["intent"]},
                "outputSuccess": ["a1000000-0000-4000-8000-000000000003"],
            },
            "a1000000-0000-4000-8000-000000000002": {
                "type": "start",
                "x": 0,
                "y": 180,
                "outputSuccess": ["a1000000-0000-4000-8000-000000000003"],
            },
            "a1000000-0000-4000-8000-000000000003": {
                "type": "action",
                "id": "homey:app:com.athom.homeyscript:runCode_v2",
                "x": 380,
                "y": 80,
                "args": {"code": source},
            },
            "a1000000-0000-4000-8000-000000000004": {
                "type": "note",
                "x": 350,
                "y": -140,
                "color": "blue",
                "value": "Heating adapter v0.1 SHADOW: Logic translation only. No device reads/writes; no LIVE authority.",
            },
        },
    }


def gate_flow(logic, source):
    return {
        "name": FLOW_NAMES["gate"],
        "enabled": True,
        "cards": {
            "b1000000-0000-4000-8000-000000000001": {
                "type": "trigger",
                "id": "homey:manager:logic:variable_changed",
                "x": 0,
                "y": 0,
                "args": {"variable": logic["adapter"]},
                "outputSuccess": ["b1000000-0000-4000-8000-000000000003"],
            },
            "b1000000-0000-4000-8000-000000000002": {
                "type": "start",
                "x": 0,
                "y": 180,
                "outputSuccess": ["b1000000-0000-4000-8000-000000000003"],
            },
            "b1000000-0000-4000-8000-000000000003": {
                "type": "delay",
                "x": 230,
                "y": 80,
                "args": {"delay": {"number": "2", "multiplier": 1}},
                "outputSuccess": ["b1000000-0000-4000-8000-000000000004"],
            },
            "b1000000-0000-4000-8000-000000000004": {
                "type": "action",
                "id": "homey:app:com.athom.homeyscript:runCode_v2",
                "x": 480,
                "y": 80,
                "args": {"code": source},
            },
            "b1000000-0000-4000-8000-000000000005": {
                "type": "note",
                "x": 450,
                "y": -140,
                "color": "blue",
                "value": "Heating Gate v0.1 SHADOW: targeted Honeywell thermostat READS only for non-HOLD commands. No capability writes.",
            },
        },
    }


def create_flow(candidate):
    path = body_file(candidate)
    try:
        raw = jrun(
            "api", "flow", "create-advanced-flow",
            "--body", f"@{path}", "--json",
        )
    finally:
        os.unlink(path)
    if isinstance(raw, dict) and isinstance(raw.get("advancedFlow"), dict):
        return raw["advancedFlow"]
    return raw


def update_flow(flow_id, candidate):
    path = body_file(candidate)
    try:
        jrun(
            "api", "flow", "update-advanced-flow",
            "--id", flow_id,
            "--body", f"@{path}",
            "--json",
        )
    finally:
        os.unlink(path)


def ensure_flow(key, candidate, config, apply):
    name = FLOW_NAMES[key]
    meta = (config.get("flows") or {}).get(key)

    if meta is None:
        if not apply:
            print("DRY-RUN: CREATE Advanced Flow:", name)
            return None

        config["pendingOperation"] = {
            "kind": "CREATE_ADVANCED_FLOW",
            "key": key,
            "name": name,
            "startedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        save_config(config)

        created = create_flow(candidate)
        if not isinstance(created, dict) or not created.get("id"):
            raise RuntimeError(f"CREATE_ADVANCED_FLOW_INVALID_RESPONSE:{name}")
        flow_id = created["id"]
        time.sleep(WRITE_SPACING_SECONDS)
        live = get_flow(flow_id)
        if writable_flow(live) != candidate:
            raise RuntimeError(f"CREATE_ADVANCED_FLOW_READBACK_MISMATCH:{name}")

        meta = {"id": flow_id, "name": name}
        config.setdefault("flows", {})[key] = meta
        config["pendingOperation"] = None
        save_config(config)
        print("created Flow:", name, flow_id)
        return meta

    if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
        raise RuntimeError(f"LOCAL_FLOW_METADATA_INVALID:{key}")

    live = get_flow(meta["id"])
    if live.get("name") != name:
        raise RuntimeError(f"TARGETED_FLOW_NAME_MISMATCH:{name}")
    before = writable_flow(live)
    if before == candidate:
        print("flow MATCH:", name, meta["id"])
        return meta

    print("flow DIFF:", name, meta["id"])
    print("live hash:", sha(before))
    print("cand hash:", sha(candidate))
    if not apply:
        print("DRY-RUN: update blocked")
        return meta

    backup = backup_flow(live, "predeploy")
    update_flow(meta["id"], candidate)
    time.sleep(WRITE_SPACING_SECONDS)
    after = get_flow(meta["id"])
    if writable_flow(after) != candidate:
        print("readback mismatch; restoring", backup)
        update_flow(meta["id"], before)
        raise RuntimeError(f"ADVANCED_FLOW_READBACK_MISMATCH:{name}")
    print("updated Flow:", name, meta["id"])
    return meta


def validate_ready_pinned_objects(config, adapter_source, gate_source):
    if config.get("state") != "READY":
        raise RuntimeError(f"RESUME_REQUIRES_READY_STATE:{config.get('state')}")

    logic = config.get("logic") or {}
    flows = config.get("flows") or {}
    if set(logic) != set(LOGIC_NAMES):
        raise RuntimeError("READY_LOGIC_IDS_INCOMPLETE")
    if set(flows) != set(FLOW_NAMES):
        raise RuntimeError("READY_FLOW_IDS_INCOMPLETE")

    for key in ("intent", "adapter", "gate"):
        meta = logic.get(key)
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
            raise RuntimeError(f"READY_LOGIC_METADATA_INVALID:{key}")
        live = get_variable(meta["id"])
        if live.get("name") != LOGIC_NAMES[key]:
            raise RuntimeError(f"READY_LOGIC_NAME_MISMATCH:{key}")
        if live.get("type") != "string":
            raise RuntimeError(f"READY_LOGIC_TYPE_INVALID:{key}")
        print("logic MATCH:", LOGIC_NAMES[key], meta["id"])
        time.sleep(READ_SPACING_SECONDS)

    candidates = {
        "adapter": adapter_flow(logic, adapter_source),
        "gate": gate_flow(logic, gate_source),
    }
    for key in ("adapter", "gate"):
        meta = flows.get(key)
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
            raise RuntimeError(f"READY_FLOW_METADATA_INVALID:{key}")
        live = get_flow(meta["id"])
        if live.get("name") != FLOW_NAMES[key]:
            raise RuntimeError(f"READY_FLOW_NAME_MISMATCH:{key}")
        if writable_flow(live) != candidates[key]:
            raise RuntimeError(f"READY_FLOW_READBACK_MISMATCH:{key}")
        print("flow MATCH:", FLOW_NAMES[key], meta["id"])
        time.sleep(READ_SPACING_SECONDS)

    return logic, flows


def _require_shadow_commands(payload, label):
    commands = payload.get("commands")
    if not isinstance(commands, list) or len(commands) != 4:
        raise RuntimeError(f"{label}_COMMAND_SET_INVALID")
    for command in commands:
        if not isinstance(command, dict) or command.get("physicalWrite") is not False:
            raise RuntimeError(f"{label}_PHYSICAL_WRITE_BOUNDARY_INVALID")


def validate_shadow_outputs(intent, adapter_out, gate_out):
    if not isinstance(intent, dict) or intent.get("schema") != "EMS_HEATING_CONTROL_INTENT_V0.1":
        raise RuntimeError("RESUME_INTENT_SCHEMA_INVALID")
    if intent.get("valid") is not True or intent.get("status") != "OK":
        raise RuntimeError(f"RESUME_INTENT_NOT_VALID:{intent.get('reason')}")
    if intent.get("physicalWriteAllowed") is not False:
        raise RuntimeError("RESUME_INTENT_PHYSICAL_WRITE_ALLOWED")
    if intent.get("deviceWrites") is not False:
        raise RuntimeError("RESUME_INTENT_DEVICE_WRITES_ALLOWED")
    if intent.get("liveExecutionAllowed") is not False:
        raise RuntimeError("RESUME_INTENT_LIVE_EXECUTION_ALLOWED")
    if (intent.get("safety") or {}).get("liveExecutionAllowed") is not False:
        raise RuntimeError("RESUME_INTENT_SAFETY_LIVE_EXECUTION_ALLOWED")
    _require_shadow_commands(intent, "RESUME_INTENT")

    if not isinstance(adapter_out, dict) or adapter_out.get("schema") != "EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.1":
        raise RuntimeError("RESUME_ADAPTER_SCHEMA_INVALID")
    if adapter_out.get("valid") is not True or adapter_out.get("status") != "PASS":
        raise RuntimeError(f"RESUME_ADAPTER_NOT_PASS:{adapter_out.get('errors')}")
    if adapter_out.get("physicalWriteAllowed") is not False:
        raise RuntimeError("RESUME_ADAPTER_PHYSICAL_WRITE_ALLOWED")
    if adapter_out.get("deviceWrites") is not False:
        raise RuntimeError("RESUME_ADAPTER_DEVICE_WRITES_ALLOWED")
    if adapter_out.get("liveExecutionAllowed") is not False:
        raise RuntimeError("RESUME_ADAPTER_LIVE_EXECUTION_ALLOWED")
    _require_shadow_commands(adapter_out, "RESUME_ADAPTER")

    if not isinstance(gate_out, dict) or gate_out.get("schema") != "EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.1":
        raise RuntimeError("RESUME_GATE_SCHEMA_INVALID")
    if gate_out.get("finalStatus") != "PASS" or (gate_out.get("errors") or []):
        raise RuntimeError(f"RESUME_GATE_NOT_PASS:{gate_out.get('errors')}")
    if gate_out.get("physicalWriteAllowed") is not False:
        raise RuntimeError("RESUME_GATE_PHYSICAL_WRITE_ALLOWED")
    if gate_out.get("deviceWrites") is not False:
        raise RuntimeError("RESUME_GATE_DEVICE_WRITES_ALLOWED")
    if gate_out.get("liveExecutionAllowed") is not False:
        raise RuntimeError("RESUME_GATE_LIVE_EXECUTION_ALLOWED")
    _require_shadow_commands(gate_out, "RESUME_GATE")

    revision = intent.get("controlRevision")
    if not isinstance(revision, str) or not revision:
        raise RuntimeError("RESUME_CONTROL_REVISION_MISSING")
    if adapter_out.get("sourceControlRevision") != revision:
        raise RuntimeError("RESUME_ADAPTER_REVISION_MISMATCH")
    if gate_out.get("sourceControlRevision") != revision:
        raise RuntimeError("RESUME_GATE_SOURCE_REVISION_MISMATCH")
    if gate_out.get("adapterControlRevision") != revision:
        raise RuntimeError("RESUME_GATE_ADAPTER_REVISION_MISMATCH")
    return revision


def _timer_is_active():
    cp = subprocess.run(
        ["systemctl", "is-active", "ems-heating-homey-shadow-publish.timer"],
        text=True,
        capture_output=True,
        check=False,
    )
    return cp.stdout.strip() == "active"


def resume_ready(config):
    if _timer_is_active():
        raise RuntimeError("RESUME_REQUIRES_PUBLISHER_TIMER_INACTIVE")

    logic = config.get("logic") or {}
    if set(logic) != set(LOGIC_NAMES):
        raise RuntimeError("READY_LOGIC_IDS_INCOMPLETE")
    for key in LOGIC_NAMES:
        meta = logic.get(key)
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
            raise RuntimeError(f"READY_LOGIC_METADATA_INVALID:{key}")

    ids = {key: logic[key]["id"] for key in LOGIC_NAMES}
    adapter_src = render(ADAPTER_SOURCE, ids)
    gate_src = render(GATE_SOURCE, ids)

    logic, flows = validate_ready_pinned_objects(config, adapter_src, gate_src)

    install_pi_runtime()

    subprocess.run(
        ["sudo", "systemctl", "start", "ems-heating-control-gate-shadow.service"],
        check=True,
    )
    subprocess.run(
        ["sudo", "systemctl", "start", "ems-heating-homey-shadow-publish.service"],
        check=True,
    )
    print(f"waiting {POST_PUBLISH_SETTLE_SECONDS}s for Homey Adapter/Gate...")
    time.sleep(POST_PUBLISH_SETTLE_SECONDS)

    intent = read_logic(logic["intent"]["id"])
    time.sleep(READ_SPACING_SECONDS)
    adapter_out = read_logic(logic["adapter"]["id"])
    time.sleep(READ_SPACING_SECONDS)
    gate_out = read_logic(logic["gate"]["id"])

    revision = validate_shadow_outputs(intent, adapter_out, gate_out)

    subprocess.run([
        "sudo", "systemctl", "enable", "--now",
        "ems-heating-homey-shadow-publish.timer",
    ], check=True)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    config["lastValidatedAt"] = now
    config["publisherTimerEnabledAt"] = now
    config["publisherTimerEnabled"] = True
    config["lastValidatedControlRevision"] = revision
    save_config(config)

    print()
    print("PASS: Heating Pi -> Homey SHADOW READY resume validated")
    print("intent:", logic["intent"]["id"], intent.get("status"), revision)
    print("adapter:", logic["adapter"]["id"], adapter_out.get("status"))
    print("gate:", logic["gate"]["id"], gate_out.get("finalStatus"))
    print("adapter flow:", flows["adapter"]["id"])
    print("gate flow:", flows["gate"]["id"])
    print("publisher timer: enabled")
    print("physicalWriteAllowed: false")
    print("liveExecutionAllowed: false")
    print("NOTE: no structural Homey Logic/Flow create/update; one SHADOW Intent value publish only")
    print("NOTE: no Honeywell/device capability write")
    return 0


def install_pi_runtime():
    subprocess.run(
        ["sudo", "install", "-d", "-m", "0755", "/home/jeroen/ems/runtime/homey-deploy"],
        check=True,
    )
    subprocess.run([
        "sudo", "install", "-m", "0755",
        str(PUBLISHER_SOURCE),
        "/home/jeroen/ems/runtime/homey-deploy/publish_heating_control_intent_shadow.py",
    ], check=True)
    for src in (SERVICE_SOURCE, TIMER_SOURCE):
        subprocess.run([
            "sudo", "install", "-m", "0644", str(src),
            f"/etc/systemd/system/{src.name}",
        ], check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)


def read_logic(var_id):
    raw = get_variable(var_id)
    value = raw.get("value")
    try:
        return json.loads(str(value or ""))
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--apply",
        action="store_true",
        help="First-install create/update path for Homey Logic and Advanced Flows",
    )
    modes.add_argument(
        "--resume-ready",
        action="store_true",
        help="Validate an existing READY SHADOW install with paced targeted readbacks, then enable publisher timer",
    )
    args = parser.parse_args()

    for source in (
        ADAPTER_SOURCE, GATE_SOURCE, PUBLISHER_SOURCE, SERVICE_SOURCE, TIMER_SOURCE
    ):
        if not source.exists():
            raise RuntimeError(f"SOURCE_MISSING:{source}")

    mode = "RESUME_READY" if args.resume_ready else "APPLY" if args.apply else "DRY-RUN"
    print("mode:", mode)
    print("physical device writes: FORBIDDEN")

    config = load_config()
    pending = config.get("pendingOperation")
    if pending:
        raise RuntimeError(
            "AMBIGUOUS_PARTIAL_COMMISSIONING:"
            + json.dumps(pending, separators=(",", ":"))
            + ":do not retry creation until the pending Homey object is reconciled"
        )

    if args.resume_ready:
        return resume_ready(config)

    logic = ensure_logic_variables(config, args.apply)

    if logic is None:
        print("DRY-RUN: Advanced Flows to create after Logic IDs exist:")
        for name in FLOW_NAMES.values():
            print("  CREATE", name)
        print("DRY-RUN complete: no Homey or systemd writes performed")
        return 0

    ids = {key: value["id"] for key, value in logic.items()}
    adapter_src = render(ADAPTER_SOURCE, ids)
    gate_src = render(GATE_SOURCE, ids)

    adapter_meta = ensure_flow(
        "adapter", adapter_flow(logic, adapter_src), config, args.apply
    )
    gate_meta = ensure_flow(
        "gate", gate_flow(logic, gate_src), config, args.apply
    )

    if not args.apply:
        print("DRY-RUN complete: targeted readback only; no Homey or systemd writes performed")
        return 0

    if not adapter_meta or not gate_meta:
        raise RuntimeError("FLOW_METADATA_MISSING_AFTER_APPLY")

    config["commissionedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    config["state"] = "READY"
    config["logic"] = logic
    config["flows"] = {"adapter": adapter_meta, "gate": gate_meta}
    config["pendingOperation"] = None
    save_config(config)

    install_pi_runtime()

    subprocess.run(
        ["sudo", "systemctl", "start", "ems-heating-control-gate-shadow.service"],
        check=True,
    )
    subprocess.run(
        ["sudo", "systemctl", "start", "ems-heating-homey-shadow-publish.service"],
        check=True,
    )
    time.sleep(6)

    intent = read_logic(logic["intent"]["id"])
    adapter_out = read_logic(logic["adapter"]["id"])
    gate_out = read_logic(logic["gate"]["id"])

    assert intent and intent.get("schema") == "EMS_HEATING_CONTROL_INTENT_V0.1"
    assert intent.get("physicalWriteAllowed") is False
    assert intent.get("deviceWrites") is False
    assert adapter_out and adapter_out.get("schema") == "EMS_HEATING_CONTROL_ADAPTER_SHADOW_V0.1"
    assert adapter_out.get("physicalWriteAllowed") is False
    assert adapter_out.get("deviceWrites") is False
    assert gate_out and gate_out.get("schema") == "EMS_HEATING_CONTROL_ADAPTER_GATE_SHADOW_V0.1"
    assert gate_out.get("physicalWriteAllowed") is False
    assert gate_out.get("deviceWrites") is False
    assert gate_out.get("liveExecutionAllowed") is False

    subprocess.run([
        "sudo", "systemctl", "enable", "--now",
        "ems-heating-homey-shadow-publish.timer",
    ], check=True)

    print()
    print("PASS: Heating Pi -> Homey SHADOW chain commissioned")
    print("intent:", logic["intent"]["id"], intent.get("valid"), intent.get("controlRevision"))
    print("adapter:", logic["adapter"]["id"], adapter_out.get("status"))
    print("gate:", logic["gate"]["id"], gate_out.get("finalStatus"))
    print("adapter flow:", adapter_meta["id"])
    print("gate flow:", gate_meta["id"])
    print("publisher timer: enabled")
    print("physicalWriteAllowed: false")
    print("liveExecutionAllowed: false")
    print("NOTE: no Honeywell/device capability was written")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

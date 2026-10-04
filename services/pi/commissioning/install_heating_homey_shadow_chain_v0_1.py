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


def normalize_collection(raw, wrapper: str):
    if isinstance(raw, dict) and isinstance(raw.get(wrapper), dict):
        raw = raw[wrapper]
    if isinstance(raw, dict):
        return list(raw.values())
    if isinstance(raw, list):
        return raw
    return []


def get_variables():
    """Discover Logic variables without trusting one large CLI wrapper payload.

    Homey CLI's manager wrapper has been observed to return a truncated JSON
    document on installations with a large Logic-variable set. First use the
    direct documented REST path through `api raw`, which avoids wrapper-side
    object serialization. If that fails syntactically, fall back to the manager
    command for compatibility. Both paths are read-only and failure remains
    fail-closed; malformed JSON is never partially accepted.
    """
    attempts = (
        ("api", "raw", "--path", "/api/manager/logic/variable"),
        ("api", "logic", "get-variables", "--json"),
    )
    errors = []
    for args in attempts:
        try:
            raw = run_homey(*args)
            parsed = json.loads(raw)
            variables = normalize_collection(parsed, "variables")
            if not variables and parsed not in ({}, []):
                raise RuntimeError("HOMEY_VARIABLE_COLLECTION_SHAPE_INVALID")
            return variables
        except (json.JSONDecodeError, RuntimeError) as exc:
            errors.append(f"{' '.join(args)} -> {exc}")
    raise RuntimeError(
        "HOMEY_VARIABLE_DISCOVERY_FAILED:" + " | ".join(errors)
    )


def get_advanced_flows():
    return normalize_collection(
        jrun("api", "flow", "get-advanced-flows", "--json"),
        "advancedFlows",
    )


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


def ensure_logic_variables(apply: bool):
    variables = get_variables()
    by_name = {}
    for var in variables:
        name = var.get("name") if isinstance(var, dict) else None
        if name:
            by_name.setdefault(name, []).append(var)

    result = {}
    missing = []
    for key, name in LOGIC_NAMES.items():
        matches = by_name.get(name, [])
        if len(matches) > 1:
            raise RuntimeError(f"DUPLICATE_LOGIC_VARIABLE:{name}")
        if matches:
            var = matches[0]
            if var.get("type") != "string":
                raise RuntimeError(f"LOGIC_VARIABLE_TYPE_INVALID:{name}")
            result[key] = {"id": var.get("id"), "name": name}
        else:
            missing.append((key, name))

    if missing and not apply:
        print("DRY-RUN: Logic variables to create:")
        for _, name in missing:
            print("  CREATE", name)
        return None

    for key, name in missing:
        created = create_variable(name)
        if isinstance(created, dict) and isinstance(created.get("variable"), dict):
            created = created["variable"]
        if not isinstance(created, dict) or not created.get("id"):
            raise RuntimeError(f"CREATE_LOGIC_VARIABLE_INVALID_RESPONSE:{name}")
        result[key] = {"id": created["id"], "name": name}
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


def ensure_flow(key, candidate, existing, apply):
    name = FLOW_NAMES[key]
    matches = [f for f in existing if isinstance(f, dict) and f.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError(f"DUPLICATE_ADVANCED_FLOW:{name}")

    if not matches:
        if not apply:
            print("DRY-RUN: CREATE Advanced Flow:", name)
            return None
        created = create_flow(candidate)
        if not isinstance(created, dict) or not created.get("id"):
            raise RuntimeError(f"CREATE_ADVANCED_FLOW_INVALID_RESPONSE:{name}")
        flow_id = created["id"]
        time.sleep(WRITE_SPACING_SECONDS)
        live = get_flow(flow_id)
        if writable_flow(live) != candidate:
            raise RuntimeError(f"CREATE_ADVANCED_FLOW_READBACK_MISMATCH:{name}")
        print("created Flow:", name, flow_id)
        return {"id": flow_id, "name": name}

    live = get_flow(matches[0]["id"])
    flow_id = live["id"]
    before = writable_flow(live)
    if before == candidate:
        print("flow MATCH:", name, flow_id)
        return {"id": flow_id, "name": name}

    print("flow DIFF:", name, flow_id)
    print("live hash:", sha(before))
    print("cand hash:", sha(candidate))
    if not apply:
        print("DRY-RUN: write blocked")
        return None

    backup = backup_flow(live, "predeploy")
    update_flow(flow_id, candidate)
    time.sleep(WRITE_SPACING_SECONDS)
    after = get_flow(flow_id)
    if writable_flow(after) != candidate:
        print("readback mismatch; restoring", backup)
        update_flow(flow_id, before)
        raise RuntimeError(f"ADVANCED_FLOW_READBACK_MISMATCH:{name}")
    print("updated Flow:", name, flow_id)
    return {"id": flow_id, "name": name}


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
    raw = jrun("api", "logic", "get-variable", "--id", var_id, "--json")
    value = raw.get("value") if isinstance(raw, dict) else None
    try:
        return json.loads(str(value or ""))
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create/update Homey Logic + Advanced Flows and enable publisher",
    )
    args = parser.parse_args()

    for source in (
        ADAPTER_SOURCE, GATE_SOURCE, PUBLISHER_SOURCE, SERVICE_SOURCE, TIMER_SOURCE
    ):
        if not source.exists():
            raise RuntimeError(f"SOURCE_MISSING:{source}")

    print("mode:", "APPLY" if args.apply else "DRY-RUN")
    print("physical device writes: FORBIDDEN")

    logic = ensure_logic_variables(args.apply)
    if logic is None:
        print("DRY-RUN complete: --apply required to allocate stable Logic IDs")
        return 0

    ids = {key: value["id"] for key, value in logic.items()}
    adapter_src = render(ADAPTER_SOURCE, ids)
    gate_src = render(GATE_SOURCE, ids)

    existing = get_advanced_flows()
    adapter_meta = ensure_flow(
        "adapter", adapter_flow(logic, adapter_src), existing, args.apply
    )
    if args.apply:
        time.sleep(WRITE_SPACING_SECONDS)
        existing = get_advanced_flows()
    gate_meta = ensure_flow(
        "gate", gate_flow(logic, gate_src), existing, args.apply
    )

    if not args.apply:
        print("DRY-RUN complete: no Homey or systemd writes performed")
        return 0

    if not adapter_meta or not gate_meta:
        raise RuntimeError("FLOW_METADATA_MISSING_AFTER_APPLY")

    config = {
        "schema": CONFIG_SCHEMA,
        "commissionedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "SHADOW",
        "deviceWrites": False,
        "physicalWriteAllowed": False,
        "logic": logic,
        "flows": {"adapter": adapter_meta, "gate": gate_meta},
    }
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(CONFIG)

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

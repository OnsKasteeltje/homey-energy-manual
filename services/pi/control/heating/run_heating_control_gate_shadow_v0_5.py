#!/usr/bin/env python3
"""Publish local Heating Control Gate V0.5 SHADOW state."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DATA = Path("/home/jeroen/ems/data")
HEATING_V03_FILE = DATA / "heating-preheat-shadow-v0.3.json"
PROGRESSION_V04_FILE = DATA / "heating-preheat-progression-shadow-v0.4.json"
OUTPUT = DATA / "heating-control-gate-shadow-v0.5.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_optional_json(path: Path):
    if not path.exists():
        return None
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("heating_control_gate_v05", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main() -> int:
    module = load_module(
        REPO / "services/pi/control/heating/build_heating_control_gate_shadow_v0_5.py"
    )
    previous = load_optional_json(OUTPUT)
    now = datetime.now(timezone.utc)
    try:
        out = module.build_gate(
            load_json(HEATING_V03_FILE),
            load_json(PROGRESSION_V04_FILE),
            previous,
            generated_at=now,
        )
        result = "PASS"
    except (OSError, json.JSONDecodeError, module.ControlGateError) as exc:
        reason = f"SOURCE_OR_CONTRACT_ERROR_{type(exc).__name__}"
        out = module.build_fail_closed(previous, reason=reason, generated_at=now)
        result = "PASS_FAIL_CLOSED"
        print(f"WARN: {reason}: {exc}")

    atomic_write(OUTPUT, out)
    print(
        f"{result}: {out['schema']} controlWrites={out['controlWrites']} "
        f"physicalWriteAllowed={out['physicalWriteAllowed']}"
    )
    print("sourceFreshness:", out["sourceFreshness"])
    for room in out["rooms"]:
        cmd = room["command"]
        print(room["key"], cmd["action"], cmd["target_C"], cmd["reason"])
    print("output:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

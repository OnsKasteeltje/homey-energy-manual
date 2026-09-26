#!/usr/bin/env python3
"""Compose the local read-only Heating Preheat V0.3 shadow artifacts.

No network calls and no device writes occur here. The runner consumes already
collected local Honeywell and Quatt artifacts.
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HONEYWELL_DIR = Path("/home/jeroen/ems/runtime/tools/honeywell/output")
SCHEDULE_FILE = HONEYWELL_DIR / "honeywell-schedule.json"
STATE_FILE = HONEYWELL_DIR / "honeywell-state.json"
QUATT_FILE = Path("/home/jeroen/ems/runtime/thermal/quatt-current.json")

DATA_DIR = Path("/home/jeroen/ems/data")
ROOM_MODEL_FILE = DATA_DIR / "heating-room-model.json"
V02_FILE = DATA_DIR / "heating-preheat-plan-v0.2.json"
V03_FILE = DATA_DIR / "heating-preheat-shadow-v0.3.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    room_mod = load_module(
        "heating_room_model",
        REPO / "services/pi/state/heating/build_heating_room_model.py",
    )
    candidate_mod = load_module(
        "heating_preheat_v02",
        REPO / "services/pi/planner/heating/build_heating_preheat_plan.py",
    )
    shadow_mod = load_module(
        "heating_preheat_v03",
        REPO / "services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py",
    )

    now = datetime.now(timezone.utc)
    room_model = room_mod.build_model(
        load_json(SCHEDULE_FILE),
        load_json(STATE_FILE),
        generated_at=now,
    )
    candidate = candidate_mod.build_plan(room_model, generated_at=now)
    shadow = shadow_mod.build_shadow(
        room_model,
        candidate,
        load_json(QUATT_FILE),
        generated_at=now,
    )

    atomic_write(ROOM_MODEL_FILE, room_model)
    atomic_write(V02_FILE, candidate)
    atomic_write(V03_FILE, shadow)

    scoped = [r for r in shadow["rooms"] if r["preheatScope"]]
    states = {r["key"]: r["shadow"]["state"] for r in scoped}
    print(f"PASS: {shadow['schema']} controlWrites={shadow['controlWrites']}")
    print("baselineHeatingDemandPresent:", shadow["house"]["baselineHeatingDemandPresent"])
    print("cvGuard:", shadow["cvGuard"])
    print("scopedStates:", states)
    print("output:", V03_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

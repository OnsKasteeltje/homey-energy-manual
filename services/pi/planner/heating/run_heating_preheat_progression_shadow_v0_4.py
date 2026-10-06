#!/usr/bin/env python3
"""Publish local stateful Heating Preheat V0.4 progression SHADOW."""

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
PLANNER_GRANT_FILE = DATA / "heating-production-grant-v0.1.json"
OUTPUT = DATA / "heating-preheat-progression-shadow-v0.4.json"


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
    spec = importlib.util.spec_from_file_location("heating_preheat_progression_v04", path)
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
        REPO / "services/pi/planner/heating/build_heating_preheat_progression_shadow_v0_4.py"
    )
    previous = load_optional_json(OUTPUT)
    out = module.build_progression(
        load_json(HEATING_V03_FILE),
        load_json(PLANNER_GRANT_FILE),
        previous,
        generated_at=datetime.now(timezone.utc),
    )
    atomic_write(OUTPUT, out)

    print(f"PASS: {out['schema']} controlWrites={out['controlWrites']}")
    print("physicalWriteAllowed:", out["physicalWriteAllowed"])
    print("sourceFreshness:", out["sourceFreshness"])
    for room in out["rooms"]:
        p = room["progression"]
        print(room["key"], {
            "state": p["state"],
            "activeStepTarget_C": p["activeStepTarget_C"],
            "activeStepReached": p["activeStepReached"],
            "nextStepTarget_C": p["nextStepTarget_C"],
            "lastTransition": p["lastTransition"],
        })
    print("output:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

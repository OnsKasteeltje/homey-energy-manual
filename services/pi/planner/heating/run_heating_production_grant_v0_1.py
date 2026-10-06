#!/usr/bin/env python3
"""Build and persist the Pi-local production Heating grant V0.1 artifact.

This runner is intentionally one-shot. It reads only existing local planner /
Heating / Flex / P1 artifacts and performs no network or device call. No timer
or Homey publisher is enabled by this file.
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DATA = Path("/home/jeroen/ems/data")

DYNAMIC_PLAN_FILE = DATA / "dynamic-shadow-plan.json"
HEATING_FILE = DATA / "heating-preheat-shadow-v0.3.json"
FLEX_FILE = DATA / "flex-priority-shadow-v0.1.json"
ENERGY_STATE_FILE = DATA / "energy-state-v2.json"
OUTPUT = DATA / "heating-production-grant-v0.1.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("heating_production_grant_v01", path)
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
    module = load_module(REPO / "services/pi/planner/heating/build_heating_production_grant_v0_1.py")
    out = module.build_heating_grant(
        load_json(DYNAMIC_PLAN_FILE),
        load_json(HEATING_FILE),
        load_json(FLEX_FILE),
        load_json(ENERGY_STATE_FILE),
        generated_at=datetime.now(timezone.utc),
    )
    atomic_write(OUTPUT, out)

    print(f"PASS: {out['schema']}")
    print("grantRevision:", out["grantRevision"])
    print("validUntil:", out["validUntil"])
    print("heating:", out["heating"])
    print("forecastOpportunity:", out["forecastOpportunity"])
    print("realtimePermission:", out["realtimePermission"])
    print("physicalWriteAllowed:", out["physicalWriteAllowed"])
    print("output:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

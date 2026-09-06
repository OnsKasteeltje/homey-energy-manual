#!/usr/bin/env python3

import json
import os
import subprocess
import time
from pathlib import Path

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"

# EM2_PLANNER_INPUT_V0.1
VARIABLE_ID = "39c7c169-34d7-4e14-a27b-520aca255032"

OUTPUT = Path("/home/jeroen/ems/data/ww-input.json")
MAX_STALE_SECONDS = 2 * 60 * 60

env = os.environ.copy()
env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")

cmd = [
    str(HOMEY_CLI),
    "api", "logic", "get-variable",
    "--id", VARIABLE_ID,
    "--json",
]

r = subprocess.run(
    cmd,
    cwd=HOMEY_PROJECT,
    env=env,
    text=True,
    capture_output=True,
)

if r.returncode != 0:
    msg = (r.stderr or r.stdout).strip()
    is_rate_limit = "429" in msg or "too many requests" in msg.lower()

    if is_rate_limit:
        if OUTPUT.exists():
            age_seconds = time.time() - OUTPUT.stat().st_mtime
            if age_seconds <= MAX_STALE_SECONDS:
                print(
                    "WARN: Homey rate limit; reusing last WW input "
                    f"(age={age_seconds / 60:.0f} min)"
                )
                raise SystemExit(0)

        raise SystemExit(
            "FAIL: Homey rate limit and no WW input newer than 2 hours"
        )

    raise SystemExit(f"FAIL: Homey read: {msg[:300]}")

variable = json.loads(r.stdout)
planner_input = json.loads(variable.get("value") or "{}")

if planner_input.get("schema") != "EM2_PLANNER_INPUT_V0.1":
    raise SystemExit("FAIL: unexpected planner input schema")

ww = planner_input.get("warmWater")

if not isinstance(ww, dict):
    raise SystemExit("FAIL: warmWater input missing")

payload = {
    "schema": "EMS_PI_WW_INPUT_V0.1",
    "mode": "shadow",
    "control_writes": False,
    "source": "EM2_PLANNER_INPUT_V0.1",
    "warmWater": ww,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
tmp.replace(OUTPUT)

print("PASS: WW planner input fetched")
print("goalReachedToday    :", ww.get("goalReachedToday"))
print("goalReached         :", ww.get("goalReached"))
print("remainingFallbackMin:", ww.get("remainingFallbackMin"))
print("catchupRequired     :", ww.get("catchupRequired"))
print("output              :", OUTPUT)

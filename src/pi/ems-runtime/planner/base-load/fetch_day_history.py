#!/usr/bin/env python3

import json
import os
import subprocess
from pathlib import Path

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"
VARIABLE_ID = "254f15cd-b060-4b42-801d-5e4f58efa069"

OUTPUT = Path("/home/jeroen/ems/data/homey-day-history.json")

env = os.environ.copy()
env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")

cmd = [
    str(HOMEY_CLI),
    "api", "logic", "get-variable",
    "--id", VARIABLE_ID,
    "--json",
]

result = subprocess.run(
    cmd,
    cwd=HOMEY_PROJECT,
    env=env,
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    msg = (result.stderr or result.stdout).strip()
    if "429" in msg:
        raise SystemExit("FAIL: Homey rate limit (429); stopped")
    raise SystemExit(f"FAIL: Homey read: {msg[:300]}")

variable = json.loads(result.stdout)

if variable.get("id") != VARIABLE_ID:
    raise SystemExit("FAIL: unexpected Homey variable")

history = json.loads(variable.get("value") or "{}")

if not isinstance(history.get("samples"), list):
    raise SystemExit("FAIL: invalid EM2_Day_History")

payload = {
    "schema": "EMS_PI_DAY_HISTORY_V0.1",
    "source": "EM2_Day_History",
    "source_schema": history.get("schema_version"),
    "date_local": history.get("date_local"),
    "sample_interval_minutes": history.get("sample_interval_minutes"),
    "sample_count": len(history["samples"]),
    "samples": history["samples"],
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
tmp.replace(OUTPUT)

print("PASS: EM2_Day_History fetched")
print("date       :", payload["date_local"])
print("samples    :", payload["sample_count"])
print("source     :", payload["source"])
print("output     :", OUTPUT)

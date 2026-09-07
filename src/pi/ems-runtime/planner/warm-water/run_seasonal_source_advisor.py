#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"
ADVISOR = Path("/home/jeroen/ems/runtime/planner/warm-water/seasonal_source_advisor.py")
MODE_VARIABLE_NAME = "WW_Boilermodus"


def run_homey(args):
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")
    r = subprocess.run(
        [str(HOMEY_CLI)] + args,
        cwd=HOMEY_PROJECT,
        env=env,
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        raise RuntimeError(msg[:800])
    return r.stdout


def current_mode():
    raw = run_homey(["api", "logic", "get-variables", "--json"])
    variables = json.loads(raw)
    if isinstance(variables, dict):
        variables = list(variables.values())

    match = next((v for v in variables if v.get("name") == MODE_VARIABLE_NAME), None)
    if not match:
        raise RuntimeError(f"Homey logic variable {MODE_VARIABLE_NAME!r} not found")

    value = match.get("value")
    if isinstance(value, bool):
        return "BOILER" if value else "CV"

    normalized = str(value).strip().lower()
    if normalized in {"ja", "yes", "true", "1", "boiler", "aan", "on"}:
        return "BOILER"
    if normalized in {"nee", "no", "false", "0", "cv", "uit", "off"}:
        return "CV"

    raise RuntimeError(f"Unsupported {MODE_VARIABLE_NAME} value: {value!r}")


def main():
    try:
        mode = current_mode()
    except Exception as exc:
        print(f"FAIL: cannot resolve current WW mode from Homey: {exc}", file=sys.stderr)
        return 2

    print(f"WW current mode: {mode}")
    result = subprocess.run([
        "/usr/bin/python3",
        str(ADVISOR),
        "--mode",
        mode,
    ])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch the EV deadline command from GitHub main into Pi runtime storage.

GitHub main is the durable command source during this migration phase. This
consumer performs no Homey calls and no device/control writes. A failed or
invalid fetch never replaces the last valid runtime command.
"""

import json
import math
import os
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

URL = os.environ.get(
    "EMS_EV_DEADLINE_COMMAND_URL",
    "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/tesla-deadline-command.json",
)
RUNTIME_FILE = Path(os.environ.get(
    "EMS_EV_DEADLINE_COMMAND_FILE",
    "/home/jeroen/ems/data/tesla-deadline-command.json",
))
TZ = ZoneInfo("Europe/Amsterdam")


def finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def validate(command):
    if not isinstance(command, dict) or command.get("schema") != 2:
        raise ValueError("SCHEMA_INVALID")
    request_id = command.get("requestId")
    requested_at = command.get("requestedAt")
    active = command.get("active")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("REQUEST_ID_INVALID")
    try:
        requested = datetime.fromisoformat(str(requested_at).replace("Z", "+00:00"))
        if requested.tzinfo is None:
            raise ValueError
    except Exception as exc:
        raise ValueError("REQUESTED_AT_INVALID") from exc
    if not isinstance(active, bool):
        raise ValueError("ACTIVE_INVALID")

    if active:
        deadline = command.get("deadline")
        try:
            parsed = datetime.fromisoformat(str(deadline))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=TZ)
        except Exception as exc:
            raise ValueError("DEADLINE_INVALID") from exc
        current_soc = finite_number(command.get("currentSoc"))
        target_soc = finite_number(command.get("targetSoc"))
        goal_kwh = finite_number(command.get("goalKWh"))
        max_a = finite_number(command.get("maxA"))
        calibration = finite_number(command.get("calibrationKWhPerPercent"))
        if current_soc is None or not 0 <= current_soc <= 100:
            raise ValueError("CURRENT_SOC_INVALID")
        if target_soc is None or not 1 <= target_soc <= 100 or target_soc <= current_soc:
            raise ValueError("TARGET_SOC_INVALID")
        if goal_kwh is None or goal_kwh <= 0:
            raise ValueError("GOAL_KWH_INVALID")
        if max_a is None or not 6 <= max_a <= 16:
            raise ValueError("MAX_A_INVALID")
        if calibration is None or calibration <= 0:
            raise ValueError("CALIBRATION_INVALID")
    return command


def fetch(url=URL, opener=urllib.request.urlopen):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ems-pi-ev-deadline-command/1.0", "Cache-Control": "no-cache"},
    )
    with opener(request, timeout=10) as response:
        return validate(json.loads(response.read().decode("utf-8")))


def atomic_write(path, command):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(command, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def sync(runtime_file=RUNTIME_FILE):
    command = fetch()
    previous = {}
    try:
        previous = json.loads(runtime_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    if previous.get("requestId") == command.get("requestId"):
        return "UNCHANGED", command
    atomic_write(runtime_file, command)
    return "UPDATED", command


def main():
    status, command = sync()
    print(json.dumps({"ok": True, "status": status, "requestId": command.get("requestId")}))


if __name__ == "__main__":
    main()

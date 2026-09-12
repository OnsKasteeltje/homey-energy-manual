#!/usr/bin/env python3

"""Read-only Honeywell/Resideo collector producing normalized EMS state.

Reads the explicit Homey <-> Honeywell zone map and writes only a local JSON
artifact. No Honeywell write API, Homey write, SQLite write, or OpenTherm action.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evohomeasync2 import EvohomeClientOld, InvalidScheduleError

ROOT = Path(__file__).resolve().parent
ACCOUNT_ENV = ROOT / "config" / "account.env"
ZONE_MAP = ROOT / "config" / "zone-map.json"
OUTPUT = ROOT / "output" / "honeywell-state.json"


def load_credentials(path: Path) -> tuple[str, str]:
    """Load the chmod-600 account.env using Bash's own assignment parser.

    account.env is intentionally written with shell-safe escaping (printf %q).
    Parsing it as plain text would preserve escape backslashes and corrupt some
    passwords, so decode it exactly as Bash would while returning only the two
    required values via NUL-delimited stdout.
    """
    if not path.exists():
        raise SystemExit(f"ERROR: missing credential file: {path}")

    script = (
        'set -a; source "$1"; '
        'printf "%s\\0%s\\0" "$HONEYWELL_USERNAME" "$HONEYWELL_PASSWORD"'
    )
    result = subprocess.run(
        ["/bin/bash", "-c", script, "bash", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    parts = result.stdout.split(b"\0")
    if len(parts) < 3:
        raise SystemExit("ERROR: credential file did not yield username/password")

    username = parts[0].decode().strip()
    password = parts[1].decode()
    if not username or not password:
        raise SystemExit("ERROR: HONEYWELL_USERNAME/PASSWORD not configured")
    return username, password


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return str(value)


def switchpoint(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    when, target = value
    return {
        "time": jsonable(when),
        "targetTemperature_C": jsonable(target),
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


async def main() -> None:
    username, password = load_credentials(ACCOUNT_ENV)

    mapping = json.loads(ZONE_MAP.read_text())
    expected_location = str(mapping["location"]["honeywellLocationId"])
    expected_system = str(mapping["location"]["honeywellSystemId"])
    zone_map = {str(z["honeywellZoneId"]): z for z in mapping["zones"]}

    if len(zone_map) != len(mapping["zones"]):
        raise SystemExit("ERROR: duplicate honeywellZoneId in zone-map.json")

    found: dict[str, dict[str, Any]] = {}
    system_mode = None

    async with EvohomeClientOld(username, password) as evo:
        await evo.update()
        for location in evo.locations:
            if str(location.id) != expected_location:
                continue
            for gateway in location.gateways:
                for system in gateway.systems:
                    if str(system.id) != expected_system:
                        continue
                    system_mode = jsonable(getattr(system, "mode", None))
                    for zone in system.zones:
                        zid = str(zone.id)
                        if zid not in zone_map:
                            continue

                        schedule_status = "OK"
                        current = None
                        nxt = None
                        try:
                            await zone.get_schedule()
                            current = zone.this_switchpoint
                            nxt = zone.next_switchpoint
                        except InvalidScheduleError:
                            schedule_status = "INVALID_OR_UNAVAILABLE"

                        m = zone_map[zid]
                        found[zid] = {
                            "key": m["key"],
                            "displayName": m["homeyName"],
                            "homeyDeviceId": m["homeyDeviceId"],
                            "honeywellZoneId": zid,
                            "sourceName": jsonable(zone.name),
                            "roomTemperature_C": jsonable(zone.temperature),
                            "targetTemperature_C": jsonable(zone.target_heat_temperature),
                            "setpointMode": jsonable(zone.mode),
                            "scheduleStatus": schedule_status,
                            "currentSwitchpoint": switchpoint(current),
                            "nextSwitchpoint": switchpoint(nxt),
                        }

    missing = [zid for zid in zone_map if zid not in found]
    if missing:
        raise SystemExit("ERROR: mapped Honeywell zones not returned: " + ", ".join(missing))

    zones = [found[str(m["honeywellZoneId"])] for m in mapping["zones"]]
    payload = {
        "schema": "EMS_HONEYWELL_STATE_V0.1",
        "mode": "READ_ONLY",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "RESIDEO_EVOHOME_CLOUD",
        "location": {
            "displayName": mapping["location"]["name"],
            "honeywellLocationId": expected_location,
            "honeywellSystemId": expected_system,
            "systemMode": system_mode,
        },
        "zoneCount": len(zones),
        "zones": zones,
    }

    atomic_write_json(OUTPUT, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

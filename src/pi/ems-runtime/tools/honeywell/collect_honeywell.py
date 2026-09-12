#!/usr/bin/env python3

"""Read-only Honeywell/Resideo collector producing normalized EMS state.

Reads the explicit Homey <-> Honeywell zone map and writes only a local JSON
artifact. No Honeywell write API, Homey write, SQLite write, or OpenTherm action.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evohomeasync2 import EvohomeClientOld, InvalidScheduleError

ROOT = Path(__file__).resolve().parent
ACCOUNT_ENV = ROOT / "config" / "account.env"
ZONE_MAP = ROOT / "config" / "zone-map.json"
OUTPUT = ROOT / "output" / "honeywell-state.json"


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"ERROR: missing credential file: {path}")
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
    load_env_file(ACCOUNT_ENV)
    username = os.environ.get("HONEYWELL_USERNAME", "").strip()
    password = os.environ.get("HONEYWELL_PASSWORD", "").strip()
    if not username or not password:
        raise SystemExit("ERROR: HONEYWELL_USERNAME/PASSWORD not configured")

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

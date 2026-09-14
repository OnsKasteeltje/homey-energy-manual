#!/usr/bin/env python3

"""Read-only Honeywell/Resideo Evohome probe.

No write API is called. The probe is intentionally diagnostic only.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from evohomeasync2 import EvohomeClientOld, InvalidScheduleError

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_ENV = ROOT / "config" / "account.env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"ERROR: missing credential file: {path}")

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return str(value)


async def main() -> None:
    load_env_file(ACCOUNT_ENV)

    username = os.environ.get("HONEYWELL_USERNAME", "").strip()
    password = os.environ.get("HONEYWELL_PASSWORD", "").strip()
    if not username or not password:
        raise SystemExit("ERROR: HONEYWELL_USERNAME/PASSWORD not configured")

    output: dict[str, Any] = {
        "schema": "EMS_HONEYWELL_PROBE_V0.1",
        "mode": "READ_ONLY",
        "locations": [],
    }

    async with EvohomeClientOld(username, password) as evo:
        await evo.update()

        for loc_idx, location in enumerate(evo.locations):
            location_out: dict[str, Any] = {
                "index": loc_idx,
                "id": jsonable(location.id),
                "name": jsonable(getattr(location, "name", None)),
                "systems": [],
            }

            for gateway in location.gateways:
                for system in gateway.systems:
                    system_out: dict[str, Any] = {
                        "id": jsonable(system.id),
                        "mode": jsonable(getattr(system, "mode", None)),
                        "zones": [],
                    }

                    for zone in system.zones:
                        schedule_status = "OK"
                        this_switchpoint = None
                        next_switchpoint = None

                        try:
                            await zone.get_schedule()
                            this_switchpoint = zone.this_switchpoint
                            next_switchpoint = zone.next_switchpoint
                        except InvalidScheduleError:
                            schedule_status = "INVALID_OR_UNAVAILABLE"

                        zone_out = {
                            "id": jsonable(zone.id),
                            "name": jsonable(zone.name),
                            "roomTemperature_C": jsonable(zone.temperature),
                            "targetTemperature_C": jsonable(
                                zone.target_heat_temperature
                            ),
                            "setpointMode": jsonable(zone.mode),
                            "scheduleStatus": schedule_status,
                            "currentSwitchpoint": (
                                [jsonable(v) for v in this_switchpoint]
                                if this_switchpoint is not None
                                else None
                            ),
                            "nextSwitchpoint": (
                                [jsonable(v) for v in next_switchpoint]
                                if next_switchpoint is not None
                                else None
                            ),
                        }
                        system_out["zones"].append(zone_out)

                    location_out["systems"].append(system_out)

            output["locations"].append(location_out)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

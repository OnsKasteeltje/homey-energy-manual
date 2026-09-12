#!/usr/bin/env python3

"""Read-only Honeywell/Resideo schedule collector.

Intended future cadence: every 6 hours, plus an explicit on-demand refresh when
needed. Fetches schedules separately from the 5-minute state poller.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from evohomeasync2 import InvalidScheduleError

from honeywell_common import (
    ROOT,
    atomic_write_json,
    create_client,
    jsonable,
    load_mapping,
    save_token_cache,
    switchpoint,
)

OUTPUT = ROOT / "output" / "honeywell-schedule.json"


async def main() -> None:
    mapping = load_mapping()
    expected_location = str(mapping["location"]["honeywellLocationId"])
    expected_system = str(mapping["location"]["honeywellSystemId"])
    zone_map = {str(z["honeywellZoneId"]): z for z in mapping["zones"]}

    found: dict[str, dict] = {}

    evo, cache_loaded, cache_valid = create_client()
    async with evo:
        await evo.update()
        save_token_cache(evo)

        for location in evo.locations:
            if str(location.id) != expected_location:
                continue
            for gateway in location.gateways:
                for system in gateway.systems:
                    if str(system.id) != expected_system:
                        continue
                    for zone in system.zones:
                        zid = str(zone.id)
                        if zid not in zone_map:
                            continue

                        status = "OK"
                        current = None
                        nxt = None
                        try:
                            await zone.get_schedule()
                            current = zone.this_switchpoint
                            nxt = zone.next_switchpoint
                        except InvalidScheduleError:
                            status = "INVALID_OR_UNAVAILABLE"

                        m = zone_map[zid]
                        found[zid] = {
                            "key": m["key"],
                            "displayName": m["homeyName"],
                            "homeyDeviceId": m["homeyDeviceId"],
                            "honeywellZoneId": zid,
                            "sourceName": jsonable(zone.name),
                            "scheduleStatus": status,
                            "currentSwitchpoint": switchpoint(current),
                            "nextSwitchpoint": switchpoint(nxt),
                        }

    missing = [zid for zid in zone_map if zid not in found]
    if missing:
        raise SystemExit("ERROR: mapped Honeywell zones not returned: " + ", ".join(missing))

    zones = [found[str(m["honeywellZoneId"])] for m in mapping["zones"]]
    payload = {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.1",
        "mode": "READ_ONLY",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "RESIDEO_EVOHOME_CLOUD",
        "pollClass": "SCHEDULE",
        "auth": {
            "tokenCacheLoaded": cache_loaded,
            "cachedAccessTokenValidAtStart": cache_valid,
            "accessTokenExpires": evo.access_token_expires.isoformat(),
        },
        "location": {
            "displayName": mapping["location"]["name"],
            "honeywellLocationId": expected_location,
            "honeywellSystemId": expected_system,
        },
        "zoneCount": len(zones),
        "zones": zones,
    }

    atomic_write_json(OUTPUT, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

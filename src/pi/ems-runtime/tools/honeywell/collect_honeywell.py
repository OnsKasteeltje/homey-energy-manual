#!/usr/bin/env python3

"""Read-only Honeywell/Resideo state collector.

Intended future cadence: every 5 minutes. It deliberately does not fetch per-zone
schedules; those are collected separately at low frequency.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from honeywell_common import (
    ROOT,
    atomic_write_json,
    create_client,
    jsonable,
    load_mapping,
    save_token_cache,
)

OUTPUT = ROOT / "output" / "honeywell-state.json"


async def main() -> None:
    mapping = load_mapping()
    expected_location = str(mapping["location"]["honeywellLocationId"])
    expected_system = str(mapping["location"]["honeywellSystemId"])
    zone_map = {str(z["honeywellZoneId"]): z for z in mapping["zones"]}

    found: dict[str, dict] = {}
    system_mode = None

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
                    system_mode = jsonable(getattr(system, "mode", None))
                    for zone in system.zones:
                        zid = str(zone.id)
                        if zid not in zone_map:
                            continue
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
                        }

    missing = [zid for zid in zone_map if zid not in found]
    if missing:
        raise SystemExit("ERROR: mapped Honeywell zones not returned: " + ", ".join(missing))

    zones = [found[str(m["honeywellZoneId"])] for m in mapping["zones"]]
    payload = {
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "mode": "READ_ONLY",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "RESIDEO_EVOHOME_CLOUD",
        "pollClass": "STATE",
        "auth": {
            "tokenCacheLoaded": cache_loaded,
            "cachedAccessTokenValidAtStart": cache_valid,
            "accessTokenExpires": evo.access_token_expires.isoformat(),
        },
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

#!/usr/bin/env python3

import json
import urllib.parse
import urllib.request
from pathlib import Path

INPUT = Path("/home/jeroen/ems/data/weather-forecast.json")

LAT = 52.70808
LON = 5.10003


def fetch_gti(azimuth, tilt):
    params = {
        "latitude": LAT,
        "longitude": LON,
        "minutely_15": "global_tilted_irradiance",
        "past_minutely_15": 4,
        "forecast_minutely_15": 104,
        "timezone": "UTC",
        "tilt": tilt,
        "azimuth": azimuth,
    }

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode(params)
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EMS-Pi-GTI/0.1"},
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)

    q = data.get("minutely_15", {})
    times = q.get("time", [])
    values = q.get("global_tilted_irradiance", [])

    result = {}

    for t, value in zip(times, values):
        # Open-Meteo returns e.g. 2026-09-05T18:15
        # Our forecast uses 2026-09-05T18:15:00Z
        key = t
        if len(key) == 16:
            key += ":00"
        key += "Z"
        result[key] = value

    return result


def main():
    payload = json.loads(INPUT.read_text())
    slots = payload.get("slots")

    if not isinstance(slots, list):
        raise RuntimeError("Invalid weather-forecast.json")

    # Open-Meteo azimuth convention:
    # 0 = south, -90 = east, +90 = west
    #
    # ZO = -135 degrees
    # ZW = +135 degrees

    gti_goodwe2000 = fetch_gti(-135, 30)
    gti_goodwe4200 = fetch_gti(135, 30)
    gti_solaredge = fetch_gti(135, 25)

    missing = []

    for slot in slots:
        start = slot["start"]

        slot["gti_goodwe2000_zo30_w_m2"] = gti_goodwe2000.get(start)
        slot["gti_goodwe4200_zw30_w_m2"] = gti_goodwe4200.get(start)
        slot["gti_solaredge_zw25_w_m2"] = gti_solaredge.get(start)

        if (
            slot["gti_goodwe2000_zo30_w_m2"] is None
            or slot["gti_goodwe4200_zw30_w_m2"] is None
            or slot["gti_solaredge_zw25_w_m2"] is None
        ):
            missing.append(start)

    if missing:
        raise RuntimeError(
            f"Missing GTI values for {len(missing)} slots; "
            f"first={missing[0]}"
        )

    tmp = INPUT.with_suffix(".gti.tmp")
    tmp.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    tmp.replace(INPUT)

    print(f"PASS: GTI added to {len(slots)} weather slots")
    print("GoodWe 2000 : ZO / 30°")
    print("GoodWe 4200 : ZW / 30°")
    print("SolarEdge   : ZW / 25°")


if __name__ == "__main__":
    main()

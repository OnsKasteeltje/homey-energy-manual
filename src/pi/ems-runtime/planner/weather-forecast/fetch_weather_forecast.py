#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

FORECAST_LIB_DIR = Path("/home/jeroen/ems/runtime/forecast")
if str(FORECAST_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(FORECAST_LIB_DIR))

from open_meteo_cache import load_snapshot

LAT = 52.70808
LON = 5.10003

STEP_SECONDS = 15 * 60
MAX_SLOTS = 96

OUTPUT = Path("/home/jeroen/ems/data/weather-forecast.json")
AXIS = Path("/home/jeroen/ems/data/planner-axis.json")

def gti_by_timestamp(data):
    q = data.get("minutely_15", {})
    times = q.get("time", [])
    values = q.get("global_tilted_irradiance", [])
    result = {}
    for t, value in zip(times, values):
        key = t + (":00" if len(t) == 16 else "") + "Z"
        result[key] = value
    return result


def main():
    snapshot = load_snapshot()
    data = snapshot["sources"]["weather"]

    q = data.get("minutely_15", {})
    times = q.get("time", [])

    fields = {
        "temperature_2m_c": q.get("temperature_2m", []),
        "apparent_temperature_c": q.get("apparent_temperature", []),
        "cloud_cover_pct": q.get("cloud_cover", []),
        "wind_speed_10m_kmh": q.get("wind_speed_10m", []),
        "wind_direction_10m_deg": q.get("wind_direction_10m", []),
        "shortwave_radiation_w_m2": q.get("shortwave_radiation", []),
        "direct_radiation_w_m2": q.get("direct_radiation", []),
        "diffuse_radiation_w_m2": q.get("diffuse_radiation", []),
        "direct_normal_irradiance_w_m2": q.get(
            "direct_normal_irradiance", []
        ),
        "shortwave_radiation_clear_sky_w_m2": q.get(
            "shortwave_radiation_clear_sky", []
        ),
        "sunshine_duration_s": q.get("sunshine_duration", []),
    }

    # PV geometry:
    #
    # GoodWe 2000: ZO, 30°
    # GoodWe 4200: ZW, 30°
    # SolarEdge:   ZW, 25°
    #
    # Open-Meteo azimuth convention:
    # 0° = south
    # -90° = east
    # +90° = west
    #
    # Therefore:
    # ZO = -135°
    # ZW = +135°

    gti_goodwe2000 = gti_by_timestamp(snapshot["sources"]["gti_goodwe2000"])
    gti_goodwe4200 = gti_by_timestamp(snapshot["sources"]["gti_goodwe4200"])
    gti_solaredge = gti_by_timestamp(snapshot["sources"]["gti_solaredge"])

    with AXIS.open() as f:
        axis = json.load(f)

    axis_slots = axis.get("slots", [])
    if len(axis_slots) != MAX_SLOTS:
        raise RuntimeError(
            f"Invalid planner axis: expected {MAX_SLOTS} slots, got {len(axis_slots)}"
        )

    axis_set = set(axis_slots)

    slots = []

    for i, t in enumerate(times):
        try:
            dt = datetime.fromisoformat(t).replace(
                tzinfo=timezone.utc
            )
        except Exception:
            continue

        start = dt.isoformat().replace("+00:00", "Z")
        if start not in axis_set:
            continue

        slot = {
            "start": start
        }

        valid = True

        for name, values in fields.items():
            if i >= len(values):
                valid = False
                break

            slot[name] = values[i]

        if not valid:
            continue

        start = slot["start"]

        slot["gti_goodwe2000_zo30_w_m2"] = gti_goodwe2000.get(start)
        slot["gti_goodwe4200_zw30_w_m2"] = gti_goodwe4200.get(start)
        slot["gti_solaredge_zw25_w_m2"] = gti_solaredge.get(start)

        if (
            slot["gti_goodwe2000_zo30_w_m2"] is None
            or slot["gti_goodwe4200_zw30_w_m2"] is None
            or slot["gti_solaredge_zw25_w_m2"] is None
        ):
            raise RuntimeError(
                f"Missing GTI for forecast slot {start}"
            )

        slots.append(slot)

        if len(slots) >= MAX_SLOTS:
            break

    if len(slots) != MAX_SLOTS:
        raise RuntimeError(
            f"Expected {MAX_SLOTS} slots, got {len(slots)}"
        )

    output = {
        "schema": "EMS_PI_WEATHER_FORECAST_V0.2",
        "sourceFetchedAt": snapshot["fetchedAt"],
        "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "mode": "shadow",
        "control_writes": False,
        "location": {
            "name": "Hauwert",
            "latitude": LAT,
            "longitude": LON,
        },
        "pv_geometry": {
            "goodwe2000": {
                "azimuth": -135,
                "orientation": "ZO",
                "tilt_deg": 30,
            },
            "goodwe4200": {
                "azimuth": 135,
                "orientation": "ZW",
                "tilt_deg": 30,
            },
            "solaredge": {
                "azimuth": 135,
                "orientation": "ZW",
                "tilt_deg": 25,
            },
        },
        "slot_count": len(slots),
        "slots": slots,
    }

    tmp = OUTPUT.with_suffix(".json.tmp")

    tmp.write_text(
        json.dumps(output, separators=(",", ":")),
        encoding="utf-8",
    )

    tmp.replace(OUTPUT)

    print(f"PASS: wrote {len(slots)} slots to {OUTPUT}")
    print("GTI: GoodWe 2000 = ZO / 30°")
    print("GTI: GoodWe 4200 = ZW / 30°")
    print("GTI: SolarEdge   = ZW / 25°")


if __name__ == "__main__":
    main()

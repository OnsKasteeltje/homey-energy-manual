#!/usr/bin/env python3

import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

DB = "/home/jeroen/ems/data/ems-history.sqlite"
WEATHER = "/home/jeroen/ems/data/weather-forecast.json"
OUTPUT = "/home/jeroen/ems/data/quatt-forecast.json"

TRAIN_START = "2026-01-01T00:00:00Z"
TRAIN_END   = "2026-04-01T00:00:00Z"

# Alleen voldoende gevulde historische bins gebruiken.
MIN_SAMPLES_PER_BIN = 4

# Boven dit punt is onze winterdataset te dun.
MAX_TRAIN_TEMP_C = 15.0


def load_training_data():
    con = sqlite3.connect(DB)

    rows = con.execute("""
    WITH p AS (
        SELECT ts_utc, value_real AS power_w
        FROM measurements x
        JOIN metrics m ON m.id=x.metric_id
        JOIN devices d ON d.id=x.device_id
        WHERE d.device_key='quatt_cic'
          AND m.metric_key='electrical_power_w'
          AND x.source_resolution_seconds=21600
          AND ts_utc >= ?
          AND ts_utc < ?
    ),
    t AS (
        SELECT ts_utc, value_real AS temp_c
        FROM measurements x
        JOIN metrics m ON m.id=x.metric_id
        JOIN devices d ON d.id=x.device_id
        WHERE d.device_key='quatt_cic'
          AND m.metric_key='outside_temperature_c'
          AND x.source_resolution_seconds=21600
          AND ts_utc >= ?
          AND ts_utc < ?
    )
    SELECT t.temp_c, p.power_w
    FROM p
    JOIN t USING(ts_utc)
    """, (TRAIN_START, TRAIN_END, TRAIN_START, TRAIN_END)).fetchall()

    con.close()
    return rows


def build_raw_bins(rows):
    bins = defaultdict(list)

    for temp, power in rows:
        if temp is None or power is None:
            continue
        if temp > MAX_TRAIN_TEMP_C:
            continue

        degree = math.floor(temp)
        bins[degree].append(float(power))

    result = []

    for degree in sorted(bins):
        vals = bins[degree]

        if len(vals) < MIN_SAMPLES_PER_BIN:
            continue

        result.append({
            "temp_c": degree + 0.5,
            "samples": len(vals),
            "power_w": sum(vals) / len(vals),
        })

    return result


def monotone_decreasing_pava(points):
    """
    Weighted isotonic regression.
    Zorgt ervoor dat voorspeld vermogen niet stijgt
    wanneer buitentemperatuur stijgt.
    """
    blocks = []

    for p in points:
        blocks.append({
            "start_temp": p["temp_c"],
            "end_temp": p["temp_c"],
            "weight": p["samples"],
            "value": p["power_w"],
            "members": [p],
        })

        # Voor dalende curve geldt vorige >= volgende.
        while len(blocks) >= 2 and blocks[-2]["value"] < blocks[-1]["value"]:
            b = blocks.pop()
            a = blocks.pop()

            weight = a["weight"] + b["weight"]
            value = (
                a["value"] * a["weight"]
                + b["value"] * b["weight"]
            ) / weight

            blocks.append({
                "start_temp": a["start_temp"],
                "end_temp": b["end_temp"],
                "weight": weight,
                "value": value,
                "members": a["members"] + b["members"],
            })

    result = []

    for block in blocks:
        for member in block["members"]:
            result.append({
                "temp_c": member["temp_c"],
                "samples": member["samples"],
                "power_w": block["value"],
            })

    return result


def heating_season_active(slot_start_utc):
    """
    Forecast-only heating-demand gate v0.2.

    Heating season:
      October through April -> heating forecast allowed
      May through September -> heating forecast = 0 W

    This NEVER controls Quatt.
    """
    from datetime import datetime

    ts = str(slot_start_utc).replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)

    return dt.month >= 10 or dt.month <= 4


def interpolate(curve, temp_c):
    if temp_c <= curve[0]["temp_c"]:
        return curve[0]["power_w"]

    if temp_c >= curve[-1]["temp_c"]:
        # Boven de betrouwbare wintercurve bouwen we de
        # voorspelde verwarmingslast af naar nul bij 18 C.
        warm_edge_c = curve[-1]["temp_c"]
        warm_edge_w = curve[-1]["power_w"]
        zero_heat_c = 18.0

        if temp_c >= zero_heat_c:
            return 0.0

        fraction = (temp_c - warm_edge_c) / (zero_heat_c - warm_edge_c)
        return warm_edge_w * (1.0 - fraction)

    for a, b in zip(curve, curve[1:]):
        if a["temp_c"] <= temp_c <= b["temp_c"]:
            span = b["temp_c"] - a["temp_c"]
            fraction = (temp_c - a["temp_c"]) / span

            return (
                a["power_w"]
                + fraction * (b["power_w"] - a["power_w"])
            )

    raise RuntimeError("Interpolation failed")


def load_weather():
    with open(WEATHER) as f:
        return json.load(f)


def extract_slots(payload):
    slots = payload.get("slots")
    if not isinstance(slots, list):
        raise RuntimeError("weather-forecast.json has no slots array")
    return slots


def extract_temp(slot):
    for key in (
        "temperature_2m",
        "temperature_2m_c",
        "temperature_c",
        "outside_temperature_c",
        "temp_c",
    ):
        if key in slot and slot[key] is not None:
            return float(slot[key])

    raise RuntimeError(
        "No temperature field found in weather slot; keys="
        + ",".join(slot.keys())
    )


def extract_timestamp(slot):
    for key in (
        "start",
        "start_utc",
        "slot_start_utc",
        "timestamp",
        "time",
        "ts",
    ):
        if key in slot:
            return slot[key]

    raise RuntimeError(
        "No timestamp field found in weather slot; keys="
        + ",".join(slot.keys())
    )


def main():
    training = load_training_data()

    if not training:
        raise RuntimeError("No Quatt training data found")

    raw_curve = build_raw_bins(training)

    if len(raw_curve) < 5:
        raise RuntimeError(
            f"Too few usable temperature bins: {len(raw_curve)}"
        )

    curve = monotone_decreasing_pava(raw_curve)

    weather = load_weather()
    weather_slots = extract_slots(weather)

    forecast_slots = []

    for slot in weather_slots:
        temp_c = extract_temp(slot)
        ts = extract_timestamp(slot)

        heating_active = heating_season_active(ts)

        if heating_active:
            power_w = max(0.0, interpolate(curve, temp_c))
        else:
            power_w = 0.0

        forecast_slots.append({
            "slot_start_utc": ts,
            "outside_temperature_c": round(temp_c, 2),
            "heatingDemandGate": bool(heating_active),
            "quattForecastW": round(power_w),
        })

    output = {
        "schema": "EMS_PI_QUATT_FORECAST_V0.2",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "shadow",
        "control_writes": False,
        "model": {
            "type": "historical_temperature_curve_monotone_v0.2_heating_season_gate",
            "training_start": TRAIN_START,
            "training_end": TRAIN_END,
            "training_samples": len(training),
            "minimum_samples_per_degree_bin": MIN_SAMPLES_PER_BIN,
            "daypart_correction": False,
            "source_resolution_seconds": 21600,
        },
        "curve": [
            {
                "temperature_c": round(p["temp_c"], 1),
                "samples": p["samples"],
                "quatt_power_w": round(p["power_w"]),
            }
            for p in curve
        ],
        "slot_count": len(forecast_slots),
        "slots": forecast_slots,
    }

    tmp = OUTPUT + ".tmp"

    with open(tmp, "w") as f:
        json.dump(output, f, indent=2)

    os.replace(tmp, OUTPUT)

    print("PASS: Quatt forecast built")
    print("training samples :", len(training))
    print("curve points     :", len(curve))
    print("forecast slots   :", len(forecast_slots))
    print("curve range      :",
          round(curve[0]["temp_c"], 1), "C ->",
          round(curve[0]["power_w"]), "W ;",
          round(curve[-1]["temp_c"], 1), "C ->",
          round(curve[-1]["power_w"]), "W")

    print("\nfirst 4 forecast slots:")
    for slot in forecast_slots[:4]:
        print(slot)


if __name__ == "__main__":
    main()

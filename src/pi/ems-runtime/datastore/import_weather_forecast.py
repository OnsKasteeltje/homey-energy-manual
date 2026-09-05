#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
INPUT = Path("/home/jeroen/ems/data/weather-forecast.json")


def main():
    payload = json.loads(INPUT.read_text())

    generated_at = payload.get("generated_at")
    slots = payload.get("slots")

    if not generated_at or not isinstance(slots, list):
        raise RuntimeError("Invalid weather-forecast.json")

    con = sqlite3.connect(DB)

    try:
        inserted = 0

        for slot in slots:
            start = slot.get("start")

            if not start:
                continue

            cur = con.execute(
                """
                INSERT OR IGNORE INTO forecast_weather_15m
                (
                    generated_at_utc,
                    start_utc,
                    temperature_2m_c,
                    cloud_cover_pct,
                    shortwave_radiation_w_m2,
                    direct_radiation_w_m2,
                    diffuse_radiation_w_m2,
                    direct_normal_irradiance_w_m2,
                    shortwave_radiation_clear_sky_w_m2,
                    sunshine_duration_s,
                    gti_goodwe2000_zo30_w_m2,
                    gti_goodwe4200_zw30_w_m2,
                    gti_solaredge_zw25_w_m2,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open-meteo')
                """,
                (
                    generated_at,
                    start,
                    slot.get("temperature_2m_c"),
                    slot.get("cloud_cover_pct"),
                    slot.get("shortwave_radiation_w_m2"),
                    slot.get("direct_radiation_w_m2"),
                    slot.get("diffuse_radiation_w_m2"),
                    slot.get("direct_normal_irradiance_w_m2"),
                    slot.get("shortwave_radiation_clear_sky_w_m2"),
                    slot.get("sunshine_duration_s"),
                    slot.get("gti_goodwe2000_zo30_w_m2"),
                    slot.get("gti_goodwe4200_zw30_w_m2"),
                    slot.get("gti_solaredge_zw25_w_m2"),
                ),
            )

            inserted += cur.rowcount

        con.commit()

        print(f"PASS: slots={len(slots)} inserted={inserted}")
        print("generated_at:", generated_at)

    finally:
        con.close()


if __name__ == "__main__":
    main()

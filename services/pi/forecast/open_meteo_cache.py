#!/usr/bin/env python3
"""One atomic, read-only Open-Meteo source snapshot for the 15-minute Pi planner.

Refresh is the sole network edge, run separately every 30 minutes. Consumers
never access Open-Meteo. A failed refresh never overwrites a good snapshot.
"""
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from open_meteo_transport import fetch_json_with_retry

CACHE = Path("/home/jeroen/ems/data/open-meteo-source-cache.json")
SCHEMA = "EMS_PI_OPEN_METEO_SOURCE_CACHE_V0.1"
MAX_SOURCE_AGE_SEC = 90 * 60
FUTURE_SLOTS = 96
STEP = timedelta(minutes=15)
LAT, LON = 52.70808, 5.10003

WEATHER_FIELDS = (
    "temperature_2m", "apparent_temperature", "cloud_cover",
    "wind_speed_10m", "wind_direction_10m", "shortwave_radiation",
    "direct_radiation", "diffuse_radiation", "direct_normal_irradiance",
    "shortwave_radiation_clear_sky", "sunshine_duration",
    "terrestrial_radiation",
)
SOURCE_FIELDS = {
    "weather": WEATHER_FIELDS,
    "gti_goodwe2000": ("global_tilted_irradiance",),
    "gti_goodwe4200": ("global_tilted_irradiance",),
    "gti_solaredge": ("global_tilted_irradiance",),
}
GTI_GEOMETRY = {
    "gti_goodwe2000": (-135, 30),
    "gti_goodwe4200": (135, 30),
    "gti_solaredge": (135, 25),
}

def utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def utc_dt(value):
    if not isinstance(value, str):
        raise ValueError("missing UTC timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Open-Meteo timezone=UTC
    return dt.astimezone(timezone.utc)

def floor_quarter(value):
    value = value.astimezone(timezone.utc)
    return value.replace(minute=value.minute // 15 * 15, second=0, microsecond=0)

def request_for(name):
    params = {
        "latitude": LAT, "longitude": LON,
        "minutely_15": ",".join(SOURCE_FIELDS[name]),
        "past_minutely_15": 4,
        "forecast_minutely_15": 104,
        "timezone": "UTC",
    }
    if name in GTI_GEOMETRY:
        params["azimuth"], params["tilt"] = GTI_GEOMETRY[name]
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    return urllib.request.Request(url, headers={"User-Agent": "EMS-Pi-Open-Meteo-Cache/0.1"})

def validate_sources(sources, now):
    """Reject incomplete source bundles, including any 96-slot horizon holes."""
    required = [floor_quarter(now) + STEP * i for i in range(FUTURE_SLOTS)]
    for name, keys in SOURCE_FIELDS.items():
        payload = sources.get(name)
        if not isinstance(payload, dict):
            raise ValueError(f"missing source {name}")
        q = payload.get("minutely_15")
        if not isinstance(q, dict) or not isinstance(q.get("time"), list):
            raise ValueError(f"invalid time series {name}")
        times = q["time"]
        if not times or any(
            not isinstance(q.get(k), list) or len(q[k]) != len(times) for k in keys
        ):
            raise ValueError(f"incomplete data arrays {name}")
        index = {utc_dt(t): i for i, t in enumerate(times)}
        for t in required:
            pos = index.get(t)
            if pos is None:
                raise ValueError(f"missing forecast slot {name} {utc_text(t)}")
            # These fields directly feed numeric PV/weather logic; null is
            # not a substitute for known solar radiation or geometry.
            critical = ("shortwave_radiation", "terrestrial_radiation") if name == "weather" else keys
            for key in critical:
                val = q[key][pos]
                if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                    raise ValueError(f"invalid {key} {name} {utc_text(t)}")

def validate_snapshot(snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("invalid Open-Meteo cache schema")
    fetched = utc_dt(snapshot.get("fetchedAt"))
    age = (now - fetched).total_seconds()
    if not -120 <= age <= MAX_SOURCE_AGE_SEC:
        raise ValueError(f"stale Open-Meteo source cache age={age:.0f}s")
    validate_sources(snapshot.get("sources") or {}, now)
    return snapshot

def load_snapshot(path=CACHE, now=None):
    with path.open(encoding="utf-8") as fd:
        return validate_snapshot(json.load(fd), now)

def refresh(path=CACHE, fetch=fetch_json_with_retry, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    sources = {}
    for name in SOURCE_FIELDS:
        sources[name] = fetch(request_for(name), label=name)
    finished = clock()
    validate_sources(sources, finished)
    snapshot = {
        "schema": SCHEMA,
        "fetchedAt": utc_text(finished),
        "readOnly": True,
        "controlWrites": False,
        "sources": sources,
    }
    # A complete, validated generation replaces the previous snapshot atomically.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(path)
    return snapshot

if __name__ == "__main__":
    snapshot = refresh()
    print("PASS: Open-Meteo source cache refreshed")
    print("fetchedAt:", snapshot["fetchedAt"])
    print("sources:", ",".join(snapshot["sources"]))

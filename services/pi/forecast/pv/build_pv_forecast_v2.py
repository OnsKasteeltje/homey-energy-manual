#!/usr/bin/env python3
"""Build Planner V2 PV forecast in shadow/read-only mode.

Forecasts PV production only. It never estimates guaranteed household export
and never performs control writes. Realtime opportunity authority remains P1.
"""
import json, math, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LAT, LON = 52.70808, 5.10003
TZ = ZoneInfo("Europe/Amsterdam")
SLOTS = 96
PV_NOMINAL_W = 8000
SOLAR_CONSTANT_W_M2 = 1367.7
MIN_CLEAR_SKY_W_M2 = 25.0
HISTORICAL_WEIGHT = 0.85
MIN_PROFILE_DAYS = 3
MIN_PROFILE_SAMPLES = 3
PV_ARRAYS = [("goodwe2000", -135, 30), ("goodwe4200", 135, 30), ("solaredge", 135, 25)]

AXIS = Path("/home/jeroen/ems/data/planner-axis.json")
PROFILE = Path("/home/jeroen/ems/data/pv-history-profile.json")
OUTPUT = Path("/home/jeroen/ems/data/pv-forecast-v2.json")
STATE = Path("/home/jeroen/ems/data/pv-forecast-v2-confidence-state.json")


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def clear_sky_ghi(terrestrial):
    terrestrial = max(0.0, float(terrestrial or 0))
    cosz = min(1.0, terrestrial / SOLAR_CONSTANT_W_M2)
    if cosz <= 0:
        return 0.0
    return max(0.0, 1098.0 * cosz * math.exp(-0.059 / cosz))


def fetch(params):
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ems-pi-pv-forecast-v2/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch_gti(azimuth, tilt):
    d = fetch({"latitude": LAT, "longitude": LON, "minutely_15": "global_tilted_irradiance",
               "past_minutely_15": 4, "forecast_minutely_15": 104, "timezone": "UTC",
               "tilt": tilt, "azimuth": azimuth})
    q = d.get("minutely_15") or {}
    out = {}
    for t, v in zip(q.get("time") or [], q.get("global_tilted_irradiance") or []):
        dt = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        out[dt.isoformat().replace("+00:00", "Z")] = max(0.0, float(v or 0))
    return out


def previous_state():
    try:
        d = json.loads(STATE.read_text())
        return d if d.get("schema") == "EMS_PI_PV_FORECAST_V2_CONFIDENCE_STATE" else {}
    except Exception:
        return {}


def main():
    axis = json.loads(AXIS.read_text())
    axis_slots = axis.get("slots") or []
    if len(axis_slots) != SLOTS:
        raise RuntimeError(f"expected {SLOTS} planner slots, got {len(axis_slots)}")
    wanted = set(axis_slots)
    gti = {name: fetch_gti(azimuth, tilt) for name, azimuth, tilt in PV_ARRAYS}

    data = fetch({
        "latitude": LAT, "longitude": LON,
        "minutely_15": "shortwave_radiation,terrestrial_radiation,cloud_cover",
        "past_minutely_15": 4, "forecast_minutely_15": 104, "timezone": "UTC",
    })
    q = data.get("minutely_15") or {}
    times = q.get("time") or []
    irr = q.get("shortwave_radiation") or []
    terrestrial = q.get("terrestrial_radiation") or []
    clouds = q.get("cloud_cover") or []
    if not times or not (len(times) == len(irr) == len(terrestrial) == len(clouds)):
        raise RuntimeError("invalid Open-Meteo 15-minute response")

    profile = {}
    usable_days = 0
    if PROFILE.exists():
        try:
            p = json.loads(PROFILE.read_text())
            if p.get("schema") == "EMS_PI_PV_HISTORY_PROFILE_V0.1":
                profile = p.get("profile") or {}
                usable_days = int(p.get("usable_day_count") or 0)
        except Exception:
            pass

    prev = previous_state()
    prev_map = prev.get("previousPvForecast") or {}
    recent_accuracy = float(prev.get("recentLocalAccuracy") or 0.70)
    slots = []
    for i, raw in enumerate(times):
        dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        start = dt.isoformat().replace("+00:00", "Z")
        if start not in wanted:
            continue

        radiation = max(0.0, float(irr[i] or 0))
        clear = clear_sky_ghi(terrestrial[i])
        gti_values = [gti[name].get(start) for name, _azimuth, _tilt in PV_ARRAYS]
        gti_complete = all(v is not None for v in gti_values)
        # GTI is geometry evidence only: inverter AC ratings are deliberately not
        # used as array Wp. Historical measured PV calibrates absolute production.
        geometry_factor = (
            sum(max(0.0, float(v)) for v in gti_values) / len(gti_values)
            if gti_complete else radiation
        )
        theoretical = min(PV_NOMINAL_W, geometry_factor * (PV_NOMINAL_W / 1000.0))
        local = dt.astimezone(TZ)
        quarter = local.hour * 4 + local.minute // 15
        hist = profile.get(str(quarter)) or {}
        envelope = hist.get("clearEnvelopeW")
        samples = int(hist.get("sampleCount") or 0)
        use_history = (usable_days >= MIN_PROFILE_DAYS and samples >= MIN_PROFILE_SAMPLES
                       and envelope is not None and clear >= MIN_CLEAR_SKY_W_M2)

        if use_history:
            cloud_factor = clamp(radiation / clear, 0.0, 1.10)
            historical = max(0.0, float(envelope) * cloud_factor)
            pv = min(PV_NOMINAL_W, HISTORICAL_WEIGHT * historical
                     + (1.0 - HISTORICAL_WEIGHT) * theoretical)
            basis = "HISTORICAL_ENVELOPE_CLOUD_ADJUSTED"
            history_quality = clamp(samples / 12.0)
        else:
            cloud_factor = None
            pv = theoretical
            basis = "THEORETICAL_FALLBACK"
            history_quality = 0.35

        cloud_window = [float(x or 0) for x in clouds[max(0, i-2):min(len(clouds), i+3)]]
        mean_cloud = sum(cloud_window) / len(cloud_window)
        variance = sum((x - mean_cloud) ** 2 for x in cloud_window) / len(cloud_window)
        cloud_stability = clamp(1.0 - math.sqrt(variance) / 35.0)
        previous_w = prev_map.get(start)
        if previous_w is None:
            consistency = 0.70
        else:
            denom = max(500.0, pv, float(previous_w))
            consistency = clamp(1.0 - abs(pv - float(previous_w)) / denom)
        horizon_h = max(0.0, (dt - datetime.now(timezone.utc)).total_seconds() / 3600)
        horizon_quality = 1.0 - 0.20 * min(1.0, horizon_h / 24.0)
        daylight = theoretical >= 25 or pv >= 25
        if daylight:
            confidence = clamp((0.40 * consistency + 0.30 * cloud_stability
                                + 0.30 * recent_accuracy) * horizon_quality)
        else:
            confidence = None

        slots.append({
            "start": start,
            "pvForecastW": round(pv),
            "confidence": None if confidence is None else round(confidence, 3),
            "confidenceComponents": {
                "historyQuality": round(history_quality, 3),
                "forecastConsistency": round(consistency, 3),
                "cloudStability": round(cloud_stability, 3),
                "recentLocalAccuracy": round(recent_accuracy, 3),
                "horizon": round(horizon_quality, 3),
            },
            "modelBasis": basis,
            "geometryBasis": "ARRAY_GTI" if gti_complete else "HORIZONTAL_RADIATION_FALLBACK",
        })
        if len(slots) == SLOTS:
            break

    if len(slots) != SLOTS:
        raise RuntimeError(f"expected {SLOTS} output slots, got {len(slots)}")

    out = {
        "schema": "EMS_PI_PV_FORECAST_V2",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "READ_ONLY",
        "controlWrites": False,
        "realtimeAuthority": "P1",
        "forecastMeaning": "PV_PRODUCTION_NOT_GUARANTEED_EXPORT",
        "slotMinutes": 15,
        "horizonSlots": SLOTS,
        "model": {
            "nominalW": PV_NOMINAL_W,
            "arrays": [{"name": n, "azimuth": a, "tiltDeg": t} for n, a, t in PV_ARRAYS],
            "arrayCapacityBasis": "NOT_ASSUMED_FROM_INVERTER_AC_RATING",
            "calibration": "ROLLING_HISTORICAL_CLEAR_ENVELOPE",
            "confidenceAdvisoryOnly": True,
            "recentLocalAccuracySource": "CLOSED_VALIDATED_HISTORY_ONLY",
        },
        "slots": slots,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    tmp.replace(OUTPUT)
    state = {"schema":"EMS_PI_PV_FORECAST_V2_CONFIDENCE_STATE",
             "updatedAt":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
             "recentLocalAccuracy":round(recent_accuracy,4),
             "previousPvForecast":{s["start"]:s["pvForecastW"] for s in slots}}
    stmp = STATE.with_suffix(".tmp")
    stmp.write_text(json.dumps(state,separators=(",",":"))+"\n")
    stmp.replace(STATE)
    print(f"PASS: wrote {len(slots)} V2 PV slots to {OUTPUT}")


if __name__ == "__main__":
    main()

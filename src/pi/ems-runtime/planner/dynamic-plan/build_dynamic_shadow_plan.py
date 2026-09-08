#!/usr/bin/env python3

"""Build the first rolling-horizon Dynamic Pi Planner in PURE_SHADOW.

Design goals:
- maximize expected PV self-consumption over the rolling 24 h horizon;
- preserve WW comfort as a hard constraint (ON_TEMP/fallback need before 19:00);
- allow WW to use the PV flanks and Tesla to absorb the high PV peak;
- combine forecast with live P1 export instead of using a fixed PV threshold;
- attach a compact confidence score to every slot;
- never perform physical writes.

This is deliberately a shadow planner. It runs beside the existing WW and
quarter-hour planners so its decisions can be replayed and compared before any
control migration.
"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PV_FILE = Path("/home/jeroen/ems/data/pv-forecast.json")
WEATHER_FILE = Path("/home/jeroen/ems/data/weather-forecast.json")
QUATT_FILE = Path("/home/jeroen/ems/data/quatt-forecast.json")
BASE_FILE = Path("/home/jeroen/ems/data/base-load-forecast.json")
WW_INPUT_FILE = Path("/home/jeroen/ems/data/ww-input.json")
AXIS_FILE = Path("/home/jeroen/ems/data/planner-axis.json")
ENERGY_STATE_FILE = Path(
    "/home/jeroen/ems/repo/homey-energy-manual/docs/data/energy-state-v2.json"
)
OUTPUT = Path("/home/jeroen/ems/data/dynamic-shadow-plan.json")
CONFIDENCE_STATE = Path("/home/jeroen/ems/data/dynamic-confidence-state.json")

TZ = ZoneInfo("Europe/Amsterdam")
SLOT_MIN = 15
SLOT_H = SLOT_MIN / 60
BOILER_W = 1900
WW_FALLBACK_MIN = 240
WW_DEADLINE_HOUR = 19
WW_MIN_RUN_SLOTS = 2

EV_W_PER_A = 690
EV_START_MIN_A = 7
EV_RUN_MIN_A = 6
EV_MAX_A = 16
LIVE_CONNECTED_HORIZON_H = 2

# Confidence deliberately uses only three compact signals.
W_CONSISTENCY = 0.40
W_CLOUD_STABILITY = 0.30
W_LOCAL_ACCURACY = 0.30


def load(path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        if default is not None:
            return default
        raise


def stamp(slot):
    value = slot.get("slot_start_utc") or slot.get("start") or slot.get("startAt")
    if value and value.endswith(".000Z"):
        value = value[:-5] + "Z"
    return value


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def pv_power(slot):
    for key in ("pvForecastW", "pv_forecast_w", "power_w", "forecast_w"):
        if slot.get(key) is not None:
            return max(0.0, float(slot[key]))
    return 0.0


def expected_tesla_home(local_dt):
    wd = local_dt.weekday()  # Mon=0 .. Sun=6
    if wd in (4, 5, 6):
        return True
    if wd == 3 and local_dt.hour >= 18:
        return True
    if wd == 0 and local_dt.hour < 8:
        return True
    return False


def ev_target(surplus_w, already_running=False):
    min_a = EV_RUN_MIN_A if already_running else EV_START_MIN_A
    if surplus_w < min_a * EV_W_PER_A:
        return 0
    amps = min(EV_MAX_A, int(surplus_w // EV_W_PER_A))
    return amps * EV_W_PER_A if amps >= min_a else 0


def deadline_utc(date_key):
    y, m, d = map(int, date_key.split("-"))
    return datetime(y, m, d, WW_DEADLINE_HOUR, tzinfo=TZ).astimezone(timezone.utc)


def cloud_stability(weather_slots, index):
    """High for stable clear/overcast regimes; low for rapidly changing clouds."""
    values = []
    for j in range(max(0, index - 2), min(len(weather_slots), index + 3)):
        value = weather_slots[j].get("cloud_cover_pct")
        if value is not None:
            values.append(float(value))
    if len(values) < 2:
        return 0.70
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = math.sqrt(variance)
    # A stable cloud field (clear OR overcast) is predictable. 35 pct standard
    # deviation maps to roughly zero stability; this is a smooth score, not a gate.
    return clamp(1.0 - std / 35.0)


def forecast_consistency(ts, current_pv_w, previous_map):
    previous = previous_map.get(ts)
    if previous is None:
        return 0.70
    scale = max(500.0, current_pv_w, float(previous))
    rel_error = abs(current_pv_w - float(previous)) / scale
    return clamp(1.0 - rel_error)


def recent_local_accuracy(now_utc, pv_map, energy_state, confidence_state):
    """Compare the latest site PV measurement with the nearest forecast slot.

    The smoothed score persists between runs. This intentionally avoids storing
    a large meteorological history: one rolling accuracy value is enough for v0.1.
    """
    previous = float(confidence_state.get("recentLocalAccuracy") or 0.70)
    pv_state = energy_state.get("pv") or {}
    actual = pv_state.get("total_w")
    if actual is None:
        return previous

    nearest = None
    nearest_delta = None
    for ts, slot in pv_map.items():
        delta = abs((parse_utc(ts) - now_utc).total_seconds())
        if nearest_delta is None or delta < nearest_delta:
            nearest = pv_power(slot)
            nearest_delta = delta

    if nearest is None or nearest_delta is None or nearest_delta > 30 * 60:
        return previous

    scale = max(500.0, float(actual), nearest)
    instantaneous = clamp(1.0 - abs(float(actual) - nearest) / scale)
    return clamp(0.65 * previous + 0.35 * instantaneous)


def horizon_factor(slot_dt, now_utc):
    """Only a mild horizon prior; weather predictability remains dominant."""
    hours = max(0.0, (slot_dt - now_utc).total_seconds() / 3600)
    return 1.0 - 0.08 * min(1.0, hours / 24.0)


def realtime_corrected_export(forecast_export_w, confidence, slot_dt, now_utc, actual_export_w):
    """Blend live P1 into the near horizon; influence decays smoothly over 2 h."""
    hours = max(0.0, (slot_dt - now_utc).total_seconds() / 3600)
    if hours > 2.0:
        return forecast_export_w, 0.0
    recency = 1.0 - hours / 2.0
    live_weight = clamp((1.0 - confidence) * recency + 0.35 * recency, 0.0, 0.85)
    corrected = (1.0 - live_weight) * forecast_export_w + live_weight * actual_export_w
    return max(0.0, corrected), live_weight


def enforce_min_run(selected, candidates, scores, required_slots):
    """Prefer runs of >=30 min without ever making WW infeasible.

    This is a soft cleanup after energy allocation, not a PV threshold.
    """
    if not selected or required_slots < WW_MIN_RUN_SLOTS:
        return selected

    selected = set(selected)
    runs = []
    run = []
    for i in range(len(candidates)):
        if i in selected:
            if run and i != run[-1] + 1:
                runs.append(run)
                run = []
            run.append(i)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)

    singles = [r[0] for r in runs if len(r) == 1]
    for single in singles:
        neighbours = [x for x in (single - 1, single + 1) if 0 <= x < len(candidates)]
        neighbours = [x for x in neighbours if x not in selected]
        if not neighbours:
            continue
        best_add = max(neighbours, key=lambda x: scores[x])
        # Swap out the weakest selected slot elsewhere so total WW energy is fixed.
        removable = [x for x in selected if x != single and abs(x - single) > 1]
        if not removable:
            continue
        worst_remove = min(removable, key=lambda x: scores[x])
        if scores[best_add] >= scores[worst_remove] * 0.75:
            selected.remove(worst_remove)
            selected.add(best_add)
    return selected


def main():
    pv_doc = load(PV_FILE)
    weather_doc = load(WEATHER_FILE)
    quatt_doc = load(QUATT_FILE)
    base_doc = load(BASE_FILE)
    ww_doc = load(WW_INPUT_FILE)
    axis_doc = load(AXIS_FILE)
    energy_state = load(ENERGY_STATE_FILE, {})
    confidence_state = load(CONFIDENCE_STATE, {})

    axis_slots = axis_doc.get("slots", [])
    if len(axis_slots) != 96:
        raise SystemExit(f"FAIL: expected 96 planner slots, got {len(axis_slots)}")

    pv_map = {stamp(x): x for x in pv_doc.get("slots", [])}
    q_map = {stamp(x): x for x in quatt_doc.get("slots", [])}
    b_map = {stamp(x): x for x in base_doc.get("slots", [])}
    weather_map = {stamp(x): x for x in weather_doc.get("slots", [])}

    common = [x for x in axis_slots if x in pv_map and x in q_map and x in b_map and x in weather_map]
    if len(common) != 96:
        raise SystemExit(f"FAIL: dynamic planner aligned slots={len(common)}, expected 96")

    now_utc = datetime.now(timezone.utc)
    today_local = now_utc.astimezone(TZ).date().isoformat()
    grid = energy_state.get("grid") or {}
    actual_export_w = max(0.0, float(grid.get("export_w") or 0))

    previous_pv = confidence_state.get("previousPvForecast") or {}
    local_accuracy = recent_local_accuracy(now_utc, pv_map, energy_state, confidence_state)
    weather_slots = [weather_map[x] for x in common]

    tesla_state = energy_state.get("tesla") or {}
    tesla_connected_now = tesla_state.get("connected") is True
    tesla_charging_now = tesla_state.get("charging") is True
    live_connected_until = now_utc + timedelta(hours=LIVE_CONNECTED_HORIZON_H)

    raw_slots = []
    for i, ts in enumerate(common):
        slot_dt = parse_utc(ts)
        local_dt = slot_dt.astimezone(TZ)
        pv_w = pv_power(pv_map[ts])
        quatt_w = max(0.0, float(q_map[ts].get("quattForecastW") or 0))
        base_w = max(0.0, float(b_map[ts].get("baseLoadForecastW") or 0))
        non_controllable = base_w + quatt_w
        forecast_export = max(0.0, pv_w - non_controllable)

        consistency = forecast_consistency(ts, pv_w, previous_pv)
        stability = cloud_stability(weather_slots, i)
        confidence = clamp(
            (W_CONSISTENCY * consistency + W_CLOUD_STABILITY * stability + W_LOCAL_ACCURACY * local_accuracy)
            * horizon_factor(slot_dt, now_utc)
        )
        corrected_export, live_weight = realtime_corrected_export(
            forecast_export, confidence, slot_dt, now_utc, actual_export_w
        )

        expected_home = expected_tesla_home(local_dt)
        live_override = tesla_connected_now and now_utc - timedelta(minutes=15) <= slot_dt <= live_connected_until
        tesla_available = live_override or expected_home

        raw_slots.append({
            "slot_start_utc": ts,
            "localDate": local_dt.date().isoformat(),
            "pvForecastW": round(pv_w),
            "baseLoadForecastW": round(base_w),
            "quattForecastW": round(quatt_w),
            "forecastExportBeforeFlexW": round(forecast_export),
            "correctedExportBeforeFlexW": round(corrected_export),
            "confidence": round(confidence, 3),
            "confidenceComponents": {
                "forecastConsistency": round(consistency, 3),
                "cloudStability": round(stability, 3),
                "recentLocalAccuracy": round(local_accuracy, 3),
                "horizonFactor": round(horizon_factor(slot_dt, now_utc), 3),
                "liveP1Weight": round(live_weight, 3),
            },
            "teslaAvailableForecast": tesla_available,
            "teslaAvailabilitySource": (
                "LIVE_CONNECTED_NEAR_TERM" if live_override
                else "WEEKLY_HOME_FORECAST" if expected_home
                else "NOT_AVAILABLE"
            ),
        })

    ww = ww_doc.get("warmWater") or {}
    by_date = {}
    for slot in raw_slots:
        by_date.setdefault(slot["localDate"], []).append(slot)

    ww_selected_ts = set()
    daily = []
    for date_key, day_slots in sorted(by_date.items()):
        goal_reached = False
        remaining_min = WW_FALLBACK_MIN
        catchup = False
        if date_key == today_local:
            goal_reached = ww.get("goalReachedToday") is True or ww.get("goalReached") is True
            remaining_min = 0 if goal_reached else max(0, int(ww.get("remainingFallbackMin") or 0))
            catchup = ww.get("catchupRequired") is True

        deadline = deadline_utc(date_key)
        candidates = [s for s in day_slots if parse_utc(s["slot_start_utc"]) < deadline and parse_utc(s["slot_start_utc"]) >= now_utc - timedelta(minutes=15)]
        required_slots = int(math.ceil(remaining_min / SLOT_MIN)) if not goal_reached else 0
        required_slots = min(required_slots, len(candidates))

        # Joint-allocation score: WW likes useful PV, but deliberately gives the
        # very high export peak to Tesla when Tesla is available and WW comfort
        # can still be met in other slots. There is no fixed PV start threshold.
        scores = []
        for s in candidates:
            export_w = float(s["correctedExportBeforeFlexW"])
            ww_capture = min(BOILER_W, export_w)
            confidence = float(s["confidence"])
            peak_for_tesla = s["teslaAvailableForecast"] and export_w >= EV_START_MIN_A * EV_W_PER_A
            tesla_peak_penalty = min(BOILER_W, max(0.0, export_w - BOILER_W)) if peak_for_tesla else 0.0
            urgency = 0.0
            if candidates:
                position = candidates.index(s) / max(1, len(candidates) - 1)
                urgency = 350.0 * position * (1.0 if catchup else 0.35)
            score = ww_capture * (0.65 + 0.35 * confidence) - 0.55 * tesla_peak_penalty + urgency
            scores.append(score)

        ranked = sorted(range(len(candidates)), key=lambda i: (scores[i], candidates[i]["slot_start_utc"]), reverse=True)
        selected = set(ranked[:required_slots])
        selected = enforce_min_run(selected, candidates, scores, required_slots)

        # Comfort is the hard constraint: if enough slots exist, exactly the
        # required count is reserved for WW before the deadline.
        if len(selected) < required_slots:
            for i in ranked:
                selected.add(i)
                if len(selected) >= required_slots:
                    break

        for i in selected:
            ww_selected_ts.add(candidates[i]["slot_start_utc"])

        daily.append({
            "date": date_key,
            "goalReached": goal_reached,
            "remainingFallbackMin": remaining_min,
            "requiredSlots": required_slots,
            "allocatedSlots": len(selected),
            "comfortFeasible": len(selected) >= required_slots,
            "deadlineLocal": "19:00",
            "allocationPolicy": "DYNAMIC_PV_CAPTURE_WITH_TESLA_PEAK_SHAPING",
        })

    # Second pass: Tesla receives the remaining peak after WW allocation.
    slots = []
    ev_running = tesla_charging_now
    for s in raw_slots:
        ww_w = BOILER_W if s["slot_start_utc"] in ww_selected_ts else 0
        export_w = float(s["correctedExportBeforeFlexW"])
        remaining_export = max(0.0, export_w - ww_w)
        ev_w = 0
        ev_reason = "NOT_AVAILABLE"
        if s["teslaAvailableForecast"]:
            ev_w = ev_target(remaining_export, ev_running)
            if ev_w > 0:
                ev_reason = "DYNAMIC_PV_PEAK_ABSORBER"
                ev_running = True
            else:
                ev_reason = "NO_ECONOMIC_PV_HEADROOM"
                ev_running = False
        else:
            ev_running = False

        net_after = float(s["baseLoadForecastW"]) + float(s["quattForecastW"]) + ww_w + ev_w - float(s["pvForecastW"])
        slots.append({
            **s,
            "wwPlanW": ww_w,
            "wwAllocationReason": "DYNAMIC_COMFORT_PV_SLOT" if ww_w else "HOLD",
            "evPlanW": ev_w,
            "evAllocationReason": ev_reason,
            "gridImportAfterFlexW": round(max(0.0, net_after)),
            "gridExportAfterFlexW": round(max(0.0, -net_after)),
        })

    payload = {
        "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.1",
        "generated_at": now_utc.isoformat().replace("+00:00", "Z"),
        "mode": "PURE_SHADOW",
        "readOnly": True,
        "control_writes": False,
        "objective": "MAXIMIZE_PV_SELF_CONSUMPTION_SUBJECT_TO_WW_COMFORT",
        "guardrails": {
            "wwComfortHardConstraint": True,
            "wwDeadlineLocal": "19:00",
            "wwMinRunMinutes": WW_MIN_RUN_SLOTS * SLOT_MIN,
            "teslaRole": "SECONDARY_FLEX_LOAD_WHEN_WW_COMFORT_REMAINS_FEASIBLE",
            "fixedPvStartThresholdW": None,
            "realtimeP1Correction": True,
        },
        "confidenceModel": {
            "signals": ["forecastConsistency", "cloudStability", "recentLocalAccuracy"],
            "weights": {
                "forecastConsistency": W_CONSISTENCY,
                "cloudStability": W_CLOUD_STABILITY,
                "recentLocalAccuracy": W_LOCAL_ACCURACY,
            },
            "horizonPolicy": "MILD_PRIOR_ONLY_MAX_8_PERCENT_24H",
        },
        "realtime": {
            "actualP1ExportW": round(actual_export_w),
            "recentLocalAccuracy": round(local_accuracy, 3),
        },
        "dailyPlans": daily,
        "slot_count": len(slots),
        "slots": slots,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    tmp.replace(OUTPUT)

    state_payload = {
        "schema": "EMS_PI_DYNAMIC_CONFIDENCE_STATE_V0.1",
        "updatedAt": now_utc.isoformat().replace("+00:00", "Z"),
        "recentLocalAccuracy": round(local_accuracy, 4),
        "previousPvForecast": {ts: round(pv_power(pv_map[ts])) for ts in common},
    }
    tmp_state = CONFIDENCE_STATE.with_suffix(".tmp")
    tmp_state.write_text(json.dumps(state_payload, separators=(",", ":")) + "\n")
    tmp_state.replace(CONFIDENCE_STATE)

    before_export_kwh = sum(float(x["correctedExportBeforeFlexW"]) for x in slots) * SLOT_H / 1000
    after_export_kwh = sum(float(x["gridExportAfterFlexW"]) for x in slots) * SLOT_H / 1000
    ww_kwh = sum(float(x["wwPlanW"]) for x in slots) * SLOT_H / 1000
    ev_kwh = sum(float(x["evPlanW"]) for x in slots) * SLOT_H / 1000

    print("PASS: dynamic shadow planner v0.1 built")
    print("slots                    :", len(slots))
    print("WW planned kWh           :", round(ww_kwh, 2))
    print("Tesla planned kWh        :", round(ev_kwh, 2))
    print("corrected export before  :", round(before_export_kwh, 2))
    print("forecast export after    :", round(after_export_kwh, 2))
    print("recent local accuracy    :", round(local_accuracy, 3))
    print("output                   :", OUTPUT)


if __name__ == "__main__":
    main()

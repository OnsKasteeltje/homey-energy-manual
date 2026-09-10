#!/usr/bin/env python3

"""Build the rolling-horizon Dynamic Pi Planner in PURE_SHADOW.

Design goals:
- maximize expected PV self-consumption over the rolling 24 h horizon;
- preserve WW comfort as a hard constraint (ON_TEMP/fallback need before 19:00);
- allow WW to use PV flanks and Tesla to absorb residual PV opportunities;
- use dynamic EV PV-window qualification instead of a fixed per-slot threshold;
- combine forecast with live P1 export;
- attach a compact confidence score to every slot;
- never perform physical writes.

This planner runs beside the existing planners so decisions can be replayed and
compared before any control migration.
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
EV_KICKSTART_A = 7
EV_RUN_MIN_A = 6
EV_MAX_A = 16
EV_RUN_MIN_W = EV_RUN_MIN_A * EV_W_PER_A
EV_MIN_WINDOW_SLOTS = 2
EV_MIN_WINDOW_PV_COVERAGE = 0.50
EV_SECONDARY_COVERAGE = 0.75
EV_PURE_COVERAGE = 1.00

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
    """Informational weekly presence forecast; never an opportunity control gate."""
    wd = local_dt.weekday()  # Mon=0 .. Sun=6
    if wd in (4, 5, 6):
        return True
    if wd == 3 and local_dt.hour >= 18:
        return True
    if wd == 0 and local_dt.hour < 8:
        return True
    return False


def is_consecutive(a, b):
    return (
        parse_utc(b["slot_start_utc"]) - parse_utc(a["slot_start_utc"])
    ).total_seconds() == SLOT_MIN * 60


def opportunity_class(coverage):
    if coverage >= EV_PURE_COVERAGE:
        return "PURE_PV"
    if coverage >= EV_SECONDARY_COVERAGE:
        return "SECONDARY"
    return "FALLBACK_MIXED"


def qualify_ev_windows(candidates):
    """Find contiguous residual-PV windows after WW comfort reservation.

    Stable planning uses 6 A. 7 A is actuator kickstart only, not a planner
    threshold. A window must last >=30 min and provide >=50% of the energy
    required for stable 6 A charging over the complete window.
    """
    windows = []
    current = []

    def finish(indices):
        if len(indices) < EV_MIN_WINDOW_SLOTS:
            return

        residual_sum_w = sum(candidates[i]["evResidualExportW"] for i in indices)
        min_ev_sum_w = EV_RUN_MIN_W * len(indices)
        raw_coverage = residual_sum_w / min_ev_sum_w if min_ev_sum_w else 0.0
        if raw_coverage < EV_MIN_WINDOW_PV_COVERAGE:
            return

        pv_capture_kwh = sum(
            min(float(candidates[i]["evResidualExportW"]), EV_RUN_MIN_W)
            for i in indices
        ) * SLOT_H / 1000
        min_ev_energy_kwh = EV_RUN_MIN_W * len(indices) * SLOT_H / 1000

        windows.append({
            "indices": tuple(indices),
            "coverage": raw_coverage,
            "displayCoverage": min(1.0, raw_coverage),
            "class": opportunity_class(raw_coverage),
            "pvCaptureKWhAt6A": pv_capture_kwh,
            "minEvEnergyKWh": min_ev_energy_kwh,
            "avgResidualExportW": residual_sum_w / len(indices),
            "start": candidates[indices[0]]["slot_start_utc"],
            "end": candidates[indices[-1]]["slot_start_utc"],
        })

    for i, slot in enumerate(candidates):
        eligible = slot["teslaOpportunityConnected"] and slot["evResidualExportW"] > 0
        if not eligible:
            finish(current)
            current = []
            continue
        if current and not is_consecutive(candidates[current[-1]], slot):
            finish(current)
            current = []
        current.append(i)
    finish(current)
    return windows


def apply_best_windows_first(windows):
    """Prefer stronger later PV windows without discarding irreplaceable PV capture."""
    class_rank = {"FALLBACK_MIXED": 1, "SECONDARY": 2, "PURE_PV": 3}

    for pos, window in enumerate(windows):
        later_better = [
            x for x in windows[pos + 1:]
            if class_rank[x["class"]] > class_rank[window["class"]]
        ]
        future_better_kwh = sum(x["pvCaptureKWhAt6A"] for x in later_better)
        window["futureBetterPvCaptureKWh"] = future_better_kwh
        window["selected"] = (
            window["class"] == "PURE_PV"
            or future_better_kwh + 1e-9 < window["pvCaptureKWhAt6A"]
        )
        if window["selected"]:
            window["selectionReason"] = (
                "BEST_PV_WINDOW"
                if window["class"] == "PURE_PV"
                else "FUTURE_BETTER_CAPACITY_INSUFFICIENT"
            )
        else:
            window["selectionReason"] = "DEFERRED_TO_LATER_BETTER_PV"

    return windows


def ev_target_from_residual(residual_w):
    """Plan stable charging at >=6 A inside a qualified opportunity window."""
    amps_from_pv = int(max(0.0, residual_w) // EV_W_PER_A)
    amps = max(EV_RUN_MIN_A, amps_from_pv)
    amps = min(EV_MAX_A, amps)
    return amps * EV_W_PER_A


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
    return clamp(1.0 - std / 35.0)


def forecast_consistency(ts, current_pv_w, previous_map):
    previous = previous_map.get(ts)
    if previous is None:
        return 0.70
    scale = max(500.0, current_pv_w, float(previous))
    rel_error = abs(current_pv_w - float(previous)) / scale
    return clamp(1.0 - rel_error)


def recent_local_accuracy(now_utc, pv_map, energy_state, confidence_state):
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
    hours = max(0.0, (slot_dt - now_utc).total_seconds() / 3600)
    return 1.0 - 0.08 * min(1.0, hours / 24.0)


def realtime_corrected_export(
    forecast_export_w, confidence, slot_dt, now_utc, actual_export_w
):
    """Blend live P1 into the near horizon; influence decays smoothly over 2 h."""
    hours = max(0.0, (slot_dt - now_utc).total_seconds() / 3600)
    if hours > 2.0:
        return forecast_export_w, 0.0
    recency = 1.0 - hours / 2.0
    live_weight = clamp(
        (1.0 - confidence) * recency + 0.35 * recency, 0.0, 0.85
    )
    corrected = (
        (1.0 - live_weight) * forecast_export_w + live_weight * actual_export_w
    )
    return max(0.0, corrected), live_weight


def enforce_min_run(selected, candidates, scores, required_slots):
    """Prefer WW runs of >=30 min without ever making WW infeasible."""
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
        neighbours = [
            x for x in (single - 1, single + 1)
            if 0 <= x < len(candidates) and x not in selected
        ]
        if not neighbours:
            continue
        best_add = max(neighbours, key=lambda x: scores[x])
        removable = [
            x for x in selected if x != single and abs(x - single) > 1
        ]
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

    common = [
        x for x in axis_slots
        if x in pv_map and x in q_map and x in b_map and x in weather_map
    ]
    if len(common) != 96:
        raise SystemExit(
            f"FAIL: dynamic planner aligned slots={len(common)}, expected 96"
        )

    now_utc = datetime.now(timezone.utc)
    today_local = now_utc.astimezone(TZ).date().isoformat()
    grid = energy_state.get("grid") or {}
    actual_export_w = max(0.0, float(grid.get("export_w") or 0))

    previous_pv = confidence_state.get("previousPvForecast") or {}
    local_accuracy = recent_local_accuracy(
        now_utc, pv_map, energy_state, confidence_state
    )
    weather_slots = [weather_map[x] for x in common]

    tesla_state = energy_state.get("tesla") or {}
    tesla_connected_now = tesla_state.get("connected") is True
    tesla_charging_now = tesla_state.get("charging") is True

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
            (
                W_CONSISTENCY * consistency
                + W_CLOUD_STABILITY * stability
                + W_LOCAL_ACCURACY * local_accuracy
            )
            * horizon_factor(slot_dt, now_utc)
        )
        corrected_export, live_weight = realtime_corrected_export(
            forecast_export, confidence, slot_dt, now_utc, actual_export_w
        )

        expected_home = expected_tesla_home(local_dt)

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
            "teslaAvailableForecast": tesla_connected_now,
            "teslaOpportunityConnected": tesla_connected_now,
            "teslaAvailabilitySource": (
                "LIVE_CONNECTED_CURRENT_STATE"
                if tesla_connected_now else "NOT_CONNECTED"
            ),
            "teslaExpectedHome": expected_home,
            "teslaConnectedNow": tesla_connected_now,
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
            goal_reached = (
                ww.get("goalReachedToday") is True
                or ww.get("goalReached") is True
            )
            remaining_min = (
                0 if goal_reached
                else max(0, int(ww.get("remainingFallbackMin") or 0))
            )
            catchup = ww.get("catchupRequired") is True

        deadline = deadline_utc(date_key)
        candidates = [
            s for s in day_slots
            if parse_utc(s["slot_start_utc"]) < deadline
            and parse_utc(s["slot_start_utc"]) >= now_utc - timedelta(minutes=15)
        ]
        required_slots = (
            int(math.ceil(remaining_min / SLOT_MIN)) if not goal_reached else 0
        )
        required_slots = min(required_slots, len(candidates))

        max_export = max(
            (float(s["correctedExportBeforeFlexW"]) for s in candidates),
            default=0.0,
        )
        scores = []
        for pos, s in enumerate(candidates):
            export_w = float(s["correctedExportBeforeFlexW"])
            ww_capture = min(BOILER_W, export_w)
            confidence = float(s["confidence"])
            peak_share = (export_w / max_export) if max_export > 0 else 0.0
            tesla_peak_penalty = (
                min(BOILER_W, export_w) * peak_share
                if tesla_connected_now else 0.0
            )
            position = pos / max(1, len(candidates) - 1)
            urgency = 350.0 * position * (1.0 if catchup else 0.35)
            score = (
                ww_capture * (0.65 + 0.35 * confidence)
                - 0.55 * tesla_peak_penalty
                + urgency
            )
            scores.append(score)

        ranked = sorted(
            range(len(candidates)),
            key=lambda i: (scores[i], candidates[i]["slot_start_utc"]),
            reverse=True,
        )
        selected = set(ranked[:required_slots])
        selected = enforce_min_run(
            selected, candidates, scores, required_slots
        )

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

    for s in raw_slots:
        ww_w = BOILER_W if s["slot_start_utc"] in ww_selected_ts else 0
        residual_after_ww = max(
            0.0, float(s["correctedExportBeforeFlexW"]) - ww_w
        )
        s["wwPlanW"] = ww_w
        s["wwAllocationReason"] = (
            "DYNAMIC_COMFORT_PV_SLOT" if ww_w else "HOLD"
        )
        s["evResidualExportW"] = round(residual_after_ww)

    qualified_windows = apply_best_windows_first(qualify_ev_windows(raw_slots))
    selected_by_index = {}
    all_by_index = {}
    for window_id, window in enumerate(qualified_windows, start=1):
        window["id"] = window_id
        for i in window["indices"]:
            all_by_index[i] = window
            if window["selected"]:
                selected_by_index[i] = window

    slots = []
    for i, s in enumerate(raw_slots):
        ev_w = 0
        ev_reason = (
            "NOT_CONNECTED"
            if not s["teslaOpportunityConnected"]
            else "NO_QUALIFIED_PV_WINDOW"
        )
        window_id = None
        window_coverage = None
        window_class = None
        selection_reason = None
        future_better_kwh = None

        window = all_by_index.get(i)
        if window is not None:
            window_id = window["id"]
            window_coverage = window["displayCoverage"]
            window_class = window["class"]
            selection_reason = window["selectionReason"]
            future_better_kwh = window["futureBetterPvCaptureKWh"]

            if i in selected_by_index:
                ev_w = ev_target_from_residual(s["evResidualExportW"])
                if s["evResidualExportW"] >= ev_w:
                    ev_reason = "DYNAMIC_PV_PEAK_ABSORBER"
                elif window["class"] == "SECONDARY":
                    ev_reason = "DYNAMIC_PV_SECONDARY_OPPORTUNITY"
                else:
                    ev_reason = "DYNAMIC_PV_MIXED_OPPORTUNITY"
            else:
                ev_reason = "DEFERRED_TO_LATER_BETTER_PV"

        net_after = (
            float(s["baseLoadForecastW"])
            + float(s["quattForecastW"])
            + float(s["wwPlanW"])
            + ev_w
            - float(s["pvForecastW"])
        )
        slots.append({
            **s,
            "evPlanW": round(ev_w),
            "evPlanA": round(ev_w / EV_W_PER_A) if ev_w else 0,
            "evAllocationReason": ev_reason,
            "evOpportunityWindowId": window_id,
            "evOpportunityWindowClass": window_class,
            "evOpportunityWindowSelectionReason": selection_reason,
            "evOpportunityWindowPvCoverage": (
                round(window_coverage, 3)
                if window_coverage is not None else None
            ),
            "evFutureBetterPvCaptureKWh": (
                round(future_better_kwh, 3)
                if future_better_kwh is not None else None
            ),
            "gridImportAfterFlexW": round(max(0.0, net_after)),
            "gridExportAfterFlexW": round(max(0.0, -net_after)),
        })

    payload = {
        "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.2",
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
            "evOpportunityWindowMinMinutes": EV_MIN_WINDOW_SLOTS * SLOT_MIN,
            "evOpportunityMinPvCoverage": EV_MIN_WINDOW_PV_COVERAGE,
            "evStableRunA": EV_RUN_MIN_A,
            "evKickstartA": EV_KICKSTART_A,
            "realtimeP1Correction": True,
        },
        "confidenceModel": {
            "signals": [
                "forecastConsistency", "cloudStability", "recentLocalAccuracy"
            ],
            "weights": {
                "forecastConsistency": W_CONSISTENCY,
                "cloudStability": W_CLOUD_STABILITY,
                "recentLocalAccuracy": W_LOCAL_ACCURACY,
            },
            "horizonPolicy": "MILD_PRIOR_ONLY_MAX_8_PERCENT_24H",
        },
        "tesla": {
            "connectedNow": tesla_connected_now,
            "chargingNow": tesla_charging_now,
            "availabilityPolicy": (
                "LIVE_CONNECTED_CURRENT_STATE_ONLY;"
                "WEEKLY_FORECAST_INFORMATIONAL"
            ),
            "opportunityPolicy": (
                "BEST_PV_WINDOWS_FIRST_AFTER_WW_"
                "MIN30M_MIN50PCT_AT_RUN6A"
            ),
            "qualifiedWindows": [
                {
                    "id": w["id"],
                    "start": w["start"],
                    "end": w["end"],
                    "class": w["class"],
                    "pvCoverage": round(w["displayCoverage"], 3),
                    "selected": w["selected"],
                    "selectionReason": w["selectionReason"],
                    "pvCaptureKWhAt6A": round(w["pvCaptureKWhAt6A"], 3),
                }
                for w in qualified_windows
            ],
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
        "previousPvForecast": {
            ts: round(pv_power(pv_map[ts])) for ts in common
        },
    }
    tmp_state = CONFIDENCE_STATE.with_suffix(".tmp")
    tmp_state.write_text(json.dumps(state_payload, separators=(",", ":")) + "\n")
    tmp_state.replace(CONFIDENCE_STATE)

    before_export_kwh = (
        sum(float(x["correctedExportBeforeFlexW"]) for x in slots)
        * SLOT_H / 1000
    )
    after_export_kwh = (
        sum(float(x["gridExportAfterFlexW"]) for x in slots)
        * SLOT_H / 1000
    )
    ww_kwh = sum(float(x["wwPlanW"]) for x in slots) * SLOT_H / 1000
    ev_kwh = sum(float(x["evPlanW"]) for x in slots) * SLOT_H / 1000

    print("PASS: dynamic shadow planner v0.2 built")
    print("slots                    :", len(slots))
    print("WW planned kWh           :", round(ww_kwh, 2))
    print("Tesla planned kWh        :", round(ev_kwh, 2))
    print("qualified EV windows     :", len(qualified_windows))
    print("corrected export before  :", round(before_export_kwh, 2))
    print("forecast export after    :", round(after_export_kwh, 2))
    print("recent local accuracy    :", round(local_accuracy, 3))
    print("output                   :", OUTPUT)


if __name__ == "__main__":
    main()

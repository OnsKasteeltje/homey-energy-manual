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
PV_MULTIDAY_FILE = Path("/home/jeroen/ems/data/pv-forecast-multiday.json")
BASE_MULTIDAY_FILE = Path("/home/jeroen/ems/data/base-load-forecast-multiday.json")
WW_INPUT_FILE = Path("/home/jeroen/ems/data/ww-input.json")
AXIS_FILE = Path("/home/jeroen/ems/data/planner-axis.json")
ENERGY_STATE_FILE = Path(
    "/home/jeroen/ems/data/energy-state-v2.json"
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
WW_SHOULDER_MIN_COVERAGE = 0.75
WW_SHOULDER_MAX_IMPORT_W = 500
WW_SHOULDER_BONUS_W = 350
WW_IMPORT_PENALTY = 0.75
WW_EV_OPPORTUNITY_COST_WEIGHT = 1.0

EV_W_PER_A = 690
EV_KICKSTART_A = 7
EV_RUN_MIN_A = 6
EV_MAX_A = 16
EV_RUN_MIN_W = EV_RUN_MIN_A * EV_W_PER_A
EV_MIN_WINDOW_SLOTS = 2
EV_MIN_WINDOW_PV_COVERAGE = 0.0
EV_SECONDARY_COVERAGE = 0.75
EV_PURE_COVERAGE = 1.00
EV_IMPORT_PENALTY = 0.75

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
    """Find contiguous *profitable* EV windows after WW reservation.

    Qualification is deliberately performed per slot before grouping. Weak
    positive residual-export shoulders are boundaries, not members of a large
    average window. This prevents e.g. 100..400 W shoulder slots from diluting
    a 2.5..4 kW central PV peak. A resulting profitable run must still span at
    least EV_MIN_WINDOW_SLOTS (30 min) to preserve anti-flapping behaviour.
    """
    windows = []
    current = []

    def finish(indices):
        if len(indices) < EV_MIN_WINDOW_SLOTS:
            return

        residual_sum_w = sum(candidates[i]["evResidualExportW"] for i in indices)
        min_ev_sum_w = EV_RUN_MIN_W * len(indices)
        raw_coverage = residual_sum_w / min_ev_sum_w if min_ev_sum_w else 0.0

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
        eligible = (
            slot["teslaOpportunityConnected"]
            and float(slot.get("evMarginalTargetCandidateW") or 0) > 0
        )
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
    """Keep every economically positive PV window.

    Deferring a useful window to a later, theoretically better window caused
    avoidable export in shadow replay. Window quality is still reported, but
    selection is now driven by marginal PV benefit per slot.
    """
    for window in windows:
        window["futureBetterPvCaptureKWh"] = 0.0
        window["selected"] = True
        window["selectionReason"] = "MARGINAL_PV_BENEFIT_POSITIVE"
    return windows


def ev_best_option(residual_w):
    """Return best EV target and marginal value for a residual-PV level."""
    residual = max(0.0, float(residual_w))
    best_w = 0
    best_score = 0.0
    for amps in range(EV_RUN_MIN_A, EV_MAX_A + 1):
        target_w = amps * EV_W_PER_A
        pv_capture_w = min(residual, target_w)
        import_w = max(0.0, target_w - residual)
        score = pv_capture_w - EV_IMPORT_PENALTY * import_w
        if score > best_score + 1e-9:
            best_score = score
            best_w = target_w
    return best_w, best_score


def ev_target_from_residual(residual_w):
    """Choose 0 or 6..16 A by marginal PV capture minus grid-import penalty."""
    best_w, _best_score = ev_best_option(residual_w)
    return best_w


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


def update_recent_export_history(confidence_state, now_utc, actual_export_w):
    history = confidence_state.get("recentP1ExportSamples") or []
    clean = []
    cutoff = now_utc - timedelta(minutes=45)
    for item in history:
        try:
            ts = parse_utc(item["ts"])
            value = max(0.0, float(item["exportW"]))
        except Exception:
            continue
        if ts >= cutoff:
            clean.append({"ts": item["ts"], "exportW": value})
    clean.append({
        "ts": now_utc.isoformat().replace("+00:00", "Z"),
        "exportW": max(0.0, float(actual_export_w)),
    })
    return clean[-3:]


def recent_export_baseline(samples, fallback):
    values = [max(0.0, float(x.get("exportW") or 0)) for x in samples]
    if not values:
        return max(0.0, float(fallback)), 0.0
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    trend = values[-1] - values[0] if len(values) >= 2 else 0.0
    baseline = max(0.0, median + 0.25 * trend)
    return baseline, trend


def realtime_corrected_export(
    forecast_export_w, confidence, stability, slot_dt, now_utc,
    actual_export_w, recent_export_samples
):
    """Adaptive near-horizon P1 correction.

    Uses the median/trend of the last ~45 minutes instead of one instantaneous
    sample. Live influence is reduced when clouds are unstable.
    """
    hours = max(0.0, (slot_dt - now_utc).total_seconds() / 3600)
    if hours > 2.0:
        return forecast_export_w, 0.0
    recency = 1.0 - hours / 2.0
    baseline, _trend = recent_export_baseline(recent_export_samples, actual_export_w)
    stability_factor = 0.45 + 0.55 * clamp(stability)
    live_weight = clamp(
        ((1.0 - confidence) * recency + 0.35 * recency) * stability_factor,
        0.0,
        0.85,
    )
    corrected = (
        (1.0 - live_weight) * forecast_export_w + live_weight * baseline
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
    pv_multiday_doc = load(PV_MULTIDAY_FILE, {})
    base_multiday_doc = load(BASE_MULTIDAY_FILE, {})
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

    pv_multiday_map = {
        stamp(x): x for x in pv_multiday_doc.get("slots", [])
        if stamp(x)
    }
    base_multiday_map = {
        stamp(x): x for x in base_multiday_doc.get("slots", [])
        if stamp(x)
    }

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
    recent_export_samples = update_recent_export_history(
        confidence_state, now_utc, actual_export_w
    )

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
            forecast_export,
            confidence,
            stability,
            slot_dt,
            now_utc,
            actual_export_w,
            recent_export_samples,
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

        # Keep the normal 24 h inputs for today.
        # For a future local date touched by the rolling 24 h action horizon,
        # evaluate the complete WW feasibility window using multiday PV/base.
        action_ts = {s["slot_start_utc"] for s in day_slots}
        lookahead_used = date_key != today_local

        if not lookahead_used:
            candidates = [
                s for s in day_slots
                if parse_utc(s["slot_start_utc"]) < deadline
                and parse_utc(s["slot_start_utc"]) >= now_utc - timedelta(minutes=15)
            ]
        else:
            candidates = []

            common_multiday = sorted(
                set(pv_multiday_map).intersection(base_multiday_map)
            )

            for ts in common_multiday:
                slot_dt = parse_utc(ts)
                local_dt = slot_dt.astimezone(TZ)

                if local_dt.date().isoformat() != date_key:
                    continue
                if slot_dt >= deadline:
                    continue
                if slot_dt < now_utc - timedelta(minutes=15):
                    continue

                pv_w = pv_power(pv_multiday_map[ts])
                base_w = max(
                    0.0,
                    float(
                        base_multiday_map[ts].get("baseLoadForecastW") or 0
                    ),
                )

                # TODO: multiday Quatt forecast.
                forecast_export = max(0.0, pv_w - base_w)

                candidates.append({
                    "slot_start_utc": ts,
                    "localDate": date_key,
                    "pvForecastW": round(pv_w),
                    "baseLoadForecastW": round(base_w),
                    "quattForecastW": 0,
                    "forecastExportBeforeFlexW": round(forecast_export),
                    "correctedExportBeforeFlexW": round(forecast_export),
                    "confidence": 0.70,
                    "lookaheadSource": "MULTIDAY_PV_BASE",
                })

        required_slots = (
            int(math.ceil(remaining_min / SLOT_MIN)) if not goal_reached else 0
        )
        required_slots = min(required_slots, len(candidates))

        scores = []
        for pos, s in enumerate(candidates):
            export_w = float(s["correctedExportBeforeFlexW"])
            ww_capture = min(BOILER_W, export_w)
            ww_grid_import = max(0.0, BOILER_W - export_w)
            ww_pv_coverage = clamp(export_w / BOILER_W) if BOILER_W else 0.0
            confidence = float(s["confidence"])

            ev_before_w = 0
            ev_before_score = 0.0
            ev_after_score = 0.0
            if tesla_connected_now:
                ev_before_w, ev_before_score = ev_best_option(export_w)
                _ev_after_w, ev_after_score = ev_best_option(
                    max(0.0, export_w - BOILER_W)
                )
            ev_opportunity_cost = max(0.0, ev_before_score - ev_after_score)

            shoulder_eligible = (
                ww_pv_coverage >= WW_SHOULDER_MIN_COVERAGE
                and ww_grid_import <= WW_SHOULDER_MAX_IMPORT_W
                and (not tesla_connected_now or ev_before_w == 0)
            )
            shoulder_bonus = (
                WW_SHOULDER_BONUS_W * confidence
                if shoulder_eligible else 0.0
            )

            position = pos / max(1, len(candidates) - 1)
            urgency = 350.0 * position * (1.0 if catchup else 0.35)
            future_good_slots = sum(
                1
                for later in candidates[pos + 1:]
                if float(later["correctedExportBeforeFlexW"]) >= BOILER_W * 0.50
            )
            scarcity = max(0, required_slots - future_good_slots)
            economical_start_pressure = (
                900.0 * min(1.0, scarcity / max(1, required_slots))
                if required_slots else 0.0
            )
            score = (
                ww_capture * (0.65 + 0.35 * confidence)
                - WW_IMPORT_PENALTY * ww_grid_import
                - WW_EV_OPPORTUNITY_COST_WEIGHT * ev_opportunity_cost
                + shoulder_bonus
                + urgency
                + economical_start_pressure
            )
            scores.append(score)

            # Persist transparent WW ranking diagnostics for replay/UI analysis.
            s["wwCandidateScore"] = round(score, 1)
            s["wwCandidatePvCoverage"] = round(ww_pv_coverage, 3)
            s["wwCandidateGridImportW"] = round(ww_grid_import)
            s["wwCandidateEvOpportunityCost"] = round(ev_opportunity_cost, 1)
            s["wwShoulderEligible"] = shoulder_eligible
            s["wwShoulderBonus"] = round(shoulder_bonus, 1)

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

        selected_ts = {
            candidates[i]["slot_start_utc"] for i in selected
        }

        published_ts = selected_ts.intersection(action_ts)
        deferred_ts = selected_ts.difference(action_ts)

        ww_selected_ts.update(published_ts)

        daily.append({
            "date": date_key,
            "goalReached": goal_reached,
            "remainingFallbackMin": remaining_min,
            "requiredSlots": required_slots,
            "allocatedSlots": len(selected),
            "publishedActionSlots": len(published_ts),
            "deferredLookaheadSlots": len(deferred_ts),
            "comfortFeasible": len(selected) >= required_slots,
            "deadlineLocal": "19:00",
            "dayBoundaryLocal": "24:00",
            "evaluationScope": (
                "MULTIDAY_LOOKAHEAD"
                if lookahead_used
                else "24H_ACTION_HORIZON"
            ),
            "lookaheadQuattIncluded": False if lookahead_used else True,
            "allocationPolicy": "DYNAMIC_PV_SHOULDER_WITH_EV_OPPORTUNITY_COST",
        })

    for s in raw_slots:
        ww_w = BOILER_W if s["slot_start_utc"] in ww_selected_ts else 0
        residual_after_ww = max(
            0.0, float(s["correctedExportBeforeFlexW"]) - ww_w
        )
        s["wwPlanW"] = ww_w
        if ww_w:
            s["wwAllocationReason"] = (
                "DYNAMIC_WW_PV_SHOULDER"
                if s.get("wwShoulderEligible") is True
                else "DYNAMIC_COMFORT_PV_SLOT"
            )
        else:
            s["wwAllocationReason"] = "HOLD"
        s["evResidualExportW"] = round(residual_after_ww)
        s["evMarginalTargetCandidateW"] = ev_target_from_residual(
            residual_after_ww
        )
        s["evMarginalEligible"] = s["evMarginalTargetCandidateW"] > 0

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
                ev_w = int(s.get("evMarginalTargetCandidateW") or 0)
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
        "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
        "generated_at": now_utc.isoformat().replace("+00:00", "Z"),
        "mode": "PURE_SHADOW",
        "readOnly": True,
        "control_writes": False,
        "objective": "MAXIMIZE_PV_SELF_CONSUMPTION_SUBJECT_TO_WW_COMFORT",
        "horizons": {
            "actionSlots": len(raw_slots),
            "actionHours": len(raw_slots) * SLOT_H,
            "futureDayEvaluation": "MULTIDAY_FORECAST",
            "wwFeasibilityDeadlineLocal": "19:00",
            "localDayBoundary": "24:00",
            "multidayPvSource": str(PV_MULTIDAY_FILE),
            "multidayBaseLoadSource": str(BASE_MULTIDAY_FILE),
            "multidayQuattIncluded": False,
        },
        "guardrails": {
            "wwComfortHardConstraint": True,
            "wwDeadlineLocal": "19:00",
            "wwMinRunMinutes": WW_MIN_RUN_SLOTS * SLOT_MIN,
            "wwShoulderMinPvCoverage": WW_SHOULDER_MIN_COVERAGE,
            "wwShoulderMaxImportW": WW_SHOULDER_MAX_IMPORT_W,
            "wwShoulderBonusW": WW_SHOULDER_BONUS_W,
            "wwImportPenalty": WW_IMPORT_PENALTY,
            "wwEvOpportunityCostWeight": WW_EV_OPPORTUNITY_COST_WEIGHT,
            "teslaRole": "SECONDARY_FLEX_LOAD_WHEN_WW_COMFORT_REMAINS_FEASIBLE",
            "fixedPvStartThresholdW": None,
            "evOpportunityWindowMinMinutes": EV_MIN_WINDOW_SLOTS * SLOT_MIN,
            "evOpportunityMinPvCoverage": EV_MIN_WINDOW_PV_COVERAGE,
            "evMarginalImportPenalty": EV_IMPORT_PENALTY,
            "evWindowSegmentation": "CONTIGUOUS_POSITIVE_MARGINAL_VALUE_SLOTS",
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
                "PROFITABLE_SUBWINDOWS_AFTER_WW_MIN30M_RUN6A_TO16A"
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
            "recentP1ExportSamples": recent_export_samples,
            "p1CorrectionPolicy": "MEDIAN_TREND_CLOUD_STABILITY_ADAPTIVE",
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
        "recentP1ExportSamples": recent_export_samples,
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

    print("PASS: dynamic shadow planner v0.4-performance built")
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

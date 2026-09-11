#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime

TARGET = Path('/home/jeroen/ems/runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py')
BACKUP = TARGET.with_suffix('.py.pre-v04')

text = TARGET.read_text()
original = text


def replace_once(old, new, label):
    global text
    if old not in text:
        raise SystemExit(f'FAIL: patch anchor not found: {label}')
    if text.count(old) != 1:
        raise SystemExit(f'FAIL: patch anchor not unique: {label} ({text.count(old)})')
    text = text.replace(old, new, 1)

# 1) EV: switch from coarse whole-window 50% gate to per-slot marginal PV benefit.
replace_once(
'''EV_MIN_WINDOW_SLOTS = 2
EV_MIN_WINDOW_PV_COVERAGE = 0.50
EV_SECONDARY_COVERAGE = 0.75
EV_PURE_COVERAGE = 1.00
''',
'''EV_MIN_WINDOW_SLOTS = 2
EV_MIN_WINDOW_PV_COVERAGE = 0.0
EV_SECONDARY_COVERAGE = 0.75
EV_PURE_COVERAGE = 1.00
EV_IMPORT_PENALTY = 0.75
''',
'EV constants')

replace_once(
'''        raw_coverage = residual_sum_w / min_ev_sum_w if min_ev_sum_w else 0.0
        if raw_coverage < EV_MIN_WINDOW_PV_COVERAGE:
            return

        pv_capture_kwh = sum(
''',
'''        raw_coverage = residual_sum_w / min_ev_sum_w if min_ev_sum_w else 0.0

        pv_capture_kwh = sum(
''',
'EV hard coverage gate')

replace_once(
'''        eligible = slot["teslaOpportunityConnected"] and slot["evResidualExportW"] > 0
''',
'''        eligible = (
            slot["teslaOpportunityConnected"]
            and ev_target_from_residual(slot["evResidualExportW"]) > 0
        )
''',
'EV eligible rule')

start = text.index('def apply_best_windows_first(windows):')
end = text.index('\n\ndef ev_target_from_residual', start)
text = text[:start] + '''def apply_best_windows_first(windows):
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
''' + text[end:]

start = text.index('def ev_target_from_residual(residual_w):')
end = text.index('\n\ndef deadline_utc', start)
text = text[:start] + '''def ev_target_from_residual(residual_w):
    """Choose 0 or 6..16 A by marginal PV capture minus grid-import penalty."""
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
    return best_w
''' + text[end:]

# 2) P1 correction: retain last 3 planner-run export samples and reduce live weight in unstable cloud regimes.
insert_after = '''def horizon_factor(slot_dt, now_utc):
    hours = max(0.0, (slot_dt - now_utc).total_seconds() / 3600)
    return 1.0 - 0.08 * min(1.0, hours / 24.0)
'''
replace_once(insert_after, insert_after + '''\n\ndef update_recent_export_history(confidence_state, now_utc, actual_export_w):
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
''', 'P1 history helpers')

start = text.index('def realtime_corrected_export(')
end = text.index('\n\ndef enforce_min_run', start)
text = text[:start] + '''def realtime_corrected_export(
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
''' + text[end:]

replace_once(
'''    actual_export_w = max(0.0, float(grid.get("export_w") or 0))

    previous_pv = confidence_state.get("previousPvForecast") or {}
''',
'''    actual_export_w = max(0.0, float(grid.get("export_w") or 0))
    recent_export_samples = update_recent_export_history(
        confidence_state, now_utc, actual_export_w
    )

    previous_pv = confidence_state.get("previousPvForecast") or {}
''',
'P1 history init')

replace_once(
'''        corrected_export, live_weight = realtime_corrected_export(
            forecast_export, confidence, slot_dt, now_utc, actual_export_w
        )
''',
'''        corrected_export, live_weight = realtime_corrected_export(
            forecast_export,
            confidence,
            stability,
            slot_dt,
            now_utc,
            actual_export_w,
            recent_export_samples,
        )
''',
'P1 adaptive call')

# 3) WW: add latest-economical-start scarcity pressure so rolling replans do not keep waiting until deadline.
replace_once(
'''            position = pos / max(1, len(candidates) - 1)
            urgency = 350.0 * position * (1.0 if catchup else 0.35)
            score = (
                ww_capture * (0.65 + 0.35 * confidence)
                - 0.55 * tesla_peak_penalty
                + urgency
            )
''',
'''            position = pos / max(1, len(candidates) - 1)
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
                - 0.55 * tesla_peak_penalty
                + urgency
                + economical_start_pressure
            )
''',
'WW economical-start pressure')

replace_once(
'''            "allocationPolicy": "DYNAMIC_PV_CAPTURE_WITH_TESLA_PEAK_SHAPING",
''',
'''            "allocationPolicy": "DYNAMIC_PV_CAPTURE_WITH_LATEST_ECONOMICAL_START",
''',
'WW policy label')

replace_once(
'''            "evOpportunityMinPvCoverage": EV_MIN_WINDOW_PV_COVERAGE,
''',
'''            "evOpportunityMinPvCoverage": EV_MIN_WINDOW_PV_COVERAGE,
            "evMarginalImportPenalty": EV_IMPORT_PENALTY,
''',
'guardrail EV penalty')

replace_once(
'''            "opportunityPolicy": (
                "BEST_PV_WINDOWS_FIRST_AFTER_WW_"
                "MIN30M_MIN50PCT_AT_RUN6A"
            ),
''',
'''            "opportunityPolicy": (
                "MARGINAL_PV_BENEFIT_AFTER_WW_MIN30M_RUN6A_TO16A"
            ),
''',
'opportunity policy label')

replace_once(
'''        "realtime": {
            "actualP1ExportW": round(actual_export_w),
            "recentLocalAccuracy": round(local_accuracy, 3),
        },
''',
'''        "realtime": {
            "actualP1ExportW": round(actual_export_w),
            "recentLocalAccuracy": round(local_accuracy, 3),
            "recentP1ExportSamples": recent_export_samples,
            "p1CorrectionPolicy": "MEDIAN_TREND_CLOUD_STABILITY_ADAPTIVE",
        },
''',
'payload realtime')

replace_once(
'''        "previousPvForecast": {
            ts: round(pv_power(pv_map[ts])) for ts in common
        },
''',
'''        "previousPvForecast": {
            ts: round(pv_power(pv_map[ts])) for ts in common
        },
        "recentP1ExportSamples": recent_export_samples,
''',
'confidence state P1 history')

replace_once(
'''    print("PASS: dynamic shadow planner v0.2 built")
''',
'''    print("PASS: dynamic shadow planner v0.4-performance built")
''',
'PASS label')

if text == original:
    raise SystemExit('FAIL: no changes produced')

if not BACKUP.exists():
    BACKUP.write_text(original)

TARGET.write_text(text)
print('PASS: runtime planner patched to v0.4-performance')
print('target :', TARGET)
print('backup :', BACKUP)

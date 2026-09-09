#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PV_FILE = Path("/home/jeroen/ems/data/pv-forecast.json")
QUATT_FILE = Path("/home/jeroen/ems/data/quatt-forecast.json")
BASE_FILE = Path("/home/jeroen/ems/data/base-load-forecast.json")
WW_FILE = Path("/home/jeroen/ems/data/ww-plan.json")
PRICE_FILE = Path("/home/jeroen/ems/data/price-forecast.json")
AXIS_FILE = Path("/home/jeroen/ems/data/planner-axis.json")
ENERGY_STATE_FILE = Path("/home/jeroen/ems/repo/homey-energy-manual/docs/data/energy-state-v2.json")
OUTPUT = Path("/home/jeroen/ems/data/shadow-load-plan.json")

TZ = ZoneInfo("Europe/Amsterdam")
EV_W_PER_A = 690
EV_KICKSTART_A = 7
EV_RUN_MIN_A = 6
EV_MAX_A = 16
EV_RUN_MIN_W = EV_RUN_MIN_A * EV_W_PER_A
EV_MIN_WINDOW_SLOTS = 2
EV_MIN_WINDOW_PV_COVERAGE = 0.50
EV_SECONDARY_COVERAGE = 0.75
EV_PURE_COVERAGE = 1.00
SLOT_H = 0.25


def load(path):
    return json.loads(path.read_text())


def timestamp(slot):
    ts = slot.get("slot_start_utc") or slot.get("start") or slot.get("startAt")
    if ts and ts.endswith(".000Z"):
        ts = ts[:-5] + "Z"
    return ts


def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def pv_power(slot):
    for key in ("pvForecastW", "pv_forecast_w", "power_w", "forecast_w"):
        if slot.get(key) is not None:
            return float(slot[key])
    raise ValueError("PV power field missing")


def expected_tesla_home(local_dt):
    # Informational weekly presence forecast only. Opportunity allocation itself
    # is gated by the actual live-connected state.
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
    ).total_seconds() == 15 * 60


def opportunity_class(coverage):
    if coverage >= EV_PURE_COVERAGE:
        return "PURE_PV"
    if coverage >= EV_SECONDARY_COVERAGE:
        return "SECONDARY"
    return "FALLBACK_MIXED"


def qualify_ev_windows(candidates):
    """Find contiguous residual-PV windows after WW comfort reservation.

    Stable planning uses 6 A. The 7 A value is only an actuator kickstart.
    A window must last at least 30 minutes and provide at least 50% of 6 A
    charging energy from residual PV over the complete window.
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
    """Suppress weaker early windows when later better PV can replace them.

    There is no opportunity-energy/SOC budget yet, so the planner uses PV capture
    capacity as the conservative substitution budget. An earlier weaker window is
    deferred only when later higher-class windows can capture at least the same PV
    energy at the stable 6 A operating point. If later better capacity is smaller,
    the weaker window remains eligible so autumn/winter PV is not discarded.
    """
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
    """Plan stable charging at >=6 A inside a selected opportunity window."""
    amps_from_pv = int(max(0.0, residual_w) // EV_W_PER_A)
    amps = max(EV_RUN_MIN_A, amps_from_pv)
    amps = min(EV_MAX_A, amps)
    return amps * EV_W_PER_A


pv = load(PV_FILE)
quatt = load(QUATT_FILE)
base = load(BASE_FILE)
ww = load(WW_FILE)
price = load(PRICE_FILE) if PRICE_FILE.exists() else {"slots": []}
axis = load(AXIS_FILE)
energy_state = load(ENERGY_STATE_FILE) if ENERGY_STATE_FILE.exists() else {}

tesla_state = energy_state.get("tesla") or {}
tesla_connected_now = tesla_state.get("connected") is True
tesla_charging_now = tesla_state.get("charging") is True

pv_map = {timestamp(s): s for s in pv.get("slots", [])}
q_map = {timestamp(s): s for s in quatt.get("slots", [])}
b_map = {timestamp(s): s for s in base.get("slots", [])}
ww_map = {timestamp(s): s for s in ww.get("slots", [])}
price_map = {timestamp(s): s for s in price.get("slots", [])}

axis_slots = axis.get("slots", [])
if len(axis_slots) != 96:
    raise SystemExit(f"FAIL: planner axis expected 96 slots, got {len(axis_slots)}")

sources = {"PV": pv_map, "Quatt": q_map, "Base": b_map, "WW": ww_map}
for name, source_map in sources.items():
    source_slots = sorted(source_map)
    if source_slots != sorted(axis_slots):
        missing = sorted(set(axis_slots) - set(source_slots))
        extra = sorted(set(source_slots) - set(axis_slots))
        raise SystemExit(
            f"FAIL: {name} axis mismatch; missing={missing[:3]} extra={extra[:3]}"
        )

common = sorted(set(pv_map) & set(q_map) & set(b_map) & set(ww_map))
if len(common) != 96:
    raise SystemExit(f"FAIL: expected 96 aligned energy slots, got {len(common)}")

price_missing = sorted(set(axis_slots) - set(price_map))
price_extra = sorted(set(price_map) - set(axis_slots))
if price_missing or price_extra:
    print(
        "WARN: Price axis mismatch ignored for FIXED contract; "
        f"missing={price_missing[:3]} extra={price_extra[:3]}"
    )

# First pass: WW/comfort is already reserved. Compute residual PV available to
# lower-priority EV opportunity charging. Actual connection gates opportunity;
# the weekly home forecast is retained as informational metadata only.
slots = []
for ts in common:
    p = pv_map[ts]
    q = q_map[ts]
    b = b_map[ts]
    w = ww_map[ts]
    pr = price_map.get(ts) or {}

    pv_w = max(0.0, pv_power(p))
    quatt_w = max(0.0, float(q.get("quattForecastW") or 0))
    base_w = max(0.0, float(b.get("baseLoadForecastW") or 0))
    ww_w = max(0.0, float(w.get("wwPlanW") or 0))
    non_controllable = base_w + quatt_w
    net_before = non_controllable - pv_w
    surplus_before = max(0.0, -net_before)
    net_after_ww = non_controllable + ww_w - pv_w
    residual_after_ww = max(0.0, -net_after_ww)

    slot_dt = parse_utc(ts)
    local_dt = slot_dt.astimezone(TZ)
    expected_home = expected_tesla_home(local_dt)
    tesla_available = tesla_connected_now
    availability_source = (
        "LIVE_CONNECTED_CURRENT_STATE"
        if tesla_connected_now
        else "NOT_CONNECTED"
    )

    slots.append({
        "slot_start_utc": ts,
        "baseLoadForecastW": round(base_w),
        "baseLoadQuality": b.get("forecastQuality"),
        "quattForecastW": round(quatt_w),
        "heatingDemandGate": q.get("heatingDemandGate"),
        "pvForecastW": round(pv_w),
        "totalNonControllableLoadW": round(non_controllable),
        "netBeforeFlexW": round(net_before),
        "gridImportBeforeFlexW": round(max(0.0, net_before)),
        "gridExportBeforeFlexW": round(surplus_before),
        "wwPlanW": round(ww_w),
        "wwAllocationReason": w.get("allocationReason"),
        "netAfterWWW": round(net_after_ww),
        "gridImportAfterWWW": round(max(0.0, net_after_ww)),
        "gridExportAfterWWW": round(residual_after_ww),
        "evResidualExportW": round(residual_after_ww),
        "teslaAvailableForecast": tesla_available,
        "teslaOpportunityConnected": tesla_connected_now,
        "teslaAvailabilitySource": availability_source,
        "teslaExpectedHome": expected_home,
        "teslaConnectedNow": tesla_connected_now,
        "price_eur_kwh": pr.get("marketPriceEurPerKwh"),
    })

qualified_windows = apply_best_windows_first(qualify_ev_windows(slots))
selected_by_index = {}
all_by_index = {}
for window_id, window in enumerate(qualified_windows, start=1):
    window["id"] = window_id
    for i in window["indices"]:
        all_by_index[i] = window
        if window["selected"]:
            selected_by_index[i] = window

# Second pass: only selected windows receive EV opportunity allocation.
for i, slot in enumerate(slots):
    ev_w = 0
    ev_reason = (
        "NOT_CONNECTED"
        if not slot["teslaOpportunityConnected"]
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
            ev_w = ev_target_from_residual(slot["evResidualExportW"])
            if slot["evResidualExportW"] >= ev_w:
                ev_reason = "PV_EXPORT_OPPORTUNITY"
            elif window["class"] == "SECONDARY":
                ev_reason = "PV_SECONDARY_OPPORTUNITY"
            else:
                ev_reason = "PV_MIXED_OPPORTUNITY"
        else:
            ev_reason = "DEFERRED_TO_LATER_BETTER_PV"

    non_controllable = float(slot["totalNonControllableLoadW"])
    pv_w = float(slot["pvForecastW"])
    ww_w = float(slot["wwPlanW"])
    net_after_ev = non_controllable + ev_w - pv_w
    net_after_flex = non_controllable + ww_w + ev_w - pv_w

    slot.update({
        "evPlanW": round(ev_w),
        "evPlanA": round(ev_w / EV_W_PER_A) if ev_w else 0,
        "evAllocationReason": ev_reason,
        "evOpportunityWindowId": window_id,
        "evOpportunityWindowClass": window_class,
        "evOpportunityWindowSelectionReason": selection_reason,
        "evOpportunityWindowPvCoverage": (
            round(window_coverage, 3) if window_coverage is not None else None
        ),
        "evFutureBetterPvCaptureKWh": (
            round(future_better_kwh, 3) if future_better_kwh is not None else None
        ),
        "netAfterEVW": round(net_after_ev),
        "gridImportAfterEVW": round(max(0.0, net_after_ev)),
        "gridExportAfterEVW": round(max(0.0, -net_after_ev)),
        "netAfterFlexW": round(net_after_flex),
        "gridImportAfterFlexW": round(max(0.0, net_after_flex)),
        "gridExportAfterFlexW": round(max(0.0, -net_after_flex)),
    })

payload = {
    "schema": "EMS_PI_SHADOW_LOAD_PLAN_V0.7",
    "mode": "shadow",
    "control_writes": False,
    "composition": {
        "nonControllableLoad": "baseLoadForecastW + quattForecastW",
        "netBeforeFlex": "totalNonControllableLoadW - pvForecastW",
        "wwPriority": "COMFORT_RESERVED_BEFORE_EV_OPPORTUNITY",
        "netAfterWW": "totalNonControllableLoadW + wwPlanW - pvForecastW",
        "netAfterEV": "totalNonControllableLoadW + evPlanW - pvForecastW",
        "netAfterFlex": "totalNonControllableLoadW + wwPlanW + evPlanW - pvForecastW",
        "quattControl": "OBSERVE_ONLY_FORECAST",
        "wwControl": "SHADOW_PLAN_ONLY",
        "teslaControl": "SHADOW_OPPORTUNITY_ONLY",
        "teslaAvailabilityPolicy": "LIVE_CONNECTED_CURRENT_STATE_ONLY;WEEKLY_FORECAST_INFORMATIONAL",
        "teslaOpportunityPolicy": "BEST_PV_WINDOWS_FIRST_AFTER_WW_MIN30M_MIN50PCT_AT_RUN6A",
        "teslaWeakWindowGuard": "DEFER_IF_LATER_HIGHER_CLASS_PV_CAPTURE_CAN_REPLACE_WINDOW",
        "teslaKickstartPolicy": "7A_ACTUATOR_KICKSTART_ONLY_NOT_PLANNER_THRESHOLD",
        "teslaDeadlinePolicy": "SEPARATE_HIGHER_PRIORITY_REQUIREMENT_NOT_INCLUDED_IN_THIS_SHADOW_BUILDER",
        "pricePolicy": "REFERENCE_ONLY_FAIL_SOFT_FOR_FIXED_CONTRACT",
    },
    "tesla": {
        "connectedNow": tesla_connected_now,
        "chargingNow": tesla_charging_now,
        "kickstartA": EV_KICKSTART_A,
        "kickstartPlannerThreshold": False,
        "runMinA": EV_RUN_MIN_A,
        "maxA": EV_MAX_A,
        "wattsPerAmp": EV_W_PER_A,
        "minOpportunityWindowMinutes": EV_MIN_WINDOW_SLOTS * 15,
        "minOpportunityWindowPvCoverage": EV_MIN_WINDOW_PV_COVERAGE,
        "secondaryCoverageThreshold": EV_SECONDARY_COVERAGE,
        "purePvCoverageThreshold": EV_PURE_COVERAGE,
        "qualifiedOpportunityWindows": len(qualified_windows),
        "selectedOpportunityWindows": sum(1 for x in qualified_windows if x["selected"]),
        "deadlinePlanningIncluded": False,
    },
    "evOpportunityWindows": [
        {
            "id": x["id"],
            "start": x["start"],
            "end": x["end"],
            "class": x["class"],
            "pvCoverage": round(x["displayCoverage"], 3),
            "pvCaptureKWhAt6A": round(x["pvCaptureKWhAt6A"], 3),
            "futureBetterPvCaptureKWh": round(x["futureBetterPvCaptureKWh"], 3),
            "selected": x["selected"],
            "selectionReason": x["selectionReason"],
        }
        for x in qualified_windows
    ],
    "price": {
        "referenceOnly": True,
        "missingAxisSlots": len(price_missing),
        "extraAxisSlots": len(price_extra),
    },
    "slot_count": len(slots),
    "slots": slots,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
tmp.replace(OUTPUT)


def energy(field):
    return sum(x[field] for x in slots) * SLOT_H / 1000


base_kwh = energy("baseLoadForecastW")
quatt_kwh = energy("quattForecastW")
pv_kwh = energy("pvForecastW")
ev_kwh = energy("evPlanW")
ww_kwh = energy("wwPlanW")
imp_before = energy("gridImportBeforeFlexW")
exp_before = energy("gridExportBeforeFlexW")
imp_after = energy("gridImportAfterFlexW")
exp_after = energy("gridExportAfterFlexW")

print("PASS: shadow load plan v0.7 built")
print("slots                    :", len(slots))
print("base load kWh            :", round(base_kwh, 2))
print("Quatt kWh                :", round(quatt_kwh, 2))
print("PV kWh                   :", round(pv_kwh, 2))
print("Tesla opportunity kWh    :", round(ev_kwh, 2))
print("Tesla opportunity slots  :", sum(1 for x in slots if x["evPlanW"] > 0))
print("Tesla qualified windows  :", len(qualified_windows))
print("Tesla selected windows   :", sum(1 for x in qualified_windows if x["selected"]))
print("WW planned kWh           :", round(ww_kwh, 2))
print("grid import before flex  :", round(imp_before, 2))
print("grid export before flex  :", round(exp_before, 2))
print("grid import after flex   :", round(imp_after, 2))
print("grid export after flex   :", round(exp_after, 2))
print("price missing slots      :", len(price_missing))
print("output                   :", OUTPUT)

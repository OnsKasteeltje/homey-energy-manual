#!/usr/bin/env python3

import json
from datetime import datetime
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
EV_START_MIN_A = 7
EV_RUN_MIN_A = 6
EV_MAX_A = 16
EV_START_MIN_W = EV_START_MIN_A * EV_W_PER_A


def load(path):
    return json.loads(path.read_text())


def timestamp(slot):
    ts = (
        slot.get("slot_start_utc")
        or slot.get("start")
        or slot.get("startAt")
    )
    if ts and ts.endswith(".000Z"):
        ts = ts[:-5] + "Z"
    return ts


def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def pv_power(slot):
    for key in (
        "pvForecastW",
        "pv_forecast_w",
        "power_w",
        "forecast_w",
    ):
        if slot.get(key) is not None:
            return float(slot[key])
    raise ValueError("PV power field missing")


def expected_tesla_home(local_dt):
    # Normal weekly presence forecast only; never a hard control gate.
    # Thu evening through Mon morning is the normal home window.
    wd = local_dt.weekday()  # Mon=0 .. Sun=6
    if wd in (4, 5, 6):  # Fri-Sun
        return True
    if wd == 3 and local_dt.hour >= 18:  # Thu evening
        return True
    if wd == 0 and local_dt.hour < 8:  # Mon morning
        return True
    return False


def ev_opportunity_target(surplus_w, already_running=False):
    min_a = EV_RUN_MIN_A if already_running else EV_START_MIN_A
    if surplus_w < min_a * EV_W_PER_A:
        return 0
    amps = min(EV_MAX_A, int(surplus_w // EV_W_PER_A))
    if amps < min_a:
        return 0
    return amps * EV_W_PER_A


pv = load(PV_FILE)
quatt = load(QUATT_FILE)
base = load(BASE_FILE)
ww = load(WW_FILE)
price = load(PRICE_FILE)
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
    raise SystemExit(
        f"FAIL: planner axis expected 96 slots, got {len(axis_slots)}"
    )

sources = {
    "PV": pv_map,
    "Quatt": q_map,
    "Base": b_map,
    "WW": ww_map,
    "Price": price_map,
}

for name, source_map in sources.items():
    source_slots = sorted(source_map)
    if source_slots != sorted(axis_slots):
        missing = sorted(set(axis_slots) - set(source_slots))
        extra = sorted(set(source_slots) - set(axis_slots))
        raise SystemExit(
            f"FAIL: {name} axis mismatch; "
            f"missing={missing[:3]} extra={extra[:3]}"
        )

common = sorted(
    set(pv_map)
    & set(q_map)
    & set(b_map)
    & set(ww_map)
    & set(price_map)
)

if len(common) != 96:
    raise SystemExit(
        f"FAIL: expected 96 aligned slots, got {len(common)}"
    )

slots = []
ev_running = tesla_charging_now

for ts in common:
    p = pv_map[ts]
    q = q_map[ts]
    b = b_map[ts]
    w = ww_map[ts]
    pr = price_map[ts]

    pv_w = max(0.0, pv_power(p))
    quatt_w = max(0.0, float(q.get("quattForecastW") or 0))
    base_w = max(0.0, float(b.get("baseLoadForecastW") or 0))
    ww_w = max(0.0, float(w.get("wwPlanW") or 0))

    non_controllable = base_w + quatt_w
    net_before = non_controllable - pv_w
    surplus_before = max(0.0, -net_before)

    local_dt = parse_utc(ts).astimezone(TZ)
    expected_home = expected_tesla_home(local_dt)

    # Current connected state is authoritative for the current home window.
    # For future slots, the normal weekly presence pattern is only a forecast.
    tesla_available = tesla_connected_now or expected_home

    ev_w = 0
    ev_reason = "NOT_AVAILABLE"
    if tesla_available:
        ev_w = ev_opportunity_target(surplus_before, ev_running)
        if ev_w > 0:
            ev_reason = "PV_EXPORT_OPPORTUNITY"
            ev_running = True
        else:
            ev_reason = "INSUFFICIENT_PV_SURPLUS"
            ev_running = False
    else:
        ev_running = False

    net_after_ev = non_controllable + ev_w - pv_w
    net_after_flex = non_controllable + ev_w + ww_w - pv_w

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
        "teslaAvailableForecast": tesla_available,
        "teslaExpectedHome": expected_home,
        "teslaConnectedNow": tesla_connected_now,
        "evPlanW": round(ev_w),
        "evAllocationReason": ev_reason,
        "netAfterEVW": round(net_after_ev),
        "gridImportAfterEVW": round(max(0.0, net_after_ev)),
        "gridExportAfterEVW": round(max(0.0, -net_after_ev)),
        "wwPlanW": round(ww_w),
        "wwAllocationReason": w.get("allocationReason"),
        "price_eur_kwh": pr.get("marketPriceEurPerKwh"),
        "netAfterFlexW": round(net_after_flex),
        "gridImportAfterFlexW": round(max(0.0, net_after_flex)),
        "gridExportAfterFlexW": round(max(0.0, -net_after_flex)),
    })

payload = {
    "schema": "EMS_PI_SHADOW_LOAD_PLAN_V0.5",
    "mode": "shadow",
    "control_writes": False,
    "composition": {
        "nonControllableLoad": "baseLoadForecastW + quattForecastW",
        "netBeforeFlex": "totalNonControllableLoadW - pvForecastW",
        "netAfterEV": "totalNonControllableLoadW + evPlanW - pvForecastW",
        "netAfterFlex": "totalNonControllableLoadW + evPlanW + wwPlanW - pvForecastW",
        "quattControl": "OBSERVE_ONLY_FORECAST",
        "wwControl": "SHADOW_PLAN_ONLY",
        "teslaControl": "SHADOW_OPPORTUNITY_ONLY",
        "teslaAvailabilityPolicy": "CONNECTED_NOW_OR_NORMAL_WEEKLY_HOME_FORECAST",
        "teslaOpportunityPolicy": "PV_SURPLUS_START7_RUN6_MAX16",
    },
    "tesla": {
        "connectedNow": tesla_connected_now,
        "chargingNow": tesla_charging_now,
        "startMinA": EV_START_MIN_A,
        "runMinA": EV_RUN_MIN_A,
        "maxA": EV_MAX_A,
        "wattsPerAmp": EV_W_PER_A,
        "deadlinePlanningIncluded": False,
    },
    "slot_count": len(slots),
    "slots": slots,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
tmp.replace(OUTPUT)

step_h = 0.25

def energy(field):
    return sum(x[field] for x in slots) * step_h / 1000

base_kwh = energy("baseLoadForecastW")
quatt_kwh = energy("quattForecastW")
pv_kwh = energy("pvForecastW")
ev_kwh = energy("evPlanW")
ww_kwh = energy("wwPlanW")

imp_before = energy("gridImportBeforeFlexW")
exp_before = energy("gridExportBeforeFlexW")
imp_after = energy("gridImportAfterFlexW")
exp_after = energy("gridExportAfterFlexW")

print("PASS: shadow load plan v0.5 built")
print("slots                    :", len(slots))
print("base load kWh            :", round(base_kwh, 2))
print("Quatt kWh                :", round(quatt_kwh, 2))
print("PV kWh                   :", round(pv_kwh, 2))
print("Tesla opportunity kWh    :", round(ev_kwh, 2))
print("WW planned kWh           :", round(ww_kwh, 2))
print("grid import before flex  :", round(imp_before, 2))
print("grid export before flex  :", round(exp_before, 2))
print("grid import after flex   :", round(imp_after, 2))
print("grid export after flex   :", round(exp_after, 2))
print("output                   :", OUTPUT)

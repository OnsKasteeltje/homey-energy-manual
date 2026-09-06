#!/usr/bin/env python3

import json
from pathlib import Path

PV_FILE = Path("/home/jeroen/ems/data/pv-forecast.json")
QUATT_FILE = Path("/home/jeroen/ems/data/quatt-forecast.json")
BASE_FILE = Path("/home/jeroen/ems/data/base-load-forecast.json")
WW_FILE = Path("/home/jeroen/ems/data/ww-plan.json")
PRICE_FILE = Path("/home/jeroen/ems/data/price-forecast.json")
AXIS_FILE = Path("/home/jeroen/ems/data/planner-axis.json")
OUTPUT = Path("/home/jeroen/ems/data/shadow-load-plan.json")

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

pv = load(PV_FILE)
quatt = load(QUATT_FILE)
base = load(BASE_FILE)
ww = load(WW_FILE)
price = load(PRICE_FILE)
axis = load(AXIS_FILE)

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
    net_after_ww = non_controllable + ww_w - pv_w

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
        "gridExportBeforeFlexW": round(max(0.0, -net_before)),

        "wwPlanW": round(ww_w),
        "wwAllocationReason": w.get("allocationReason"),
        "price_eur_kwh": pr.get("marketPriceEurPerKwh"),

        "netAfterWWW": round(net_after_ww),
        "gridImportAfterWWW": round(max(0.0, net_after_ww)),
        "gridExportAfterWWW": round(max(0.0, -net_after_ww)),
    })

payload = {
    "schema": "EMS_PI_SHADOW_LOAD_PLAN_V0.4",
    "mode": "shadow",
    "control_writes": False,

    "composition": {
        "nonControllableLoad":
            "baseLoadForecastW + quattForecastW",
        "netBeforeFlex":
            "totalNonControllableLoadW - pvForecastW",
        "netAfterWW":
            "totalNonControllableLoadW + wwPlanW - pvForecastW",
        "quattControl": "OBSERVE_ONLY_FORECAST",
        "wwControl": "SHADOW_PLAN_ONLY",
        "teslaControl": "NOT_INCLUDED",
    },

    "slot_count": len(slots),
    "slots": slots,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(
    json.dumps(payload, separators=(",", ":")) + "\n"
)
tmp.replace(OUTPUT)

step_h = 0.25

def energy(field):
    return sum(x[field] for x in slots) * step_h / 1000

base_kwh = energy("baseLoadForecastW")
quatt_kwh = energy("quattForecastW")
pv_kwh = energy("pvForecastW")
ww_kwh = energy("wwPlanW")

imp_before = energy("gridImportBeforeFlexW")
exp_before = energy("gridExportBeforeFlexW")

imp_after = energy("gridImportAfterWWW")
exp_after = energy("gridExportAfterWWW")

print("PASS: shadow load plan v0.4 built")
print("slots                    :", len(slots))
print("base load kWh            :", round(base_kwh, 2))
print("Quatt kWh                :", round(quatt_kwh, 2))
print("PV kWh                   :", round(pv_kwh, 2))
print("WW planned kWh           :", round(ww_kwh, 2))
print("grid import before WW kWh:", round(imp_before, 2))
print("grid export before WW kWh:", round(exp_before, 2))
print("grid import after WW kWh :", round(imp_after, 2))
print("grid export after WW kWh :", round(exp_after, 2))
print("export reduction by WW   :", round(exp_before-exp_after, 2))
print("output                   :", OUTPUT)

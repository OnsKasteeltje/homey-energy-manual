#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

WW_INPUT = Path("/home/jeroen/ems/data/ww-input.json")
PV_FILE = Path("/home/jeroen/ems/data/pv-forecast.json")
QUATT_FILE = Path("/home/jeroen/ems/data/quatt-forecast.json")
BASE_FILE = Path("/home/jeroen/ems/data/base-load-forecast.json")
OUTPUT = Path("/home/jeroen/ems/data/ww-plan.json")

TZ = ZoneInfo("Europe/Amsterdam")

BOILER_W = 1900
WW_DAILY_FALLBACK_MIN = 240
WW_DEADLINE_HOUR = 19
WW_DEADLINE_SAFETY_SLOTS = 2
WW_SLOT_ENERGY_KWH = BOILER_W / 1000 * 0.25

def load(path):
    return json.loads(path.read_text())

def ts(slot):
    return (
        slot.get("slot_start_utc")
        or slot.get("start")
        or slot.get("startAt")
    )

def pv_power(slot):
    for key in ("pvForecastW", "pv_forecast_w", "power_w", "forecast_w"):
        if slot.get(key) is not None:
            return float(slot[key])
    raise ValueError("PV power field missing")

def local_date(timestamp):
    dt = datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    ).astimezone(TZ)
    return dt.date().isoformat()

def deadline_utc(date_key):
    y, m, d = map(int, date_key.split("-"))
    dt = datetime(
        y, m, d, WW_DEADLINE_HOUR, 0, 0, tzinfo=TZ
    )
    return dt.astimezone(timezone.utc)

ww_doc = load(WW_INPUT)
pv_doc = load(PV_FILE)
quatt_doc = load(QUATT_FILE)
base_doc = load(BASE_FILE)

ww = ww_doc["warmWater"]

pv_map = {ts(s): s for s in pv_doc.get("slots", [])}
q_map = {ts(s): s for s in quatt_doc.get("slots", [])}
b_map = {ts(s): s for s in base_doc.get("slots", [])}

common = sorted(set(pv_map) & set(q_map) & set(b_map))

if len(common) != 96:
    raise SystemExit(
        f"FAIL: expected 96 aligned forecast slots, got {len(common)}"
    )

source_slots = []

for timestamp in common:
    pv_w = max(0.0, pv_power(pv_map[timestamp]))
    quatt_w = max(
        0.0,
        float(q_map[timestamp].get("quattForecastW") or 0)
    )
    base_w = max(
        0.0,
        float(b_map[timestamp].get("baseLoadForecastW") or 0)
    )

    net_before = base_w + quatt_w - pv_w

    source_slots.append({
        "slot_start_utc": timestamp,
        "gridExportBeforeFlexW": max(0.0, -net_before),
    })

today_local = datetime.now(TZ).date().isoformat()

def metrics(slot):
    surplus = max(
        0.0,
        float(slot.get("gridExportBeforeFlexW") or 0)
    )
    pv_coverage = min(BOILER_W, surplus)
    marginal_import = max(0.0, BOILER_W - surplus)
    return surplus, pv_coverage, marginal_import

by_date = {}

for s in source_slots:
    d = local_date(s["slot_start_utc"])
    by_date.setdefault(d, []).append(s)

plan_slots = []
daily = []

for date_key, day_slots in sorted(by_date.items()):
    is_today = date_key == today_local

    goal_reached = False
    remaining_min = WW_DAILY_FALLBACK_MIN
    catchup = False

    if is_today:
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
        if datetime.fromisoformat(
            s["slot_start_utc"].replace("Z", "+00:00")
        ) < deadline
    ]

    need_kwh = remaining_min / 60 * BOILER_W / 1000
    remain = need_kwh
    chosen = []

    if not goal_reached and remain > 0:
        full_pv = []
        partial = []

        for s in candidates:
            surplus, pv_cov, marginal = metrics(s)
            item = (s, surplus, pv_cov, marginal)

            if marginal == 0:
                full_pv.append(item)
            else:
                partial.append(item)

        full_pv.sort(
            key=lambda x: (-x[2], x[0]["slot_start_utc"])
        )

        for s, surplus, pv_cov, marginal in full_pv:
            if remain <= 1e-9:
                break

            alloc = min(WW_SLOT_ENERGY_KWH, remain)

            chosen.append({
                "slot_start_utc": s["slot_start_utc"],
                "wwPlanW": BOILER_W,
                "allocatedKWh": round(alloc, 3),
                "pvCoverageW": round(pv_cov),
                "gridRequiredW": round(marginal),
                "allocationReason": "PV_SURPLUS_FULL",
            })

            remain -= alloc

        if remain > 1e-9:
            used = {x["slot_start_utc"] for x in chosen}
            rest = [
                x for x in partial
                if x[0]["slot_start_utc"] not in used
            ]

            required_slots = int(
                remain / WW_SLOT_ENERGY_KWH + 0.999999
            )

            slack_slots = max(0, len(rest) - required_slots)

            may_defer = (
                not catchup
                and slack_slots > WW_DEADLINE_SAFETY_SLOTS
            )

            if not may_defer:
                rest.sort(
                    key=lambda x: (
                        x[3],
                        x[0]["slot_start_utc"]
                    )
                )

                for s, surplus, pv_cov, marginal in rest:
                    if remain <= 1e-9:
                        break

                    alloc = min(WW_SLOT_ENERGY_KWH, remain)

                    chosen.append({
                        "slot_start_utc": s["slot_start_utc"],
                        "wwPlanW": BOILER_W,
                        "allocatedKWh": round(alloc, 3),
                        "pvCoverageW": round(pv_cov),
                        "gridRequiredW": round(marginal),
                        "allocationReason":
                            "PV_PARTIAL_FALLBACK"
                            if pv_cov > 0
                            else "DEADLINE_FALLBACK",
                    })

                    remain -= alloc

    chosen_map = {
        x["slot_start_utc"]: x for x in chosen
    }

    for s in day_slots:
        c = chosen_map.get(s["slot_start_utc"])

        if c:
            plan_slots.append(c)
        else:
            plan_slots.append({
                "slot_start_utc": s["slot_start_utc"],
                "wwPlanW": 0,
                "allocatedKWh": 0,
                "pvCoverageW": 0,
                "gridRequiredW": 0,
                "allocationReason": "HOLD",
            })

    daily.append({
        "date": date_key,
        "goalReached": goal_reached,
        "remainingFallbackMin": remaining_min,
        "requiredEnergyKWh": round(need_kwh, 3),
        "allocatedEnergyKWh": round(
            sum(x["allocatedKWh"] for x in chosen), 3
        ),
        "unallocatedEnergyKWh": round(max(0.0, remain), 3),
        "catchupRequired": catchup,
        "deadlineLocal": "19:00",
        "allocatedSlots": len(chosen),
    })

plan_slots.sort(key=lambda x: x["slot_start_utc"])

payload = {
    "schema": "EMS_PI_WW_PLAN_V0.2",
    "mode": "shadow",
    "control_writes": False,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "sourceForecast":
        "pv + quatt + quatt-free-base",
    "boilerPowerW": BOILER_W,
    "dailyFallbackMin": WW_DAILY_FALLBACK_MIN,
    "deadlineLocal": "19:00",
    "slot_count": len(plan_slots),
    "dailyPlans": daily,
    "slots": plan_slots,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(
    json.dumps(payload, separators=(",", ":")) + "\n"
)
tmp.replace(OUTPUT)

print("PASS: WW plan v0.2 built")
print("slots:", len(plan_slots))

for d in daily:
    print(
        d["date"],
        "goalReached=", d["goalReached"],
        "required=", d["requiredEnergyKWh"],
        "allocated=", d["allocatedEnergyKWh"],
        "slots=", d["allocatedSlots"],
    )

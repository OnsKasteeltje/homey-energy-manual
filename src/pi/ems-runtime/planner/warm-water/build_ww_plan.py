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
WW_FALLBACK_HOUR = 16
WW_DEADLINE_SAFETY_SLOTS = 2
WW_MIN_RUN_SLOTS = 2
WW_SLOT_ENERGY_KWH = BOILER_W / 1000 * 0.25


def load(path):
    return json.loads(path.read_text())


def ts(slot):
    return (
        slot.get("slot_start_utc")
        or slot.get("start")
        or slot.get("startAt")
    )


def parse_utc(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def pv_power(slot):
    for key in ("pvForecastW", "pv_forecast_w", "power_w", "forecast_w"):
        if slot.get(key) is not None:
            return float(slot[key])
    raise ValueError("PV power field missing")


def local_dt(timestamp):
    return parse_utc(timestamp).astimezone(TZ)


def local_date(timestamp):
    return local_dt(timestamp).date().isoformat()


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


def is_consecutive(a, b):
    return (
        parse_utc(b["slot_start_utc"]) -
        parse_utc(a["slot_start_utc"])
    ).total_seconds() == 15 * 60


def choose_pv_blocks(candidates, required_slots):
    """Choose best non-overlapping 30-minute blocks with any PV coverage."""
    blocks = []

    for i in range(len(candidates) - 1):
        a = candidates[i]
        b = candidates[i + 1]
        if not is_consecutive(a, b):
            continue

        a_pv = metrics(a)[1]
        b_pv = metrics(b)[1]
        score = a_pv + b_pv

        if score <= 0:
            continue

        blocks.append({
            "indices": (i, i + 1),
            "score": score,
            "start": a["slot_start_utc"],
        })

    blocks.sort(key=lambda x: (-x["score"], x["start"]))

    selected = set()
    for block in blocks:
        if required_slots - len(selected) < WW_MIN_RUN_SLOTS:
            break

        i, j = block["indices"]
        if i in selected or j in selected:
            continue

        selected.add(i)
        selected.add(j)

        if len(selected) >= required_slots:
            break

    return selected


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
        if parse_utc(s["slot_start_utc"]) < deadline
    ]

    need_kwh = remaining_min / 60 * BOILER_W / 1000
    required_slots = int(
        need_kwh / WW_SLOT_ENERGY_KWH + 0.999999
    )
    chosen_indices = set()

    if not goal_reached and required_slots > 0:
        # Phase 1: PV-first. Any predicted PV surplus is valuable, but
        # discretionary starts are planned in 30-minute blocks to avoid ping-pong.
        chosen_indices = choose_pv_blocks(candidates, required_slots)

        remaining_slots = max(0, required_slots - len(chosen_indices))

        if remaining_slots > 0:
            unchosen = [
                (i, s) for i, s in enumerate(candidates)
                if i not in chosen_indices
            ]

            after_1600 = [
                (i, s) for i, s in unchosen
                if local_dt(s["slot_start_utc"]).hour >= WW_FALLBACK_HOUR
            ]

            # Normal fallback is only after 16:00. If waiting until 16:00
            # would make the 19:00 deadline impossible, extend the fallback
            # window earlier just enough to preserve comfort.
            fallback_pool = (
                after_1600
                if len(after_1600) >= remaining_slots and not catchup
                else unchosen
            )

            fallback_pool.sort(
                key=lambda x: x[1]["slot_start_utc"],
                reverse=True
            )

            for i, _ in fallback_pool[:remaining_slots]:
                chosen_indices.add(i)

    remain_kwh = need_kwh
    chosen = []

    for i, s in enumerate(candidates):
        if i not in chosen_indices:
            continue

        surplus, pv_cov, marginal = metrics(s)
        dt_local = local_dt(s["slot_start_utc"])

        if pv_cov > 0:
            reason = (
                "PV_SURPLUS_FULL"
                if marginal == 0
                else "PV_PARTIAL_OPTIMIZED"
            )
        elif dt_local.hour >= WW_FALLBACK_HOUR:
            reason = "DEADLINE_FALLBACK"
        else:
            reason = "SAFETY_EARLY_FALLBACK"

        alloc = min(WW_SLOT_ENERGY_KWH, remain_kwh)

        chosen.append({
            "slot_start_utc": s["slot_start_utc"],
            "wwPlanW": BOILER_W,
            "allocatedKWh": round(alloc, 3),
            "pvCoverageW": round(pv_cov),
            "gridRequiredW": round(marginal),
            "allocationReason": reason,
        })

        remain_kwh = max(0.0, remain_kwh - alloc)

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
        "unallocatedEnergyKWh": round(max(0.0, remain_kwh), 3),
        "catchupRequired": catchup,
        "fallbackNotBeforeLocal": "16:00",
        "deadlineLocal": "19:00",
        "minRunMinutes": WW_MIN_RUN_SLOTS * 15,
        "allocatedSlots": len(chosen),
    })

plan_slots.sort(key=lambda x: x["slot_start_utc"])

payload = {
    "schema": "EMS_PI_WW_PLAN_V0.3",
    "mode": "shadow",
    "control_writes": False,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "sourceForecast":
        "pv + quatt + quatt-free-base",
    "boilerPowerW": BOILER_W,
    "dailyFallbackMin": WW_DAILY_FALLBACK_MIN,
    "fallbackNotBeforeLocal": "16:00",
    "deadlineLocal": "19:00",
    "minRunMinutes": WW_MIN_RUN_SLOTS * 15,
    "slot_count": len(plan_slots),
    "dailyPlans": daily,
    "slots": plan_slots,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(
    json.dumps(payload, separators=(",", ":")) + "\n"
)
tmp.replace(OUTPUT)

print("PASS: WW plan v0.3 built")
print("slots:", len(plan_slots))

for d in daily:
    print(
        d["date"],
        "goalReached=", d["goalReached"],
        "required=", d["requiredEnergyKWh"],
        "allocated=", d["allocatedEnergyKWh"],
        "slots=", d["allocatedSlots"],
    )

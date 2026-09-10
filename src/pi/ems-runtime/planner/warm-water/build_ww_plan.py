#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

WW_INPUT = Path("/home/jeroen/ems/data/ww-input.json")
PV_FILE = Path("/home/jeroen/ems/data/pv-forecast.json")
QUATT_FILE = Path("/home/jeroen/ems/data/quatt-forecast.json")
BASE_FILE = Path("/home/jeroen/ems/data/base-load-forecast.json")
ENERGY_STATE_FILE = Path("/home/jeroen/ems/repo/homey-energy-manual/docs/data/energy-state-v2.json")
OUTPUT = Path("/home/jeroen/ems/data/ww-plan.json")

TZ = ZoneInfo("Europe/Amsterdam")

BOILER_W = 1900
# Future-day expected WW demand used for PV reservation.
# This is deliberately separate from the physical/safety ceiling.
# Initial value is based on observed complete-day history (~5.86 kWh/day).
WW_EXPECTED_DAILY_KWH = 6.0

WW_EXPECTED_DAILY_KWH_BY_WEEKDAY = {
    0: 5.8,  # Monday
    1: 4.5,  # Tuesday
    2: 6.3,  # Wednesday
    3: 7.0,  # Thursday
    4: 5.9,  # Friday
    5: 7.7,  # Saturday
    6: 7.7,  # Sunday
}

# Legacy maximum planned fallback duration.
# 240 min × 1.9 kW = 7.6 kWh is NOT a physical daily-energy ceiling;
# observed historical daily boiler energy can be materially higher.
WW_SAFETY_MAX_MIN = 240
WW_DEADLINE_HOUR = 19
WW_FALLBACK_HOUR = 16
WW_MIN_RUN_SLOTS = 2
WW_MIN_PV_WINDOW_KWH = 0.10
WW_SLOT_ENERGY_KWH = BOILER_W / 1000 * 0.25


def load(path):
    return json.loads(path.read_text())


def ts(slot):
    return slot.get("slot_start_utc") or slot.get("start") or slot.get("startAt")


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
    dt = datetime(y, m, d, WW_DEADLINE_HOUR, 0, 0, tzinfo=TZ)
    return dt.astimezone(timezone.utc)


ww_doc = load(WW_INPUT)
pv_doc = load(PV_FILE)
quatt_doc = load(QUATT_FILE)
base_doc = load(BASE_FILE)
energy_state = load(ENERGY_STATE_FILE) if ENERGY_STATE_FILE.exists() else {}
ww = ww_doc["warmWater"]

tesla_state = energy_state.get("tesla") or {}
tesla_connected_now = tesla_state.get("connected") is True

pv_map = {ts(s): s for s in pv_doc.get("slots", [])}
q_map = {ts(s): s for s in quatt_doc.get("slots", [])}
b_map = {ts(s): s for s in base_doc.get("slots", [])}
common = sorted(set(pv_map) & set(q_map) & set(b_map))

if len(common) != 96:
    raise SystemExit(f"FAIL: expected 96 aligned forecast slots, got {len(common)}")

source_slots = []
for timestamp in common:
    pv_w = max(0.0, pv_power(pv_map[timestamp]))
    quatt_w = max(0.0, float(q_map[timestamp].get("quattForecastW") or 0))
    base_w = max(0.0, float(b_map[timestamp].get("baseLoadForecastW") or 0))
    net_before = base_w + quatt_w - pv_w
    source_slots.append({
        "slot_start_utc": timestamp,
        "gridExportBeforeFlexW": max(0.0, -net_before),
        # Peak preservation is allowed only when the vehicle is physically
        # connected now. The weekly home forecast must never move WW.
        "teslaOpportunityRelevant": tesla_connected_now,
    })

today_local = datetime.now(TZ).date().isoformat()


def metrics(slot):
    surplus = max(0.0, float(slot.get("gridExportBeforeFlexW") or 0))
    pv_coverage = min(BOILER_W, surplus)
    marginal_import = max(0.0, BOILER_W - surplus)
    return surplus, pv_coverage, marginal_import


def is_consecutive(a, b):
    return (
        parse_utc(b["slot_start_utc"]) - parse_utc(a["slot_start_utc"])
    ).total_seconds() == 15 * 60


def find_pv_windows(candidates):
    """Return contiguous positive-export windows that justify a boiler start."""
    windows = []
    current = []

    def finish(indices):
        if len(indices) < WW_MIN_RUN_SLOTS:
            return
        pv_sum_w = sum(metrics(candidates[i])[1] for i in indices)
        pv_energy_kwh = pv_sum_w * 0.25 / 1000
        if pv_energy_kwh < WW_MIN_PV_WINDOW_KWH:
            return
        windows.append({
            "indices": tuple(indices),
            "pvSumW": pv_sum_w,
            "pvEnergyKWh": pv_energy_kwh,
            "avgPvW": pv_sum_w / len(indices),
            "start": candidates[indices[0]]["slot_start_utc"],
            "teslaOpportunityRelevant": tesla_connected_now,
        })

    for i, slot in enumerate(candidates):
        pv_cov = metrics(slot)[1]
        if pv_cov <= 0:
            finish(current)
            current = []
            continue
        if current and not is_consecutive(candidates[current[-1]], slot):
            finish(current)
            current = []
        current.append(i)
    finish(current)

    windows.sort(key=lambda x: (-x["avgPvW"], -x["pvEnergyKWh"], x["start"]))
    return windows


def best_subrun(indices, candidates, length):
    """Pick the strongest consecutive WW subrun."""
    best = None
    for pos in range(0, len(indices) - length + 1):
        run = indices[pos:pos + length]
        score = sum(metrics(candidates[i])[1] for i in run)
        start = candidates[run[0]]["slot_start_utc"]
        key = (score, -parse_utc(start).timestamp())
        if best is None or key > best[0]:
            best = (key, run)
    return tuple(best[1]) if best else tuple()


def shoulder_subruns(indices, candidates, length):
    """Use both PV-window shoulders while preserving minimum WW run lengths."""
    if length >= len(indices):
        return tuple(indices)
    if length < 2 * WW_MIN_RUN_SLOTS:
        return best_subrun(indices, candidates, length)

    left_len = max(WW_MIN_RUN_SLOTS, length // 2)
    right_len = max(WW_MIN_RUN_SLOTS, length - left_len)

    while left_len + right_len > length:
        if right_len > left_len and right_len > WW_MIN_RUN_SLOTS:
            right_len -= 1
        elif left_len > WW_MIN_RUN_SLOTS:
            left_len -= 1
        else:
            return best_subrun(indices, candidates, length)

    if length % 2:
        left_score = sum(metrics(candidates[i])[1] for i in indices[:left_len + 1])
        right_score = sum(metrics(candidates[i])[1] for i in indices[-(right_len + 1):])
        if left_score > right_score and right_len > WW_MIN_RUN_SLOTS:
            left_len += 1
            right_len -= 1
        elif right_score > left_score and left_len > WW_MIN_RUN_SLOTS:
            right_len += 1
            left_len -= 1

    run = list(indices[:left_len]) + list(indices[-right_len:])
    return tuple(dict.fromkeys(run))


def choose_pv_windows(candidates, required_slots):
    """Reserve WW first; preserve the PV peak only for a connected Tesla."""
    selected = set()
    windows = find_pv_windows(candidates)

    for window in windows:
        remaining = required_slots - len(selected)
        if remaining < WW_MIN_RUN_SLOTS:
            break
        indices = window["indices"]
        if len(indices) <= remaining:
            run = indices
        elif tesla_connected_now:
            run = shoulder_subruns(indices, candidates, remaining)
        else:
            run = best_subrun(indices, candidates, remaining)
        selected.update(run)
        if len(selected) >= required_slots:
            break

    return selected, windows


by_date = {}
for s in source_slots:
    by_date.setdefault(local_date(s["slot_start_utc"]), []).append(s)

plan_slots = []
daily = []

for date_key, day_slots in sorted(by_date.items()):
    is_today = date_key == today_local
    goal_reached = False
    # Future days use the validated weekday demand model.
    # The historic fixed 6.0 kWh value remains the explicit fail-safe fallback.
    remaining_min = None

    local_date = datetime.fromisoformat(date_key).date()
    weekday_expected_kwh = WW_EXPECTED_DAILY_KWH_BY_WEEKDAY.get(
        local_date.weekday(),
        WW_EXPECTED_DAILY_KWH,
    )
    need_kwh = weekday_expected_kwh
    catchup = False

    if is_today:
        goal_reached = ww.get("goalReachedToday") is True or ww.get("goalReached") is True
        remaining_min = (
            0 if goal_reached
            else max(0, int(ww.get("remainingFallbackMin") or 0))
        )
        catchup = ww.get("catchupRequired") is True
        need_kwh = remaining_min / 60 * BOILER_W / 1000

    deadline = deadline_utc(date_key)
    candidates = [
        s for s in day_slots
        if parse_utc(s["slot_start_utc"]) < deadline
    ]
    required_slots = int(need_kwh / WW_SLOT_ENERGY_KWH + 0.999999)
    chosen_indices = set()
    pv_chosen_indices = set()
    eligible_pv_windows = []

    if not goal_reached and required_slots > 0:
        chosen_indices, eligible_pv_windows = choose_pv_windows(
            candidates, required_slots
        )
        pv_chosen_indices = set(chosen_indices)
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
            fallback_pool = (
                after_1600
                if len(after_1600) >= remaining_slots and not catchup
                else unchosen
            )
            fallback_pool.sort(
                key=lambda x: x[1]["slot_start_utc"], reverse=True
            )
            for i, _ in fallback_pool[:remaining_slots]:
                chosen_indices.add(i)

    remain_kwh = need_kwh
    chosen = []

    for i, s in enumerate(candidates):
        if i not in chosen_indices:
            continue

        _, pv_cov, marginal = metrics(s)
        dt_local = local_dt(s["slot_start_utc"])

        if i in pv_chosen_indices:
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

    chosen_map = {x["slot_start_utc"]: x for x in chosen}
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
        "expectedDailyEnergyKWh": round(weekday_expected_kwh, 3),
        "expectedDailyEnergySource": "WEEKDAY_MEDIAN_SQLITE_V0.2",
        "expectedDailyEnergyFallbackKWh": WW_EXPECTED_DAILY_KWH,
        "expectedDailyEnergyShadowKWh": round(weekday_expected_kwh, 3),
        "expectedDailyEnergyShadowSource": "WEEKDAY_MEDIAN_SQLITE_V0.2",
        "allocatedEnergyKWh": round(
            sum(x["allocatedKWh"] for x in chosen), 3
        ),
        "unallocatedEnergyKWh": round(max(0.0, remain_kwh), 3),
        "catchupRequired": catchup,
        "fallbackNotBeforeLocal": "16:00",
        "deadlineLocal": "19:00",
        "minRunMinutes": WW_MIN_RUN_SLOTS * 15,
        "minPvWindowEnergyKWh": WW_MIN_PV_WINDOW_KWH,
        "eligiblePvWindows": len(eligible_pv_windows),
        "evRelevantPvWindows": (
            len(eligible_pv_windows) if tesla_connected_now else 0
        ),
        "allocatedSlots": len(chosen),
    })

plan_slots.sort(key=lambda x: x["slot_start_utc"])

payload = {
    "schema": "EMS_PI_WW_PLAN_V0.7.0",
    "mode": "shadow",
    "control_writes": False,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "sourceForecast": "pv + quatt + quatt-free-base",
    "boilerPowerW": BOILER_W,
    "dailyFallbackMin": WW_SAFETY_MAX_MIN,
    "expectedDailyEnergyFallbackKWh": WW_EXPECTED_DAILY_KWH,
    "expectedDailyEnergyProductionSource": "WEEKDAY_MEDIAN_SQLITE_V0.2",
    "fallbackNotBeforeLocal": "16:00",
    "deadlineLocal": "19:00",
    "minRunMinutes": WW_MIN_RUN_SLOTS * 15,
    "minPvWindowEnergyKWh": WW_MIN_PV_WINDOW_KWH,
    "pvWindowPolicy": "STRONGEST_SUBRUN_UNLESS_TESLA_CONNECTED_THEN_SHOULDERS",
    "flexPriority": "WW_COMFORT_RESERVED_BEFORE_EV_OPPORTUNITY",
    "teslaPeakPreservation": "LIVE_CONNECTED_CURRENT_STATE_ONLY",
    "teslaConnectedNow": tesla_connected_now,
    "slot_count": len(plan_slots),
    "dailyPlans": daily,
    "slots": plan_slots,
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
tmp.replace(OUTPUT)

print("PASS: WW plan v0.7.0 built")
print("slots:", len(plan_slots))
for d in daily:
    print(
        d["date"],
        "goalReached=", d["goalReached"],
        "required=", d["requiredEnergyKWh"],
        "allocated=", d["allocatedEnergyKWh"],
        "pvWindows=", d["eligiblePvWindows"],
        "evRelevant=", d["evRelevantPvWindows"],
        "slots=", d["allocatedSlots"],
    )

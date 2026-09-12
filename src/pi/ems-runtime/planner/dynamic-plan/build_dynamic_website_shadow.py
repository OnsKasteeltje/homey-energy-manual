#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path("/home/jeroen/ems/data/dynamic-shadow-plan.json")
ENERGY_STATE = Path("/home/jeroen/ems/data/energy-state-v2.json")
OUTPUT = Path("/home/jeroen/ems/data/energy-planner-shadow-dynamic.json")
TZ = ZoneInfo("Europe/Amsterdam")
SLOT_MIN = 15
SLOT_H = SLOT_MIN / 60
EV_W_PER_A = 690
EV_MIN_A = 6
EV_MAX_A = 16


def load(path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        if default is not None:
            return default
        raise


def parse_utc(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def iso_ms(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def clamp(value, low, high):
    return max(low, min(high, value))


src = load(SOURCE)
state = load(ENERGY_STATE, {})
slots = src.get("slots", [])
if len(slots) != 96:
    raise SystemExit(f"FAIL: expected 96 Dynamic planner slots, got {len(slots)}")

now_utc = datetime.now(timezone.utc)
tesla_state = state.get("tesla") or {}
deadline_active = tesla_state.get("deadline_active") is True
connected = tesla_state.get("connected") is True
remaining_kwh = max(0.0, float(tesla_state.get("remaining_kwh") or 0))
deadline_dt = parse_utc(tesla_state.get("deadline_at"))
latest_start_dt = parse_utc(tesla_state.get("latest_start_at"))

inferred_max_a = None
if (
    deadline_active
    and connected
    and remaining_kwh > 0
    and deadline_dt is not None
    and latest_start_dt is not None
    and deadline_dt > latest_start_dt
):
    hours = (deadline_dt - latest_start_dt).total_seconds() / 3600
    inferred_kw = remaining_kwh / hours if hours > 0 else 0
    inferred_max_a = int(round(inferred_kw / (EV_W_PER_A / 1000)))
    inferred_max_a = clamp(inferred_max_a, EV_MIN_A, EV_MAX_A)

# Deadline overlay is intentionally website-shadow only. It makes the hard
# executor deadline visible in the 24 h planner without changing the canonical
# Dynamic Pi control plan. The Homey executor remains the deadline safety owner.
deadline_overlay_w = {}
base_future_ev_kwh = 0.0
reserve_need_kwh = 0.0
reserve_added_kwh = 0.0
deadline_in_horizon = False

if (
    inferred_max_a is not None
    and deadline_dt is not None
    and deadline_dt > now_utc
):
    future_before_deadline = []
    for i, s in enumerate(slots):
        start_dt = parse_utc(s.get("slot_start_utc"))
        if start_dt is None or start_dt < now_utc or start_dt >= deadline_dt:
            continue
        base_w = max(0, int(round(s.get("evPlanW") or 0)))
        base_future_ev_kwh += base_w * SLOT_H / 1000
        future_before_deadline.append((i, start_dt, base_w))

    if future_before_deadline:
        deadline_in_horizon = deadline_dt <= (
            max(x[1] for x in future_before_deadline) + timedelta(minutes=SLOT_MIN)
        )

    reserve_need_kwh = max(0.0, remaining_kwh - base_future_ev_kwh)
    remaining_reserve = reserve_need_kwh
    deadline_target_w = inferred_max_a * EV_W_PER_A

    # Reserve the latest slots first. Earlier profitable PV slots stay untouched;
    # their planned energy therefore automatically moves the effective hard start
    # later, matching the executor-side latest-start behaviour.
    for i, start_dt, base_w in sorted(
        future_before_deadline,
        key=lambda x: x[1],
        reverse=True,
    ):
        if remaining_reserve <= 1e-9:
            break
        target_w = max(base_w, deadline_target_w)
        incremental_kwh = max(0, target_w - base_w) * SLOT_H / 1000
        if incremental_kwh <= 0:
            continue
        deadline_overlay_w[i] = target_w
        reserve_added_kwh += incremental_kwh
        remaining_reserve = max(0.0, remaining_reserve - incremental_kwh)

    deadline_feasible = remaining_reserve <= 1e-6
else:
    deadline_feasible = not deadline_active or remaining_kwh <= 0


actions = []
for i, s in enumerate(slots):
    start_dt = parse_utc(s["slot_start_utc"])
    end_dt = start_dt + timedelta(minutes=SLOT_MIN)
    local = start_dt.astimezone(TZ)
    net_before = int(round(
        (s.get("baseLoadForecastW") or 0)
        + (s.get("quattForecastW") or 0)
        - (s.get("pvForecastW") or 0)
    ))
    ww_w = int(round(s.get("wwPlanW") or 0))
    source_ev_w = int(round(s.get("evPlanW") or 0))
    ev_w = int(deadline_overlay_w.get(i, source_ev_w))
    deadline_required = i in deadline_overlay_w

    if deadline_required:
        tesla_mode = "DEADLINE_REQUIRED"
        tesla_reason = "PI_WEBSITE_DEADLINE_RESERVE"
    elif source_ev_w > 0:
        tesla_mode = "OPPORTUNITY"
        tesla_reason = s.get("evAllocationReason")
    else:
        tesla_mode = "HOLD"
        tesla_reason = s.get("evAllocationReason")

    actions.append({
        "i": i,
        "start": iso_ms(start_dt),
        "end": iso_ms(end_dt),
        "localDate": local.date().isoformat(),
        "localQuarter": local.hour * 4 + local.minute // 15,
        "price_eur_kwh": None,
        "priceClass": "FIXED",
        "baseLoadForecastW": int(round(s.get("baseLoadForecastW") or 0)),
        "pvForecastW": int(round(s.get("pvForecastW") or 0)),
        "netBeforeFlexW": net_before,
        "importBeforeFlexW": max(0, net_before),
        "pvSurplusBeforeFlexW": max(0, -net_before),
        "correctedExportBeforeFlexW": int(round(s.get("correctedExportBeforeFlexW") or 0)),
        "confidence": s.get("confidence"),
        "confidenceComponents": s.get("confidenceComponents"),
        "forecastQuality": {
            "baseLoad": "PI_HISTORY_MODEL",
            "pv": "PI_DYNAMIC_CONFIDENCE_PV_FORECAST"
        },
        "battery": "HOLD",
        "tesla": "RUN" if ev_w > 0 else "HOLD",
        "warmWater": "RUN" if ww_w > 0 else "HOLD",
        "targets": {
            "evTargetW": ev_w,
            "sourceEvTargetW": source_ev_w,
            "wwTargetW": ww_w,
            "batteryTargetW": 0
        },
        "teslaPlan": {
            "mode": tesla_mode,
            "reason": tesla_reason,
            "availableForecast": bool(s.get("teslaAvailableForecast")),
            "availabilitySource": s.get("teslaAvailabilitySource"),
            "deadlineOverlay": deadline_required,
            "controlImpact": "NONE_WEBSITE_SHADOW_ONLY"
        },
        "warmWaterPlan": {
            "reason": s.get("wwAllocationReason")
        }
    })


generated = iso_ms(datetime.now(timezone.utc))
deadline_plan = {
    "active": deadline_active,
    "connected": connected,
    "remainingKWh": round(remaining_kwh, 3),
    "deadlineAt": iso_ms(deadline_dt) if deadline_dt else None,
    "latestStartAtInput": iso_ms(latest_start_dt) if latest_start_dt else None,
    "inferredMaxA": inferred_max_a,
    "baseOpportunityPlannedKWhBeforeDeadline": round(base_future_ev_kwh, 3),
    "reserveNeedKWh": round(reserve_need_kwh, 3),
    "reserveAddedKWh": round(reserve_added_kwh, 3),
    "reserveSlots": len(deadline_overlay_w),
    "deadlineWithinActionHorizon": deadline_in_horizon,
    "feasibleWithinVisibleHorizon": deadline_feasible,
    "policy": "LATEST_SLOTS_AFTER_PV_OPPORTUNITY_V0.1",
    "controlImpact": "NONE_WEBSITE_SHADOW_ONLY",
    "executorSafetyOwner": "HOMEY"
}

plan = {
    "schema": "EMS_PI_DYNAMIC_ENERGY_PLAN_24H_V0.2",
    "generatedAt": generated,
    "controlMode": "PURE_SHADOW",
    "readOnly": True,
    "physicalWritePerformed": False,
    "purpose": "DYNAMIC_24H_PV_SELF_CONSUMPTION_OPTIMIZATION_PLUS_DEADLINE_VISIBILITY",
    "objective": src.get("objective"),
    "guardrails": src.get("guardrails"),
    "confidenceModel": src.get("confidenceModel"),
    "realtime": src.get("realtime"),
    "deadlinePlan": deadline_plan,
    "inputs": {
        "contract": "FIXED",
        "forecastQuality": {
            "baseLoad": "PI_HISTORY_MODEL",
            "pv": "PI_DYNAMIC_CONFIDENCE_PV_FORECAST",
            "quatt": "PI_QUATT_FORECAST",
            "tesla": "PI_WEEKLY_PRESENCE_PLUS_LIVE_CONNECTED_PLUS_HOMEY_DEADLINE_STATE"
        }
    },
    "plan": {
        "slotMinutes": SLOT_MIN,
        "horizonQuality": "FULL_24H_DYNAMIC_AXIS",
        "slotsAvailable": len(actions),
        "actions": actions
    }
}

payload = {
    "schema": "EMS_PI_DYNAMIC_PLANNER_SHADOW_PUBLISH_V0.2",
    "publishedAt": generated,
    "observabilityOnly": True,
    "controlImpact": "NONE",
    "sourceRevision": None,
    "generatedAt": generated,
    "plan": plan,
    "status": "PI_DYNAMIC_SHADOW",
    "regression": None
}

OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
print("PASS: Dynamic Pi website shadow v0.2 built")
print("slots                  :", len(actions))
print("Tesla source slots     :", sum(1 for x in actions if x["targets"]["sourceEvTargetW"] > 0))
print("Tesla deadline slots   :", len(deadline_overlay_w))
print("WW slots               :", sum(1 for x in actions if x["warmWater"] == "RUN"))
print("deadline active        :", deadline_active)
print("deadline inferred maxA :", inferred_max_a)
print("deadline reserve kWh   :", round(reserve_added_kwh, 3))
print("output                 :", OUTPUT)

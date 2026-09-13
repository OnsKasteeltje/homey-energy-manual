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

# Tesla deadline planning is canonical in dynamic-shadow-plan.json.
# This website builder is render-only: it must never reconstruct or add
# deadline energy. It only exposes the canonical planner classification.
canonical_deadline = (src.get("tesla") or {}).get("deadlinePlan") or {}

deadline_in_horizon = False
if deadline_dt is not None:
    starts = []
    for s in slots:
        start_dt = parse_utc(s.get("slot_start_utc"))
        if start_dt is not None:
            starts.append(start_dt)
    if starts:
        deadline_in_horizon = deadline_dt <= (
            max(starts) + timedelta(minutes=SLOT_MIN)
        )

base_future_ev_kwh = 0.0
deadline_required_kwh = 0.0

for s in slots:
    start_dt = parse_utc(s.get("slot_start_utc"))
    if (
        start_dt is None
        or start_dt < now_utc
        or deadline_dt is None
        or start_dt >= deadline_dt
    ):
        continue

    ev_w = max(0, int(round(s.get("evPlanW") or 0)))
    if ev_w <= 0:
        continue

    kwh = ev_w * SLOT_H / 1000
    reason = str(s.get("evAllocationReason") or "")

    if reason == "DEADLINE_REQUIRED" or s.get("evDeadlineRequired") is True:
        deadline_required_kwh += kwh
    else:
        base_future_ev_kwh += kwh

reserve_need_kwh = max(
    0.0,
    float(canonical_deadline.get("deadlineRequiredKWh") or 0),
)
reserve_added_kwh = max(
    0.0,
    float(canonical_deadline.get("deadlineAddedKWh") or 0),
)
deadline_feasible = (
    not deadline_active
    or remaining_kwh <= 0
    or (
        base_future_ev_kwh
        + deadline_required_kwh
        + 1e-9
        >= remaining_kwh
    )
)

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
    ev_w = source_ev_w

    tesla_reason = s.get("evAllocationReason")
    deadline_required = (
        tesla_reason == "DEADLINE_REQUIRED"
        or s.get("evDeadlineRequired") is True
    )

    if deadline_required and source_ev_w > 0:
        tesla_mode = "DEADLINE_REQUIRED"
    elif source_ev_w > 0:
        tesla_mode = "OPPORTUNITY"
    else:
        tesla_mode = "HOLD"

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
    "reserveSlots": int(canonical_deadline.get("appliedSlots") or 0),
    "deadlineWithinActionHorizon": deadline_in_horizon,
    "feasibleWithinVisibleHorizon": deadline_feasible,
    "policy": canonical_deadline.get("policy") or "CANONICAL_DYNAMIC_PLANNER",
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
print("Tesla deadline slots   :", int(canonical_deadline.get("appliedSlots") or 0))
print("WW slots               :", sum(1 for x in actions if x["warmWater"] == "RUN"))
print("deadline active        :", deadline_active)
print("deadline inferred maxA :", inferred_max_a)
print("deadline reserve kWh   :", round(reserve_added_kwh, 3))
print("output                 :", OUTPUT)

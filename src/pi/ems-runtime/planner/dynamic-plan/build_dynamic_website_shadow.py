#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path("/home/jeroen/ems/data/dynamic-shadow-plan.json")
OUTPUT = Path("/home/jeroen/ems/data/energy-planner-shadow-dynamic.json")
TZ = ZoneInfo("Europe/Amsterdam")

src = json.loads(SOURCE.read_text())
slots = src.get("slots", [])
if len(slots) != 96:
    raise SystemExit(f"FAIL: expected 96 Dynamic planner slots, got {len(slots)}")


def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def iso_ms(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


actions = []
for i, s in enumerate(slots):
    start_dt = parse_utc(s["slot_start_utc"])
    end_dt = start_dt + timedelta(minutes=15)
    local = start_dt.astimezone(TZ)
    net_before = int(round((s.get("baseLoadForecastW") or 0) + (s.get("quattForecastW") or 0) - (s.get("pvForecastW") or 0)))
    ww_w = int(round(s.get("wwPlanW") or 0))
    ev_w = int(round(s.get("evPlanW") or 0))

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
            "wwTargetW": ww_w,
            "batteryTargetW": 0
        },
        "teslaPlan": {
            "mode": "OPPORTUNITY" if ev_w > 0 else "HOLD",
            "reason": s.get("evAllocationReason"),
            "availableForecast": bool(s.get("teslaAvailableForecast")),
            "availabilitySource": s.get("teslaAvailabilitySource")
        },
        "warmWaterPlan": {
            "reason": s.get("wwAllocationReason")
        }
    })

generated = iso_ms(datetime.now(timezone.utc))
plan = {
    "schema": "EMS_PI_DYNAMIC_ENERGY_PLAN_24H_V0.1",
    "generatedAt": generated,
    "controlMode": "PURE_SHADOW",
    "readOnly": True,
    "physicalWritePerformed": False,
    "purpose": "DYNAMIC_24H_PV_SELF_CONSUMPTION_OPTIMIZATION",
    "objective": src.get("objective"),
    "guardrails": src.get("guardrails"),
    "confidenceModel": src.get("confidenceModel"),
    "realtime": src.get("realtime"),
    "inputs": {
        "contract": "FIXED",
        "forecastQuality": {
            "baseLoad": "PI_HISTORY_MODEL",
            "pv": "PI_DYNAMIC_CONFIDENCE_PV_FORECAST",
            "quatt": "PI_QUATT_FORECAST",
            "tesla": "PI_WEEKLY_PRESENCE_PLUS_LIVE_CONNECTED"
        }
    },
    "plan": {
        "slotMinutes": 15,
        "horizonQuality": "FULL_24H_DYNAMIC_AXIS",
        "slotsAvailable": len(actions),
        "actions": actions
    }
}

payload = {
    "schema": "EMS_PI_DYNAMIC_PLANNER_SHADOW_PUBLISH_V0.1",
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
print("PASS: Dynamic Pi website shadow v0.1 built")
print("slots       :", len(actions))
print("Tesla slots :", sum(1 for x in actions if x["tesla"] == "RUN"))
print("WW slots    :", sum(1 for x in actions if x["warmWater"] == "RUN"))
print("output      :", OUTPUT)

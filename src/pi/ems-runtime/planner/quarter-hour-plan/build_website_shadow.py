#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path("/home/jeroen/ems/data/shadow-load-plan.json")
OUTPUT = Path("/home/jeroen/ems/data/energy-planner-shadow-pi.json")
TZ = ZoneInfo("Europe/Amsterdam")

src = json.loads(SOURCE.read_text())
slots = src.get("slots", [])

if len(slots) != 96:
    raise SystemExit(f"FAIL: expected 96 Pi planner slots, got {len(slots)}")

def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def iso_ms(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

actions = []

for i, s in enumerate(slots):
    start_dt = parse_utc(s["slot_start_utc"])
    end_dt = start_dt + timedelta(minutes=15)
    local = start_dt.astimezone(TZ)

    net = int(round(s.get("netBeforeFlexW") or 0))
    ww_w = int(round(s.get("wwPlanW") or 0))

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
        "netBeforeFlexW": net,
        "importBeforeFlexW": max(0, net),
        "pvSurplusBeforeFlexW": max(0, -net),
        "gridHeadroomW": None,
        "forecastQuality": {
            "baseLoad": s.get("baseLoadQuality"),
            "pv": "PI_ARRAY_GEOMETRY_FORECAST"
        },
        "battery": "HOLD",
        "tesla": "HOLD",
        "warmWater": "RUN" if ww_w > 0 else "HOLD",
        "targets": {
            "evTargetW": 0,
            "wwTargetW": ww_w,
            "batteryTargetW": 0
        }
    })

generated = iso_ms(datetime.now(timezone.utc))

plan = {
    "schema": "EMS_PI_ENERGY_PLAN_24H_V0.1",
    "generatedAt": generated,
    "controlMode": "SHADOW",
    "readOnly": True,
    "physicalWritePerformed": False,
    "purpose": "24H_ENERGY_BALANCE_AND_COST_PLANNING",
    "inputs": {
        "contract": "FIXED",
        "price": {
            "quality": "REFERENCE_ONLY",
            "usable": False,
            "dynamicSlots": 0
        },
        "forecastQuality": {
            "baseLoad": "PI_HISTORY_MODEL",
            "pv": "PI_ARRAY_GEOMETRY_FORECAST",
            "quatt": "PI_QUATT_FORECAST"
        }
    },
    "plan": {
        "slotMinutes": 15,
        "horizonQuality": "FULL_24H_ENERGY_AXIS",
        "slotsAvailable": len(actions),
        "actions": actions
    }
}

payload = {
    "schema": "EMS_PI_PLANNER_SHADOW_PUBLISH_V0.1",
    "publishedAt": generated,
    "observabilityOnly": True,
    "controlImpact": "NONE",
    "sourceRevision": None,
    "generatedAt": generated,
    "plan": plan,
    "status": "PI_SHADOW",
    "regression": None
}

tmp = OUTPUT.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, indent=2) + "\n")
tmp.replace(OUTPUT)

print("PASS: Pi website shadow built")
print("slots :", len(actions))
print("output:", OUTPUT)

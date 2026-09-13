#!/usr/bin/env python3

"""Production-readiness guard for the Dynamic Pi Planner.

This wrapper deliberately remains PURE_SHADOW. It validates the production
contract and input freshness before running the existing dynamic planner, then
adds an explicit plan/executor contract and overlays a real Tesla deadline
requirement from energy-state-v2 when one is active.

No physical writes are performed here.
"""

import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUNTIME = Path("/home/jeroen/ems/runtime")
DATA = Path("/home/jeroen/ems/data")
REPO = Path("/home/jeroen/ems/repo/homey-energy-manual")

CONTRACT_FILE = RUNTIME / "planner/contract-policy.json"
PV_FILE = DATA / "pv-forecast.json"
WEATHER_FILE = DATA / "weather-forecast.json"
QUATT_FILE = DATA / "quatt-forecast.json"
BASE_FILE = DATA / "base-load-forecast.json"
WW_FILE = DATA / "ww-input.json"
AXIS_FILE = DATA / "planner-axis.json"
ENERGY_STATE_FILE = Path("/home/jeroen/ems/data/energy-state-v2.json")
BUILDER = RUNTIME / "planner/dynamic-plan/build_dynamic_shadow_plan.py"
OUTPUT = DATA / "dynamic-shadow-plan.json"

PLAN_TTL_MIN = 20
EV_W_PER_A = 690
SLOT_H = 0.25

# Deliberately tighter than the legacy WW fetcher's same-day 429 fallback.
# A stale planner must fail closed rather than silently become production-safe.
MAX_AGE_SEC = {
    PV_FILE: 45 * 60,
    WEATHER_FILE: 3 * 60 * 60,
    QUATT_FILE: 45 * 60,
    BASE_FILE: 45 * 60,
    WW_FILE: 2 * 60 * 60,
    AXIS_FILE: 45 * 60,
    ENERGY_STATE_FILE: 20 * 60,
}


def load(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"FAIL_CLOSED: required input missing: {path}")
    except Exception as exc:
        raise SystemExit(f"FAIL_CLOSED: invalid JSON {path}: {exc}")


def parse_utc(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def document_time(doc):
    for key in ("generated_at", "generatedAt", "updatedAt", "fetchedAt", "createdAt"):
        value = doc.get(key)
        if value:
            try:
                return parse_utc(value)
            except Exception:
                pass
    meta = doc.get("meta") or {}
    for key in ("generated_at", "generatedAt", "heartbeat_at", "source_sample_at"):
        value = meta.get(key)
        if value:
            try:
                return parse_utc(value)
            except Exception:
                pass
    return None


def validate_freshness(now):
    report = {}
    for path, max_age in MAX_AGE_SEC.items():
        doc = load(path)
        stamp = document_time(doc)
        if stamp is None:
            stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            source = "FILE_MTIME"
        else:
            source = "DOCUMENT_TIMESTAMP"
        age = max(0.0, (now - stamp).total_seconds())
        fresh = age <= max_age
        report[path.name] = {
            "fresh": fresh,
            "ageSec": round(age),
            "maxAgeSec": max_age,
            "timestampSource": source,
        }
        if not fresh:
            raise SystemExit(
                f"FAIL_CLOSED: stale input {path.name}: age={age:.0f}s max={max_age}s"
            )
    return report


def validate_contract():
    policy = load(CONTRACT_FILE)
    if policy.get("schema") != "EMS_CONTRACT_POLICY_V1.0":
        raise SystemExit("CONTRACT_CONFIG_ERROR: unsupported contract-policy schema")
    if policy.get("productionContractMode") != "FIXED":
        raise SystemExit("CONTRACT_CONFIG_ERROR: production contract must remain FIXED")
    if policy.get("productionContractId") != "ENGIE_3Y_2026_2029":
        raise SystemExit("CONTRACT_CONFIG_ERROR: unexpected production contract id")
    if policy.get("productionSupplier") != "ENGIE":
        raise SystemExit("CONTRACT_CONFIG_ERROR: unexpected production supplier")

    dynamic = policy.get("dynamicPricing") or {}
    safety = policy.get("safety") or {}
    if dynamic.get("enabledForProduction") is not False:
        raise SystemExit("CONTRACT_CONFIG_ERROR: dynamic pricing enabled for production")
    if safety.get("failClosed") is not True:
        raise SystemExit("CONTRACT_CONFIG_ERROR: failClosed must be true")
    if safety.get("fixedModeMustIgnoreDynamicPrices") is not True:
        raise SystemExit("CONTRACT_CONFIG_ERROR: fixed mode must ignore dynamic prices")
    if safety.get("automaticContractModeSwitchAllowed") is not False:
        raise SystemExit("CONTRACT_CONFIG_ERROR: automatic contract switching forbidden")
    return policy


def deadline_requirement(energy_state, now):
    tesla = energy_state.get("tesla") or {}
    if tesla.get("connected") is not True or tesla.get("deadline_active") is not True:
        return None

    deadline = parse_utc(tesla.get("deadline_at"))
    if deadline is None or deadline <= now:
        return None

    remaining = tesla.get("remaining_kwh")
    if remaining is None:
        raise SystemExit("FAIL_CLOSED: active Tesla deadline without remaining_kwh")
    remaining = max(0.0, float(remaining))

    # requested_a is the current actuator request, not necessarily the deadline cap.
    # The deadline command historically carries maxA; until that value is published
    # into energy-state, use the safe hardware planner maximum of 16 A.
    max_a = 16
    return {
        "deadline": deadline,
        "remainingKWh": remaining,
        "maxA": max_a,
    }


def apply_tesla_deadline(plan, requirement, now):
    """Validate the canonical Tesla deadline plan without modifying it.

    The Dynamic Pi planner is the sole Tesla deadline allocator.
    This hardened layer only verifies that the published action plan
    contains enough executable EV energy before the deadline.
    """
    if not requirement or requirement["remainingKWh"] <= 0:
        return {
            "active": False,
            "feasible": True,
            "remainingKWh": 0.0 if requirement else None,
            "plannedKWh": 0.0,
            "opportunityKWh": 0.0,
            "deadlineRequiredKWh": 0.0,
            "validatorOnly": True,
        }

    deadline = requirement["deadline"]
    needed_kwh = requirement["remainingKWh"]

    opportunity_kwh = 0.0
    deadline_kwh = 0.0
    total_kwh = 0.0
    planned_slots = 0

    for slot in plan.get("slots") or []:
        start = parse_utc(slot.get("slot_start_utc"))
        if start is None:
            continue

        # Allow the currently running quarter, matching planner semantics.
        if start < now - timedelta(minutes=15) or start >= deadline:
            continue

        ev_w = max(0.0, float(slot.get("evPlanW") or 0))
        if ev_w <= 0:
            continue

        kwh = ev_w * SLOT_H / 1000
        reason = str(slot.get("evAllocationReason") or "")

        total_kwh += kwh
        planned_slots += 1

        if reason == "DEADLINE_REQUIRED" or slot.get("evDeadlineRequired") is True:
            deadline_kwh += kwh
        elif (
            reason.startswith("DYNAMIC_PV_")
            or reason == "DYNAMIC_PV_PEAK_ABSORBER"
        ):
            opportunity_kwh += kwh

    feasible = total_kwh + 1e-9 >= needed_kwh

    canonical = (plan.get("tesla") or {}).get("deadlinePlan") or {}

    return {
        "active": True,
        "deadlineAt": iso_z(deadline),
        "remainingKWh": round(needed_kwh, 3),
        "plannedKWh": round(min(total_kwh, needed_kwh), 3),
        "plannedEnergyKWh": round(total_kwh, 3),
        "opportunityKWh": round(opportunity_kwh, 3),
        "deadlineRequiredKWh": round(deadline_kwh, 3),
        "plannedSlots": planned_slots,
        "feasible": feasible,
        "policy": "VALIDATE_CANONICAL_DEADLINE_PLAN_V0.2",
        "validatorOnly": True,
        "canonicalPolicy": canonical.get("policy"),
        "executorSafetyOwner": "HOMEY_EXACT_MINUTE_GUARD",
    }


def main():
    now = datetime.now(timezone.utc)
    policy = validate_contract()
    freshness = validate_freshness(now)
    energy_state = load(ENERGY_STATE_FILE)

    result = subprocess.run([sys.executable, str(BUILDER)], text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    plan = load(OUTPUT)
    if plan.get("mode") != "PURE_SHADOW" or plan.get("control_writes") is not False:
        raise SystemExit("FAIL_CLOSED: dynamic planner escaped PURE_SHADOW boundary")

    requirement = deadline_requirement(energy_state, now)
    deadline_status = apply_tesla_deadline(plan, requirement, now)

    valid_until = now + timedelta(minutes=PLAN_TTL_MIN)
    plan["schema"] = "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3"
    plan["generated_at"] = iso_z(now)
    plan["validUntil"] = iso_z(valid_until)
    plan["mode"] = "PURE_SHADOW"
    plan["readOnly"] = True
    plan["control_writes"] = False
    plan["plannerOwner"] = "PI"
    plan["executorContract"] = {
        "intendedExecutor": "HOMEY",
        "executionEnabled": False,
        "requiredPlannerOwner": "PI",
        "rejectAfterValidUntil": True,
        "rejectUnknownSchema": True,
        "stalePlanAction": "NO_OPPORTUNISTIC_STARTS_KEEP_LOCAL_SAFETY",
    }
    plan["contract"] = {
        "mode": policy["productionContractMode"],
        "id": policy["productionContractId"],
        "supplier": policy["productionSupplier"],
        "dynamicPricingUsedForProduction": False,
        "dynamicPricingAllowedUses": policy["dynamicPricing"]["allowedUses"],
        "automaticSwitchAllowed": False,
    }
    plan["inputFreshness"] = {
        "status": "PASS",
        "failClosed": True,
        "inputs": freshness,
    }
    plan["teslaDeadline"] = deadline_status
    plan.setdefault("guardrails", {})["contractPolicyEnforced"] = True
    plan["guardrails"]["inputFreshnessFailClosed"] = True
    plan["guardrails"]["teslaDeadlineHardConstraintWhenActive"] = True
    plan["guardrails"]["homeyPlannerMayBeDisabled"] = False
    plan["guardrails"]["cutoverGate"] = "REQUIRES_SHADOW_REPLAY_PASS"

    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, separators=(",", ":")) + "\n")
    tmp.replace(OUTPUT)

    print("PASS: hardened dynamic planner shadow contract v0.3")
    print("contract                  :", policy["productionContractId"])
    print("validUntil                :", iso_z(valid_until))
    print("Tesla deadline active     :", deadline_status["active"])
    print("Tesla deadline feasible   :", deadline_status["feasible"])
    print("control_writes            :", False)
    print("cutover                    : BLOCKED_PENDING_REPLAY_PASS")


if __name__ == "__main__":
    main()

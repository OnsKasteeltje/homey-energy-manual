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
ENERGY_STATE_FILE = REPO / "docs/data/energy-state-v2.json"
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
    if not requirement or requirement["remainingKWh"] <= 0:
        return {
            "active": False,
            "feasible": True,
            "remainingKWh": 0.0 if requirement else None,
            "plannedKWh": 0.0,
        }

    deadline = requirement["deadline"]
    max_a = requirement["maxA"]
    max_w = max_a * EV_W_PER_A
    needed_kwh = requirement["remainingKWh"]

    eligible = []
    for i, slot in enumerate(plan.get("slots") or []):
        start = parse_utc(slot.get("slot_start_utc"))
        if start is None:
            continue
        if start >= now - timedelta(minutes=15) and start < deadline:
            eligible.append(i)

    capacity_kwh = len(eligible) * max_w * SLOT_H / 1000
    feasible = capacity_kwh + 1e-9 >= needed_kwh

    # Preserve PV objective: fill the slots with the largest corrected residual
    # export first. Deadline feasibility, not market price, is the hard constraint.
    eligible.sort(
        key=lambda i: (
            float(plan["slots"][i].get("evResidualExportW") or 0),
            plan["slots"][i].get("slot_start_utc") or "",
        ),
        reverse=True,
    )

    remaining = needed_kwh
    planned = 0.0
    for i in eligible:
        if remaining <= 1e-9:
            break
        slot = plan["slots"][i]
        slot_capacity = max_w * SLOT_H / 1000
        # Round up to whole amps; never exceed maxA. Deadline charging is allowed
        # to import because reaching the explicit user goal is the hard constraint.
        required_w = min(max_w, remaining * 1000 / SLOT_H)
        amps = min(max_a, max(6, int(math.ceil(required_w / EV_W_PER_A))))
        ev_w = amps * EV_W_PER_A
        delivered = ev_w * SLOT_H / 1000

        slot["evPlanW"] = round(ev_w)
        slot["evPlanA"] = amps
        slot["evAllocationReason"] = "TESLA_DEADLINE_HARD_REQUIREMENT"
        slot["teslaDeadlineAt"] = iso_z(deadline)

        net_after = (
            float(slot.get("baseLoadForecastW") or 0)
            + float(slot.get("quattForecastW") or 0)
            + float(slot.get("wwPlanW") or 0)
            + ev_w
            - float(slot.get("pvForecastW") or 0)
        )
        slot["gridImportAfterFlexW"] = round(max(0.0, net_after))
        slot["gridExportAfterFlexW"] = round(max(0.0, -net_after))

        planned += delivered
        remaining = max(0.0, remaining - delivered)

    return {
        "active": True,
        "deadlineAt": iso_z(deadline),
        "remainingKWh": round(needed_kwh, 3),
        "plannedKWh": round(min(planned, needed_kwh), 3),
        "maxA": max_a,
        "capacityKWhBeforeDeadline": round(capacity_kwh, 3),
        "feasible": feasible,
        "policy": "HARD_DEADLINE_PV_BEST_SLOTS_FIRST_GRID_IMPORT_ALLOWED",
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

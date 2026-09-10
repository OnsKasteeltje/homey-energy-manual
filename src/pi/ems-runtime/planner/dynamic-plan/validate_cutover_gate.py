#!/usr/bin/env python3

"""Read-only cutover gate for the Pi dynamic planner.

A PASS here is necessary but not sufficient for production cut-over: measured
multi-day replay/PV-capture evidence is still required. This script never writes
to Homey or devices.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

PLAN = Path("/home/jeroen/ems/data/dynamic-shadow-plan.json")


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fail(reason):
    raise SystemExit("FAIL CUTOVER GATE: " + reason)


def main():
    try:
        plan = json.loads(PLAN.read_text())
    except Exception as exc:
        fail(f"cannot read plan: {exc}")

    now = datetime.now(timezone.utc)
    if plan.get("schema") != "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3":
        fail("hardened v0.3 plan required")
    if plan.get("mode") != "PURE_SHADOW":
        fail("mode must remain PURE_SHADOW")
    if plan.get("readOnly") is not True or plan.get("control_writes") is not False:
        fail("read-only boundary violated")
    if plan.get("plannerOwner") != "PI":
        fail("plannerOwner must be PI")

    valid_until = parse_utc(plan.get("validUntil") or "1970-01-01T00:00:00Z")
    if valid_until <= now:
        fail("plan is stale")

    contract = plan.get("contract") or {}
    if contract.get("mode") != "FIXED":
        fail("production contract is not FIXED")
    if contract.get("id") != "ENGIE_3Y_2026_2029":
        fail("unexpected production contract")
    if contract.get("dynamicPricingUsedForProduction") is not False:
        fail("dynamic pricing leaked into production contract")
    if contract.get("automaticSwitchAllowed") is not False:
        fail("automatic contract switching is enabled")

    freshness = plan.get("inputFreshness") or {}
    if freshness.get("status") != "PASS" or freshness.get("failClosed") is not True:
        fail("input freshness gate not passed")
    for name, status in (freshness.get("inputs") or {}).items():
        if status.get("fresh") is not True:
            fail(f"stale input: {name}")

    if plan.get("slot_count") != 96 or len(plan.get("slots") or []) != 96:
        fail("expected exactly 96 aligned slots")

    for day in plan.get("dailyPlans") or []:
        if day.get("comfortFeasible") is not True:
            fail(f"WW comfort infeasible for {day.get('date')}")

    tesla = plan.get("teslaDeadline") or {}
    if tesla.get("active") is True and tesla.get("feasible") is not True:
        fail("active Tesla deadline is infeasible")

    executor = plan.get("executorContract") or {}
    if executor.get("executionEnabled") is not False:
        fail("Homey execution must remain disabled during validation")
    if executor.get("rejectAfterValidUntil") is not True:
        fail("executor stale-plan rejection missing")

    print("PASS: Pi dynamic planner structural cutover gate")
    print("NOTE: Homey planner must remain enabled; multi-day shadow/replay evidence is still required.")


if __name__ == "__main__":
    main()

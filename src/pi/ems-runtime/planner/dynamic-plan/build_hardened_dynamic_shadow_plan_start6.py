#!/usr/bin/env python3

"""Hardened Dynamic Pi Planner entrypoint for START6 / 15-minute EV policy.

Safety correction 2026-09-12:
- opportunity charging may start at 6 A;
- a single positive 15-minute slot may qualify;
- deadline-forced grid charging may only be overlaid at/after Homey's
  latest_start_at. Before latest-start, normal PV opportunity planning remains
  authoritative.
"""

import importlib.util
from pathlib import Path

BASE = Path(__file__).with_name("build_hardened_dynamic_shadow_plan.py")
START6_BUILDER = Path("/home/jeroen/ems/runtime/planner/dynamic-plan/build_dynamic_shadow_plan_start6.py")

spec = importlib.util.spec_from_file_location("ems_hardened_dynamic_base", BASE)
hardened = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardened)
hardened.BUILDER = START6_BUILDER

_base_deadline_requirement = hardened.deadline_requirement
_base_apply_tesla_deadline = hardened.apply_tesla_deadline


def deadline_requirement_latest_start(energy_state, now):
    """Extend the base requirement with the canonical Homey latest-start time."""
    requirement = _base_deadline_requirement(energy_state, now)
    if not requirement:
        return requirement

    tesla = energy_state.get("tesla") or {}
    latest_start = hardened.parse_utc(tesla.get("latest_start_at"))
    if latest_start is None:
        raise SystemExit("FAIL_CLOSED: active Tesla deadline without latest_start_at")
    if latest_start >= requirement["deadline"]:
        raise SystemExit("FAIL_CLOSED: Tesla latest_start_at is not before deadline")

    requirement["latestStart"] = latest_start
    return requirement


def apply_tesla_deadline_from_latest_start(plan, requirement, now):
    """Never force deadline charging before latest-start.

    The base deadline allocator is retained unchanged, but it receives only
    slots at/after latest-start. Slot dictionaries are shared with the original
    plan, so any legitimate deadline overlay still updates the canonical plan.
    """
    if not requirement or requirement.get("remainingKWh", 0) <= 0:
        return _base_apply_tesla_deadline(plan, requirement, now)

    latest_start = requirement.get("latestStart")
    if latest_start is None:
        raise SystemExit("FAIL_CLOSED: deadline requirement missing latestStart")

    eligible_slots = []
    for slot in plan.get("slots") or []:
        start = hardened.parse_utc(slot.get("slot_start_utc"))
        if start is not None and start >= latest_start:
            eligible_slots.append(slot)

    proxy = dict(plan)
    proxy["slots"] = eligible_slots
    result = _base_apply_tesla_deadline(proxy, requirement, now)
    result["latestStartAt"] = hardened.iso_z(latest_start)
    result["policy"] = "HARD_DEADLINE_FROM_LATEST_START_PV_BEST_SLOTS_GRID_IMPORT_ALLOWED"
    result["preLatestStartForcedChargingAllowed"] = False
    return result


hardened.deadline_requirement = deadline_requirement_latest_start
hardened.apply_tesla_deadline = apply_tesla_deadline_from_latest_start

if __name__ == "__main__":
    hardened.main()

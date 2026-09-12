#!/usr/bin/env python3

"""START6 / 15-minute opportunity policy wrapper for the Dynamic Pi Planner.

Keeps the canonical planner implementation unchanged while overriding only the
validated Tesla opportunity policy:
- a stopped Tesla may start at 6 A;
- one 15-minute profitable slot is enough to qualify an opportunity;
- every following profitable slot is evaluated independently, so charging
  continues quarter-by-quarter while PV remains worthwhile.

Deadline, WW, contract and fail-closed behaviour remain owned by the canonical
planner and hardened wrapper.
"""

import importlib.util
from pathlib import Path

BASE = Path(__file__).with_name("build_dynamic_shadow_plan.py")

spec = importlib.util.spec_from_file_location("ems_dynamic_shadow_base", BASE)
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

planner.EV_KICKSTART_A = 6
planner.EV_RUN_MIN_A = 6
planner.EV_RUN_MIN_W = planner.EV_RUN_MIN_A * planner.EV_W_PER_A
planner.EV_MIN_WINDOW_SLOTS = 1

if __name__ == "__main__":
    planner.main()

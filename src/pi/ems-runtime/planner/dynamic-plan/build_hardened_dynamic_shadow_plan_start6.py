#!/usr/bin/env python3

"""Hardened Dynamic Pi Planner entrypoint for START6 / 15-minute EV policy."""

import importlib.util
from pathlib import Path

BASE = Path(__file__).with_name("build_hardened_dynamic_shadow_plan.py")
START6_BUILDER = Path("/home/jeroen/ems/runtime/planner/dynamic-plan/build_dynamic_shadow_plan_start6.py")

spec = importlib.util.spec_from_file_location("ems_hardened_dynamic_base", BASE)
hardened = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardened)
hardened.BUILDER = START6_BUILDER

if __name__ == "__main__":
    hardened.main()

#!/usr/bin/env python3
"""Regression for unplugged EV actuator semantics in EMS AI analysis."""

import importlib.util
from pathlib import Path


SERVER = Path("services/pi/api/analysis/server.py")
spec = importlib.util.spec_from_file_location("ems_ai_analysis_server", SERVER)
server = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(server)


instructions = server.SYSTEM_INSTRUCTIONS

required = [
    "physical connection and measured charging evidence outrank actuator/controller state",
    "If evControlEvents[].chargeState is plugged_out",
    "FAILED, PAUSE_CONFIRM_TIMEOUT, STABLE",
    "only as controller diagnostics",
    "they are not evidence that a vehicle was connected, charging, paused, or in a charging session",
    "Prefer explicit chargeState plus measured Easee power/energy over actuator status",
]

for phrase in required:
    assert phrase in instructions, phrase

assert "A plugged_out event with targetW=0 or actuatorTargetA=0 must not be described as a missed or interrupted charging session" in instructions

print("PASS: EMS AI treats plugged_out EV actuator failures as controller diagnostics")

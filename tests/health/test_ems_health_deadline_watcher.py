#!/usr/bin/env python3
"""Regression: local EV deadline command watcher is a systemd .path unit."""

import importlib.util
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/health/ems_health.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_health_deadline_watcher", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    health = load_module()
    assert health.FUNCTION_UNITS["evDeadlineCommand"] == {
        "unit": "ems-ev-deadline-command.path",
    }
    assert health.FUNCTION_UNITS["evDeadlineState"] == {
        "unit": "ems-ev-deadline-state.timer",
        "service": "ems-ev-deadline-state.service",
    }

    observed_units = []

    def systemctl(unit, expected_active=True):
        observed_units.append(unit)
        if unit == "ems-ev-deadline-command.path":
            assert expected_active is True
        return {
            "unit": unit,
            "status": "OK",
            "ActiveState": "active",
            "LoadState": "loaded",
            "Result": "success",
        }

    def execution(unit):
        observed_units.append(unit)
        return {
            "unit": unit,
            "status": "OK",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
            "ExecMainExitTimestamp": "2026-10-14 07:55:00 CEST",
        }

    with mock.patch.object(health, "_systemctl_show", side_effect=systemctl), \
         mock.patch.object(health, "_execution_status", side_effect=execution):
        functions, degraded = health._functions_status()

    assert degraded is False
    assert functions["evDeadlineCommand"]["status"] == "OK"
    assert functions["evDeadlineState"]["status"] == "OK"
    assert "ems-ev-deadline-command.path" in observed_units
    assert "ems-ev-deadline-state.service" in observed_units
    assert "ems-ev-deadline-command.timer" not in observed_units
    assert "ems-ev-deadline-command.service" not in observed_units

    def inactive_path(unit, expected_active=True):
        if unit == "ems-ev-deadline-command.path":
            return {"unit": unit, "status": "DEGRADED", "ActiveState": "inactive"}
        return systemctl(unit, expected_active)

    with mock.patch.object(health, "_systemctl_show", side_effect=inactive_path), \
         mock.patch.object(health, "_execution_status", side_effect=execution):
        functions, degraded = health._functions_status()
    assert degraded is True
    assert functions["evDeadlineCommand"]["status"] == "DEGRADED"

    def failed_state_execution(unit):
        if unit == "ems-ev-deadline-state.service":
            return {"unit": unit, "status": "DEGRADED", "ExecMainStatus": "1"}
        return execution(unit)

    with mock.patch.object(health, "_systemctl_show", side_effect=systemctl), \
         mock.patch.object(health, "_execution_status", side_effect=failed_state_execution):
        functions, degraded = health._functions_status()
    assert degraded is True
    assert functions["evDeadlineState"]["status"] == "DEGRADED"

    print("PASS: EMS health EV deadline path watcher contract")


if __name__ == "__main__":
    main()

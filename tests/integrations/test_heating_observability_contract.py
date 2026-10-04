#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/health/ems_health.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_health_heating_contract", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    m = load_module()

    expected_data = {
        "heatingPreheatV03": 420,
        "flexPriorityV01": 120,
        "heatingProgressionV04": 120,
        "heatingControlGateV05": 120,
    }
    for key, max_age in expected_data.items():
        assert key in m.DATA_SOURCES
        assert m.DATA_SOURCES[key][2] == max_age

    expected_units = {
        "heatingPreheatV03": (
            "ems-heating-preheat-shadow.timer",
            "ems-heating-preheat-shadow.service",
        ),
        "flexPriorityV01": (
            "ems-flex-priority-shadow.timer",
            "ems-flex-priority-shadow.service",
        ),
        "heatingProgressionV04": (
            "ems-heating-preheat-progression-shadow.timer",
            "ems-heating-preheat-progression-shadow.service",
        ),
        "heatingControlGateV05": (
            "ems-heating-control-gate-shadow.timer",
            "ems-heating-control-gate-shadow.service",
        ),
    }
    for key, (timer, service) in expected_units.items():
        spec = m.FUNCTION_UNITS[key]
        assert spec["unit"] == timer
        assert spec["service"] == service
        assert spec["proofData"] == key

    def fake_systemctl(unit, expected_active=True):
        if unit.endswith(".timer"):
            return {
                "unit": unit,
                "status": "OK",
                "ActiveState": "active",
                "Result": "success",
                "LastTriggerUSec": "Sun 2026-10-04 11:13:33 CEST",
            }
        return {
            "unit": unit,
            "status": "OK",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
            "ExecMainExitTimestamp": "",
        }

    original_systemctl = m._systemctl_show
    original_units = m.FUNCTION_UNITS
    m._systemctl_show = fake_systemctl
    m.FUNCTION_UNITS = {
        key: original_units[key]
        for key in expected_units
    }
    try:
        data = {key: {"status": "OK"} for key in expected_data}
        functions, degraded = m._functions_status(data)
        assert degraded is False
        for key in expected_units:
            item = functions[key]
            assert item["status"] == "OK"
            assert item["lastExecution"]["status"] == "NOT_PROVEN"
            assert item["executionProof"]["status"] == "OK"
            assert item["executionProof"]["method"] == "TIMER_TRIGGER_PLUS_FRESH_ARTIFACT"

        stale = dict(data)
        stale["heatingControlGateV05"] = {"status": "STALE"}
        functions, degraded = m._functions_status(stale)
        assert degraded is True
        assert functions["heatingControlGateV05"]["status"] == "DEGRADED"
    finally:
        m._systemctl_show = original_systemctl
        m.FUNCTION_UNITS = original_units

    print("PASS: Heating V0.3 -> Flex -> V0.4 -> V0.5 health contract")


if __name__ == "__main__":
    main()

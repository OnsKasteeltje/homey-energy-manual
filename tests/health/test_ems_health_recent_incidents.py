#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/health/ems_health.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_health_contract", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeProc:
    returncode = 0
    stderr = ""

    def __init__(self, rows):
        self.stdout = "\n".join(json.dumps(row) for row in rows)


def main():
    health = load_module()

    base_us = 1791261983000000
    rows = [
        {
            "SYSLOG_IDENTIFIER": "systemd",
            "_COMM": "systemd",
            "_PID": "1",
            "_SYSTEMD_UNIT": "init.scope",
            "__REALTIME_TIMESTAMP": str(base_us),
            "PRIORITY": "3",
            "MESSAGE": (
                "ems-weather-forecast.service: "
                "Failed with result 'exit-code'."
            ),
        },
        {
            "SYSLOG_IDENTIFIER": "systemd",
            "_COMM": "systemd",
            "_PID": "1",
            "_SYSTEMD_UNIT": "init.scope",
            "__REALTIME_TIMESTAMP": str(base_us + 200000),
            "PRIORITY": "3",
            "MESSAGE": (
                "Failed to start ems-weather-forecast.service - "
                "EMS Weather Forecast Fetcher."
            ),
        },
        {
            "_SYSTEMD_UNIT": "ems-honeywell-state.service",
            "__REALTIME_TIMESTAMP": str(base_us + 20_000_000),
            "PRIORITY": "4",
            "MESSAGE": "Honeywell request timeout",
        },
        {
            "SYSLOG_IDENTIFIER": "systemd",
            "_COMM": "systemd",
            "_PID": "1",
            "__REALTIME_TIMESTAMP": str(base_us + 30_000_000),
            "PRIORITY": "3",
            "MESSAGE": "unrelated.service: Failed with result 'exit-code'.",
        },
    ]

    def fake_run(*args, **kwargs):
        assert args[0][0] == "journalctl"
        return FakeProc(rows)

    health.subprocess.run = fake_run
    incidents = health._recent_incidents()
    events = incidents["events"]

    assert incidents["coverage"] == "JOURNAL_24H_BEST_EFFORT"
    assert len(events) == 2, events
    assert events[0]["unit"] == "ems-weather-forecast.service"
    assert events[0]["kind"] == "SYSTEMD_FAILURE"
    assert "Failed with result" in events[0]["message"]
    assert events[1]["unit"] == "ems-honeywell-state.service"
    assert events[1]["kind"] == "JOURNAL_WARNING"

    health._data_status = lambda: ({}, False)
    health._functions_status = lambda _data=None: ({}, False)
    health._system_status = lambda: {}
    snapshot = health.build_health()
    assert snapshot["status"] == "HEALTHY_WITH_RECENT_INCIDENTS"

    health._functions_status = lambda _data=None: ({}, True)
    degraded = health.build_health()
    assert degraded["status"] == "DEGRADED"

    print("PASS: EMS health recent systemd incident contract")


if __name__ == "__main__":
    main()

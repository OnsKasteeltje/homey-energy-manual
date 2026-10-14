#!/usr/bin/env python3
"""Standalone read-only daily report web API archive test, no pytest."""
import importlib.util
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path("services/pi/api/web-data/server.py")
spec = importlib.util.spec_from_file_location("ems_web_daily_report", SOURCE)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

day = (datetime.now(ZoneInfo("Europe/Amsterdam")).date() - timedelta(days=2)).isoformat()
report = {
    "schema": "EMS_PI_DAILY_PERFORMANCE_EVALUATION_V0.1",
    "dateLocal": day, "readOnly": True, "controlWrites": False, "status": "READY",
    "accounting": {
        "authority": "P1_CUMULATIVE_ENERGY_COUNTERS",
        "gridImportKWh": 9.603, "gridExportKWh": 3.347,
        "pvProducedKWh": 8.748, "pvSelfConsumedKWh": 5.401,
        "pvSelfConsumptionRate": .6174, "p1Coverage": 1.0, "pairedCoverage": 1.0,
    },
    "evReplay": {
        "energyAuthority": "SAMPLED_POWER_ESTIMATE_NOT_P1_COUNTER",
        "available": True, "estimatedAdditionalFeasibleCaptureKWh": .0035,
    },
    "quality": {"issues": ["REVIEW_PV_P1_SAMPLE_ALIGNMENT"]},
    "lines": [
        "P1 gemeten: 9.603 kWh import, 3.347 kWh export.",
        "PV: 8.748 kWh opgewekt, 61.7% zelfverbruik.",
        "EV-only replay: circa 0.0035 kWh extra opname; geschat.",
        "PV/P1 tijdalignering controleren.",
    ],
    "private_secret_do_not_expose": "must never be returned",
}

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "daily-performance-archive.json"
    api.DAILY_PERFORMANCE_ARCHIVE_FILE = str(path)
    archive = {"schema": "EMS_PI_DAILY_PERFORMANCE_ARCHIVE_V0.1", "days": {day: report}}
    path.write_text(json.dumps(archive), encoding="utf-8")

    result = api.daily_performance_resource(day)
    assert result["schema"] == "EMS_WEB_DAILY_PERFORMANCE_V1"
    assert result["dateLocal"] == day
    assert result["readOnly"] is True and result["controlWrites"] is False
    assert result["accounting"]["gridExportKWh"] == 3.347
    assert result["accounting"]["pvSelfConsumptionRate"] == .6174
    assert result["evReplay"]["estimatedAdditionalFeasibleCaptureKWh"] == .0035
    assert "private_secret_do_not_expose" not in json.dumps(result)
    assert api.daily_performance_resource("2020-01-02") is None

    for invalid in ("today", "2026-02-30", "2026-10-13/../../secret",
                    datetime.now(ZoneInfo("Europe/Amsterdam")).date().isoformat()):
        try:
            api.daily_performance_resource(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Open/invalid day unexpectedly accepted")

    archive["days"][day]["controlWrites"] = True
    path.write_text(json.dumps(archive), encoding="utf-8")
    try:
        api.daily_performance_resource(day)
    except RuntimeError:
        pass
    else:
        raise AssertionError("non-read-only report unexpectedly accepted")

source = SOURCE.read_text(encoding="utf-8")
assert '["web", "analysis", "performance", "day"]' in source
assert "import subprocess" not in source
assert 'load_json(DAILY_PERFORMANCE_ARCHIVE_FILE)' in source
assert "DAILY_PERFORMANCE_ARCHIVE_FILE" in source
assert "DAY_REPORT_NOT_ARCHIVED" in source
print("PASS: read-only daily performance archive and web allowlist contract")

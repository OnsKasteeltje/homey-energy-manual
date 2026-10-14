#!/usr/bin/env python3
"""Standalone, DB-free regressions; no pytest dependency."""

import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/history/daily_performance_evaluation.py"
spec = importlib.util.spec_from_file_location("daily_performance_evaluation", SOURCE)
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)

DAY = date(2026, 10, 13)
PERF = {
    "schema": "EMS_PI_DAY_PERFORMANCE_V0.1",
    "dateLocal": DAY.isoformat(),
    "quality": {"status": "GOOD"},
    "energyAccounting": {
        "available": True, "p1Coverage": 1.0, "pairedCoverage": 1.0,
        "importKWh": 9.602992, "exportKWh": 3.347,
        "pvKWh": 8.748, "pvSelfConsumedKWh": 5.401,
        "pvSelfConsumptionRate": 0.6174,
        "sourceQualityCounts": {"pv": {"observed": 3, "held": 170, "estimated": 115}},
    },
    "powerSampleQuality": {"impossibleExportIntervals": 10},
}
REPLAY = {
    "schema": "EMS_PI_CONSTRAINED_REPLAY_V0.1.1",
    "scope": "EV_EXPORT_ONLY", "readOnly": True, "controlWrites": False,
    "coverage": {"integratedHours": 23.917},
    "totals": {
        "observedGridExportKWh": 3.7452,
        "additionalFeasibleCaptureKWh": 0.0035,
        "byClassificationKWh": {"UNAVOIDABLE_EXPORT": 2.0677},
    },
}
NOW = datetime(2026, 10, 14, 7, 0, tzinfo=timezone.utc)


def main():
    result = daily.build_digest(DAY, PERF, REPLAY, now=NOW)
    assert result["status"] == "READY"
    assert result["accounting"]["gridExportKWh"] == 3.347
    assert result["accounting"]["pvSelfConsumptionRate"] == 0.6174
    assert result["evReplay"]["estimatedAdditionalFeasibleCaptureKWh"] == 0.0035
    assert result["evReplay"]["energyAuthority"] == "SAMPLED_POWER_ESTIMATE_NOT_P1_COUNTER"
    assert result["evReplay"]["estimatedByClassificationKWh"]["UNAVOIDABLE_EXPORT"] == 2.0677
    assert result["quality"]["issues"] == ["REVIEW_PV_P1_SAMPLE_ALIGNMENT"]
    assert result["readOnly"] and not result["controlWrites"]
    assert len(result["lines"]) == 4
    assert "3.7452" not in " ".join(result["lines"])
    assert "3.347" in result["lines"][0]

    # Fail closed: P1 counter coverage below threshold never falls back to replay kWh.
    bad_perf = {**PERF, "energyAccounting": {**PERF["energyAccounting"], "p1Coverage": 0.80}}
    bad = daily.build_digest(DAY, bad_perf, REPLAY)
    assert bad["status"] == "INSUFFICIENT_EVIDENCE"
    assert bad["accounting"]["gridExportKWh"] is None
    assert "P1_COUNTER_ENERGY_UNAVAILABLE" in bad["quality"]["issues"]

    missing = daily.build_digest(DAY, PERF, None)
    assert missing["status"] == "PARTIAL"
    assert missing["accounting"]["gridExportKWh"] == 3.347
    assert missing["evReplay"]["estimatedAdditionalFeasibleCaptureKWh"] is None

    # The Amsterdam day can be 23 or 25 hours; compare replay coverage to its actual length.
    dst_day = date(2026, 10, 25)  # 25-hour autumn clock change
    dst_perf = {**PERF, "dateLocal": dst_day.isoformat()}
    short = {**REPLAY, "coverage": {"integratedHours": 22.0}}
    dst = daily.build_digest(dst_day, dst_perf, short)
    assert dst["status"] == "PARTIAL"
    assert not dst["evReplay"]["available"]

    try:
        daily.build_digest(date(2026, 10, 12), PERF, REPLAY)
    except ValueError as exc:
        assert "date mismatch" in str(exc)
    else:
        raise AssertionError("Mismatched performance date must fail closed")

    print("PASS: deterministic daily EMS performance evaluation; P1 authority preserved")


if __name__ == "__main__":
    main()

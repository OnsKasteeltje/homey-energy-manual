#!/usr/bin/env python3

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("ems_ai_analysis_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ai = load_server()


def fixture_payload():
    return {
        "schema": "EMS_PI_CONSTRAINED_REPLAY_V0.1.1",
        "scope": "EV_EXPORT_ONLY",
        "readOnly": True,
        "controlWrites": False,
        "coverage": {
            "integratedHours": 22.75,
            "insufficientEvidenceExportKWh": 0.0,
        },
        "totals": {
            "observedGridExportKWh": 6.8958,
            "byClassificationKWh": {
                "CONSTRAINT_DRIVEN_EXPORT": 5.1359,
                "INSUFFICIENT_EVIDENCE": 0.0,
                "REAL_MISSED_OPPORTUNITY": 0.22,
                "UNAVOIDABLE_EXPORT": 1.3829,
            },
            "realMissedOpportunityCaptureKWh": 0.1887,
        },
        "reasonEnergyKWh": {
            "DOWNSTREAM_OFFER_BELOW_REQUEST": 3.0805,
            "OFF_REENTRY_DWELL_ACTIVE": 1.1023,
        },
        "windows": [
            {
                "start": "2026-10-04T10:31:02Z",
                "end": "2026-10-04T10:33:02Z",
                "classification": "REAL_MISSED_OPPORTUNITY",
                "primaryReason": "OFF_TO_1P_FEASIBLE_NOT_TAKEN",
                "reasons": ["OFF_TO_1P_FEASIBLE_NOT_TAKEN"],
                "phaseModes": ["OFF"],
                "controlReasons": ["MODE_OFF"],
                "exportKWh": 0.1396,
                "additionalFeasibleCaptureKWh": 0.1227,
                "peakExportW": 4200,
                "confidence": "MEDIUM",
                "semanticEvents": [],
            },
            {
                "start": "2026-10-04T09:00:00Z",
                "end": "2026-10-04T09:05:00Z",
                "classification": "CONSTRAINT_DRIVEN_EXPORT",
                "primaryReason": "DOWNSTREAM_OFFER_BELOW_REQUEST",
                "reasons": ["DOWNSTREAM_OFFER_BELOW_REQUEST"],
                "phaseModes": ["1P"],
                "controlReasons": ["HOLD_A"],
                "exportKWh": 0.32,
                "additionalFeasibleCaptureKWh": 0.0,
                "peakExportW": 3900,
                "confidence": "MEDIUM",
                "semanticEvents": [],
            },
            {
                "start": "2026-10-04T10:46:02Z",
                "end": "2026-10-04T10:47:02Z",
                "classification": "REAL_MISSED_OPPORTUNITY",
                "primaryReason": "3P_PROMOTION_FEASIBLE_NOT_TAKEN",
                "reasons": ["3P_PROMOTION_FEASIBLE_NOT_TAKEN"],
                "phaseModes": ["1P"],
                "controlReasons": ["HOLD_A"],
                "exportKWh": 0.0353,
                "additionalFeasibleCaptureKWh": 0.0304,
                "peakExportW": 2500,
                "confidence": "MEDIUM",
                "semanticEvents": [],
            },
        ],
        "limitations": [
            "UNAVOIDABLE_EXPORT is EV-relative only.",
        ],
    }


def main():
    payload = fixture_payload()

    day_projection = ai._project_constrained_replay(payload, [])
    assert day_projection["available"] is True
    assert day_projection["schema"] == "EMS_PI_CONSTRAINED_REPLAY_V0.1.1"
    assert day_projection["scope"] == "EV_EXPORT_ONLY"
    assert day_projection["readOnly"] is True
    assert day_projection["controlWrites"] is False
    assert day_projection["totals"]["realMissedOpportunityCaptureKWh"] == 0.1887
    assert day_projection["windowSelection"] == "REAL_MISSES_THEN_LARGEST_EXPORT"
    assert day_projection["selectedWindows"][0]["classification"] == "REAL_MISSED_OPPORTUNITY"
    assert (
        day_projection["selectedWindows"][0]["additionalFeasibleCaptureKWh"]
        == 0.1227
    )

    anchor = datetime(2026, 10, 4, 10, 45, tzinfo=timezone.utc)
    scoped = ai._project_constrained_replay(payload, [anchor])
    assert scoped["windowSelection"] == "AROUND_ANALYSIS_ANCHORS"
    assert len(scoped["selectedWindows"]) == 2
    assert all(
        row["classification"] == "REAL_MISSED_OPPORTUNITY"
        for row in scoped["selectedWindows"]
    )

    completed = subprocess.CompletedProcess(
        args=["ems-constrained-replay"],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )
    with mock.patch.object(ai.subprocess, "run", return_value=completed) as run:
        loaded = ai._load_constrained_replay(
            datetime(2026, 10, 4, tzinfo=timezone.utc).date()
        )
    assert loaded["schema"] == "EMS_PI_CONSTRAINED_REPLAY_V0.1.1"
    args = run.call_args.args[0]
    assert args[-1] == "--no-write-output"
    assert "2026-10-04" in args

    with mock.patch.object(
        ai.subprocess,
        "run",
        side_effect=FileNotFoundError("ems-constrained-replay missing"),
    ):
        unavailable = ai._load_constrained_replay(
            datetime(2026, 10, 4, tzinfo=timezone.utc).date()
        )
    assert unavailable["available"] is False
    assert unavailable["reason"] == "CONSTRAINED_REPLAY_COMMAND_UNAVAILABLE"

    invalid = subprocess.CompletedProcess(
        args=["ems-constrained-replay"],
        returncode=0,
        stdout=json.dumps({"schema": "OLD"}),
        stderr="",
    )
    with mock.patch.object(ai.subprocess, "run", return_value=invalid):
        rejected = ai._load_constrained_replay(
            datetime(2026, 10, 4, tzinfo=timezone.utc).date()
        )
    assert rejected["available"] is False
    assert rejected["reason"] == "CONSTRAINED_REPLAY_SCHEMA_INVALID"

    source = SERVER.read_text(encoding="utf-8")
    assert "EMS_CONSTRAINED_REPLAY_COMMAND" in source
    assert '"constrainedReplay": constrained_replay' in source
    assert "never relabel UNAVOIDABLE_EXPORT" in source
    assert "EV_EXPORT_ONLY" in source
    assert "do not claim more counterfactual capture than the replay reports" in source

    print("PASS: AI constrained replay evidence contract")


if __name__ == "__main__":
    main()

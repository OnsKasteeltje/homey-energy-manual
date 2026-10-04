#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_ai_evidence_quality_contract", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ai = load_module()

    inactive = ai._deadline_semantics(
        {
            "deadlineActive": False,
            "remainingKWh": 3.85,
            "deadlineAt": "2026-09-20T07:00:00Z",
        },
        "2026-10-04T08:00:00+02:00",
    )
    assert inactive["effective"] is False
    assert inactive["state"] == "INACTIVE"

    stale_active = ai._deadline_semantics(
        {
            "deadlineActive": True,
            "remainingKWh": 3.85,
            "deadlineAt": "2026-10-02T18:00:00Z",
            "status": "TRACKING",
        },
        "2026-10-04T08:00:00+02:00",
    )
    assert stale_active["effective"] is False
    assert stale_active["state"] == "EXPIRED_OR_STALE"

    active = ai._deadline_semantics(
        {
            "active": True,
            "remainingKWh": 5.0,
            "deadlineAt": "2026-10-04T18:00:00Z",
            "status": "TRACKING",
        },
        "2026-10-04T08:00:00+02:00",
    )
    assert active["effective"] is True
    assert active["state"] == "ACTIVE"

    telemetry = [{
        "atLocal": "2026-10-04T08:00:00+02:00",
        "deadlineActive": False,
        "remainingKWh": 3.85,
        "deadlineAt": "2026-09-20T07:00:00Z",
    }]
    planner = [{
        "snapshotGeneratedAtLocal": "2026-10-04T08:00:00+02:00",
        "deadline": {
            "active": False,
            "remainingKWh": 3.85,
            "deadlineAt": "2026-09-20T07:00:00Z",
        },
    }]
    flex = [{
        "snapshotCapturedAtLocal": "2026-10-04T08:00:00+02:00",
        "priority": {
            "ev": {
                "deadlineActive": True,
                "remainingKWh": 3.85,
                "deadlineAt": "2026-10-02T18:00:00Z",
                "urgency": "AVAILABLE_LATER",
            }
        },
    }]

    ai._annotate_deadline_semantics(telemetry, planner, flex)

    assert telemetry[0]["deadlineSemantics"]["state"] == "INACTIVE"
    assert planner[0]["deadline"]["deadlineSemantics"]["effective"] is False
    assert flex[0]["priority"]["ev"]["deadlineSemantics"]["state"] == "EXPIRED_OR_STALE"

    instructions = ai.SYSTEM_INSTRUCTIONS
    assert "directly observed device-state fields" in instructions
    assert "washerActive" in instructions
    assert "dryerActive" in instructions
    assert "mention that state as a Feit" in instructions
    assert "Never equate an active device state with measured power attribution" in instructions

    print("PASS: AI evidence quality semantics contract")


if __name__ == "__main__":
    main()

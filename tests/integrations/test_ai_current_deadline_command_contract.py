#!/usr/bin/env python3
import importlib.util
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "ems_ai_current_deadline_command_contract",
        SERVER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ai = load_module()
    today = datetime.now(ai.LOCAL_TZ).date()

    with tempfile.TemporaryDirectory() as temp:
        command_file = Path(temp) / "tesla-deadline-command.json"
        command = {
            "schema": 2,
            "requestId": "req-current-1",
            "requestedAt": datetime.now(ai.LOCAL_TZ).isoformat(),
            "source": "website",
            "active": True,
            "deadline": f"{today.isoformat()}T22:15",
            "currentSoc": 94,
            "targetSoc": 99,
            "goalKWh": 3.1,
            "maxA": 10,
        }
        command_file.write_text(json.dumps(command), encoding="utf-8")
        ai.EV_DEADLINE_COMMAND_FILE = str(command_file)

        current = ai._current_deadline_command(today)
        assert current["available"] is True
        assert current["authority"] == "CURRENT_USER_INTENT_COMMAND"
        assert current["provenanceClass"] == "USER_INTENT_COMMAND"
        assert current["requestId"] == "req-current-1"
        assert current["deadline"].endswith("T22:15")
        assert current["currentSoc"] == 94
        assert current["targetSoc"] == 99
        assert current["maxA"] == 10
        assert current["requestedAtLocal"]

        historical = ai._current_deadline_command(today - timedelta(days=1))
        assert historical == {
            "available": False,
            "reason": "NOT_CURRENT_DAY",
            "provenanceClass": "USER_INTENT_COMMAND",
        }

        ai._load_performance = lambda _day: {
            "schema": "EMS_PI_DAY_PERFORMANCE_V0.1",
            "surplusWindowsForReplay": [],
        }
        ai._ev_control_events = lambda _day: [{
            "atLocal": datetime.now(ai.LOCAL_TZ).isoformat(),
            "targetW": 6900,
            "requestedA": 10,
            "phaseMode": "3P",
            "intentReason": "HOMEY_EXECUTOR_DEADLINE_GUARD",
            "physicalWritePerformed": True,
        }]
        ai._ev_telemetry = lambda _day: []
        ai._quooker_events = lambda _day: []
        ai._semantic_events = lambda _day: (
            [],
            {
                "available": True,
                "schema": "EMS_PI_SEMANTIC_EVENT_ARCHIVE_V0.1",
                "commissionedAt": datetime.now(ai.LOCAL_TZ).isoformat(),
                "historicalBackfill": False,
                "eventCount": 0,
                "oldestEventAt": None,
                "newestEventAt": None,
            },
        )
        ai._timeline = lambda _day: []
        ai._load_health = lambda: {
            "schema": "EMS_PI_HEALTH_V0.1",
            "status": "HEALTHY",
        }
        ai._planner_decision_window = lambda _day, _anchors: []
        ai._flex_context_window = lambda _day, _anchors: []
        ai._forecast_vs_actual_15m = lambda _day, _anchors: {
            "available": True,
            "summary": {},
            "slots": [],
        }
        ai._apply_model_input_budget = lambda evidence, *_args: evidence

        evidence = ai.build_evidence(
            today,
            "Wat is de laatste deadline opdracht die je ziet?",
        )
        assert evidence["currentDeadlineCommand"]["requestId"] == "req-current-1"
        assert evidence["currentDeadlineCommand"]["authority"] == "CURRENT_USER_INTENT_COMMAND"
        assert evidence["evControlEvents"][0]["intentReason"] == "HOMEY_EXECUTOR_DEADLINE_GUARD"
        assert "currentDeadlineCommand" in evidence["sourceAuthority"]

        summary = ai._evidence_summary(evidence)
        assert summary["currentDeadlineCommand"]["requestId"] == "req-current-1"

    instructions = ai.SYSTEM_INSTRUCTIONS
    assert "currentDeadlineCommand is the authority" in instructions
    assert "evControlEvents are executor/realtime control outputs" in instructions
    assert "must never be relabelled as a user deadline command" in instructions
    assert "do not project currentDeadlineCommand backwards" in instructions

    print("PASS: AI current EV deadline command contract")


if __name__ == "__main__":
    main()

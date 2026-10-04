#!/usr/bin/env python3
import importlib.util
from datetime import date
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
    assert "Relevance is mandatory" in instructions
    assert "do not mention unrelated device-state observations" in instructions
    assert "whether the Tesla charged" in instructions
    assert "omit washer/dryer state" in instructions
    assert "Never equate an active device state with measured power attribution" in instructions
    assert "evidenceSelection.mode is EXPLICIT_TIME_WINDOW" in instructions

    day = date(2026, 10, 4)
    explicit = ai._explicit_question_anchors(
        "Waarom was het verbruik rond 05:20 zo hoog?",
        day,
    )
    assert len(explicit) == 1
    assert explicit[0].hour == 5
    assert explicit[0].minute == 20
    assert ai._explicit_question_anchors(
        "Hoe heeft het EMS het vandaag gedaan?",
        day,
    ) == []

    points = [
        {"atLocal": "2026-10-04T04:49:00+02:00", "id": "too-early"},
        {"atLocal": "2026-10-04T04:50:00+02:00", "id": "window-start"},
        {"atLocal": "2026-10-04T05:20:00+02:00", "id": "anchor"},
        {"atLocal": "2026-10-04T05:50:00+02:00", "id": "window-end"},
        {"atLocal": "2026-10-04T05:51:00+02:00", "id": "too-late"},
        {"atLocal": "2026-10-04T14:00:00+02:00", "id": "other-time"},
    ]
    selected = ai._select_points_near_anchors(points, explicit)
    assert [point["id"] for point in selected] == [
        "window-start",
        "anchor",
        "window-end",
    ]
    assert ai._select_points_near_anchors(points, []) == points

    two_anchors = ai._explicit_question_anchors(
        "Vergelijk 05:20 met 14:00.",
        day,
    )
    selected_two = ai._select_points_near_anchors(points, two_anchors)
    assert [point["id"] for point in selected_two] == [
        "window-start",
        "anchor",
        "window-end",
        "other-time",
    ]

    fallback = ai._question_anchors(
        "Hoe heeft het EMS het vandaag gedaan?",
        day,
        {
            "surplusWindowsForReplay": [
                {"start": "2026-10-04T10:00:00+02:00"}
            ]
        },
        [],
    )
    assert len(fallback) == 1
    assert fallback[0].hour == 10
    assert fallback[0].minute == 0

    maxed = {
        "id": "resp_test_max",
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 4096,
            "output_tokens_details": {"reasoning_tokens": 4096},
            "total_tokens": 5296,
        },
        "output": [{"type": "reasoning"}],
    }
    assert ai._model_failure_reason(maxed) == "MODEL_INCOMPLETE_MAX_OUTPUT_TOKENS"
    maxed_diag = ai._model_response_diagnostics(
        maxed, ai._model_failure_reason(maxed)
    )
    assert maxed_diag["responseId"] == "resp_test_max"
    assert maxed_diag["status"] == "incomplete"
    assert maxed_diag["incompleteReason"] == "max_output_tokens"
    assert maxed_diag["outputTokens"] == 4096
    assert maxed_diag["reasoningTokens"] == 4096
    assert set(maxed_diag) == {
        "event",
        "reason",
        "responseId",
        "status",
        "durationMs",
        "incompleteReason",
        "errorCode",
        "refusalPresent",
        "inputTokens",
        "outputTokens",
        "reasoningTokens",
        "totalTokens",
    }

    refused = {
        "id": "resp_test_refused",
        "status": "completed",
        "output": [{
            "type": "message",
            "content": [{"type": "refusal", "refusal": "not logged"}],
        }],
    }
    assert ai._model_failure_reason(refused) == "MODEL_REFUSED"
    assert ai._model_response_diagnostics(
        refused, ai._model_failure_reason(refused)
    )["refusalPresent"] is True

    completed_empty = {
        "id": "resp_test_empty",
        "status": "completed",
        "output": [{"type": "message", "content": []}],
    }
    assert ai._model_failure_reason(completed_empty) == "MODEL_EMPTY_RESPONSE_COMPLETED"

    normal = {
        "id": "resp_test_ok",
        "status": "completed",
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": "antwoord"}],
        }],
    }
    assert ai._extract_output_text(normal) == "antwoord"
    success_diag = ai._model_success_diagnostics(
        {
            **normal,
            "usage": {
                "input_tokens": 2000,
                "output_tokens": 300,
                "output_tokens_details": {"reasoning_tokens": 120},
                "total_tokens": 2300,
            },
        },
        1234,
    )
    assert success_diag == {
        "event": "EMS_AI_MODEL_RESPONSE_SUCCESS",
        "responseId": "resp_test_ok",
        "status": "completed",
        "durationMs": 1234,
        "inputTokens": 2000,
        "outputTokens": 300,
        "reasoningTokens": 120,
        "totalTokens": 2300,
    }

    print("PASS: AI evidence quality semantics contract")


if __name__ == "__main__":
    main()

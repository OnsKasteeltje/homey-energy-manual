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
    assert "Recent conversation context" in instructions
    assert "referential context only" in instructions
    assert "TOPIC_DAY_SCOPE" in instructions
    assert "omittedFields" in instructions
    assert "evidenceSelection.inputBudget.status" in instructions
    assert "budgetCompactedFields" in instructions

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

    context = ai._validate_conversation_context([
        {
            "role": "user",
            "content": "De EV deadline loopt tot 17:00.",
        },
        {
            "role": "assistant",
            "content": "Om 16:45 zat de planner in dat tijdslot.",
        },
    ])
    assert len(context) == 2
    context_anchor = ai._context_followup_anchors(
        "Waarom staat er in dit tijdslot geen waarde?",
        day,
        context,
    )
    assert len(context_anchor) == 1
    assert context_anchor[0].hour == 16
    assert context_anchor[0].minute == 45

    assert ai._question_topics(
        "is de deadline opdracht goed in de keten verwerkt?",
        [],
    ) == ["EV"]

    followup_topics = ai._question_topics(
        "waarom staat er op de PV&Flex pagina dan in dit tijdslot geen waarde?",
        context,
    )
    assert "PV_FLEX" in followup_topics
    assert "EV" in followup_topics

    try:
        ai._validate_conversation_context([
            {
                "role": "assistant",
                "content": "x" * (ai.MAX_CONTEXT_MESSAGE_CHARS + 1),
            }
        ])
        raise AssertionError("oversized context must fail")
    except ValueError as exc:
        assert str(exc) == "CONTEXT_INVALID"

    bounded_source = [
        {"id": index, "state": "A" if index < 50 else "B"}
        for index in range(100)
    ]
    bounded = ai._bounded_points(
        bounded_source,
        10,
        change_paths=(("state",),),
    )
    assert len(bounded) == 10
    assert bounded[0]["id"] == 0
    assert bounded[-1]["id"] == 99
    assert any(item["state"] == "A" for item in bounded)
    assert any(item["state"] == "B" for item in bounded)

    def points(count, prefix):
        return [
            {
                "atLocal": (
                    f"2026-10-04T{index // 60:02d}:{index % 60:02d}:00+02:00"
                ),
                "id": f"{prefix}-{index}",
            }
            for index in range(count)
        ]

    ai._load_performance = lambda _day: {
        "schema": "EMS_PI_DAY_PERFORMANCE_V0.1",
        "surplusWindowsForReplay": [],
    }
    ai._ev_control_events = lambda _day: points(100, "control")
    ai._ev_telemetry = lambda _day: points(100, "telemetry")
    ai._quooker_events = lambda _day: points(100, "quooker")
    ai._timeline = lambda _day: points(100, "timeline")
    ai._planner_decision_window = lambda _day, _anchors: []
    ai._flex_context_window = lambda _day, _anchors: [
        {"id": index} for index in range(5)
    ]
    ai._forecast_vs_actual_15m = lambda _day, _anchors: {
        "available": True,
        "summary": {},
        "slots": [],
    }
    ai._load_health = lambda: {
        "schema": "EMS_PI_HEALTH_V0.1",
        "status": "HEALTHY",
    }

    ev_evidence = ai.build_evidence(
        day,
        "is de deadline opdracht goed in de keten verwerkt?",
        [],
    )
    assert ev_evidence["evidenceSelection"]["mode"] == "TOPIC_DAY_SCOPE"
    assert ev_evidence["evidenceSelection"]["topics"] == ["EV"]
    assert len(ev_evidence["evControlEvents"]) <= ai.DAY_SCOPE_LIMITS["evControlEvents"]
    assert len(ev_evidence["evTelemetry5m"]) <= ai.DAY_SCOPE_LIMITS["evTelemetry5m"]
    assert ev_evidence["quookerEvents"] == []
    assert len(ev_evidence["flexContextWindow"]) <= ai.DAY_SCOPE_LIMITS["flexContextWindow"]

    pv_evidence = ai.build_evidence(
        day,
        "waarom staat er op de PV&Flex pagina geen waarde?",
        [],
    )
    assert pv_evidence["evidenceSelection"]["mode"] == "TOPIC_DAY_SCOPE"
    assert "PV_FLEX" in pv_evidence["evidenceSelection"]["topics"]
    assert pv_evidence["evControlEvents"] == []
    assert pv_evidence["evTelemetry5m"] == []
    assert pv_evidence["quookerEvents"] == []

    pv_context = [
        {
            "role": "user",
            "content": "Ik kijk naar het PV&Flex tijdslot rond 00:45.",
        },
        {
            "role": "assistant",
            "content": "Rond 00:45 is dit het relevante PV&Flex tijdslot.",
        },
    ]
    pv_context_evidence = ai.build_evidence(
        day,
        "waarom staat er op de PV&Flex pagina dan in dit tijdslot geen waarde?",
        pv_context,
    )
    assert pv_context_evidence["evidenceSelection"]["mode"] == "CONTEXT_TIME_WINDOW"
    assert pv_context_evidence["evidenceSelection"]["topics"] == ["PV_FLEX"]
    assert pv_context_evidence["evidenceSelection"]["contextTimeAnchorsLocal"] == [
        "2026-10-04T00:45:00+02:00"
    ]
    assert pv_context_evidence["evidenceSelection"]["originalCounts"]["evControlEvents"] == 100
    assert pv_context_evidence["evidenceSelection"]["selectedCounts"]["evControlEvents"] == 0
    assert pv_context_evidence["evidenceSelection"]["selectedCounts"]["evTelemetry5m"] == 0
    assert pv_context_evidence["evControlEvents"] == []
    assert pv_context_evidence["evTelemetry5m"] == []
    assert pv_context_evidence["quookerEvents"] == []
    assert "evControlEvents" in pv_context_evidence["evidenceSelection"]["omittedFields"]
    assert "evTelemetry5m" in pv_context_evidence["evidenceSelection"]["omittedFields"]

    pv_explicit_evidence = ai.build_evidence(
        day,
        "waarom ontbreekt PV&Flex om 00:45?",
        [],
    )
    assert pv_explicit_evidence["evidenceSelection"]["mode"] == "EXPLICIT_TIME_WINDOW"
    assert pv_explicit_evidence["evidenceSelection"]["topics"] == ["PV_FLEX"]
    assert pv_explicit_evidence["evControlEvents"] == []
    assert pv_explicit_evidence["evTelemetry5m"] == []
    assert pv_explicit_evidence["quookerEvents"] == []

    normal_budget = pv_explicit_evidence["evidenceSelection"]["inputBudget"]
    assert normal_budget["targetTokens"] == 80000
    assert normal_budget["hardLimitTokens"] == 100000
    assert normal_budget["exactTokenizer"] is False
    assert normal_budget["status"] in {
        "WITHIN_BUDGET",
        "COMPACTED_TO_BUDGET",
        "WITHIN_HARD_LIMIT",
    }
    assert normal_budget["estimatedTokens"] <= normal_budget["hardLimitTokens"]

    budget_evidence = {
        "evidenceSelection": {
            "compactedFields": [],
            "selectedCounts": {
                "timeline5m": 100,
                "evTelemetry5m": 0,
                "evControlEvents": 0,
                "quookerEvents": 0,
                "flexContextWindow": 0,
            },
        },
        "timeline5m": [
            {
                "atLocal": f"2026-10-04T00:{index % 60:02d}:00+02:00",
                "blob": "x" * 4000,
            }
            for index in range(100)
        ],
        "evTelemetry5m": [],
        "evControlEvents": [],
        "quookerEvents": [],
        "plannerDecisionWindow": [],
        "flexContextWindow": [],
        "forecastVsActual15m": {"available": True, "summary": {}, "slots": []},
    }
    budgeted = ai._apply_model_input_budget(
        budget_evidence,
        "analyseer vandaag",
        [],
    )
    compact_budget = budgeted["evidenceSelection"]["inputBudget"]
    assert compact_budget["status"] in {
        "COMPACTED_TO_BUDGET",
        "WITHIN_HARD_LIMIT",
    }
    assert compact_budget["compactionStepsApplied"] >= 1
    assert "timeline5m" in compact_budget["budgetCompactedFields"]
    assert len(budgeted["timeline5m"]) < 100
    assert compact_budget["estimatedTokens"] <= ai.MODEL_INPUT_HARD_LIMIT_TOKENS
    if compact_budget["status"] == "COMPACTED_TO_BUDGET":
        assert compact_budget["estimatedTokens"] <= ai.MODEL_INPUT_TARGET_TOKENS
    else:
        assert compact_budget["estimatedTokens"] > ai.MODEL_INPUT_TARGET_TOKENS
    assert budgeted["evidenceSelection"]["selectedCounts"]["timeline5m"] == len(
        budgeted["timeline5m"]
    )

    hard_evidence = {
        "evidenceSelection": {
            "compactedFields": [],
            "selectedCounts": {},
        },
        "timeline5m": [],
        "evTelemetry5m": [],
        "evControlEvents": [],
        "quookerEvents": [],
        "plannerDecisionWindow": [],
        "flexContextWindow": [],
        "forecastVsActual15m": {"available": True, "summary": {}, "slots": []},
        "nonCompactable": "x" * 400000,
    }
    try:
        ai._apply_model_input_budget(
            hard_evidence,
            "analyseer vandaag",
            [],
        )
        raise AssertionError("hard input budget must fail closed")
    except RuntimeError as exc:
        assert str(exc) == "MODEL_INPUT_BUDGET_EXCEEDED"
        assert (
            hard_evidence["evidenceSelection"]["inputBudget"]["status"]
            == "HARD_LIMIT_EXCEEDED"
        )

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

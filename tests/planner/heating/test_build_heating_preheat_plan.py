import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[3] / "services/pi/planner/heating/build_heating_preheat_plan.py"
spec = importlib.util.spec_from_file_location("build_heating_preheat_plan", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def room_model(direction="UP", target=19.0):
    return {
        "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": "2026-09-15T20:00:00Z",
        "timezone": "Europe/Amsterdam",
        "baselineAuthority": "HONEYWELL",
        "valid": True,
        "rooms": [{
            "key": "woonkamer",
            "displayName": "Woonkamer",
            "valid": True,
            "current": {
                "temperature_C": 18.0,
                "targetTemperature_C": 18.0,
                "setpointMode": "FOLLOW_SCHEDULE",
            },
            "baseline": {
                "currentTarget_C": 15.5,
                "currentSince": "2026-09-16T08:00:00+02:00",
                "nextChangeAt": "2026-09-16T17:30:00+02:00",
                "nextTarget_C": target,
                "direction": direction,
            },
        }],
    }


def build(model=None):
    return module.build_plan(
        model or room_model(),
        generated_at=datetime(2026, 9, 15, 21, 45, tzinfo=timezone.utc),
    )


def test_up_transition_is_eligible_but_has_no_start_time_yet():
    plan = build()
    room = plan["rooms"][0]
    assert plan["schema"] == "EMS_HEATING_PREHEAT_PLAN_V0.1"
    assert plan["mode"] == "READ_ONLY"
    assert plan["controlMode"] == "SHADOW"
    assert plan["timezone"] == "Europe/Amsterdam"
    assert room["baseline"] == {
        "changeAt": "2026-09-16T17:30:00+02:00",
        "targetTemperature_C": 19.0,
        "direction": "UP",
    }
    assert room["candidate"] == {
        "status": "ELIGIBLE_UP_TRANSITION",
        "startAt": None,
        "targetTemperature_C": 19.0,
        "reason": "AWAITING_OPPORTUNITY_EVALUATION",
    }


@pytest.mark.parametrize("direction", ["DOWN", "NONE"])
def test_non_up_transition_is_not_eligible(direction):
    room = build(room_model(direction=direction))["rooms"][0]
    assert room["candidate"]["status"] == "NOT_ELIGIBLE"
    assert room["candidate"]["startAt"] is None
    assert room["candidate"]["reason"] == f"BASELINE_{direction}"


def test_candidate_target_is_exactly_honeywell_baseline_target():
    room = build(room_model(target=20.5))["rooms"][0]
    assert room["candidate"]["targetTemperature_C"] == 20.5
    assert room["candidate"]["targetTemperature_C"] == room["baseline"]["targetTemperature_C"]


def test_invalid_source_fails_closed():
    model = room_model()
    model["valid"] = False
    with pytest.raises(module.PlanError, match="room model is not valid"):
        build(model)


def test_wrong_timezone_fails_closed():
    model = room_model()
    model["timezone"] = "UTC"
    with pytest.raises(module.PlanError, match="unexpected room model timezone"):
        build(model)


def test_naive_baseline_timestamp_is_rejected():
    model = room_model()
    model["rooms"][0]["baseline"]["nextChangeAt"] = "2026-09-16T17:30:00"
    with pytest.raises(module.PlanError, match="offset-aware"):
        build(model)


def test_invalid_direction_is_rejected():
    model = room_model(direction="EARLY")
    with pytest.raises(module.PlanError, match="invalid baseline direction"):
        build(model)

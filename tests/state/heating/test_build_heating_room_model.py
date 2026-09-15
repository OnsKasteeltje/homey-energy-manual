import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[3] / "services/pi/state/heating/build_heating_room_model.py"
spec = importlib.util.spec_from_file_location("build_heating_room_model", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def schedule(next_target=15.5, status="OK"):
    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "generatedAt": "2026-09-15T19:49:03.104492Z",
        "zones": [{
            "key": "woonkamer",
            "displayName": "Woonkamer",
            "scheduleStatus": status,
            "currentSwitchpoint": {"time": "2026-09-15T19:30:00+02:00", "targetTemperature_C": 19.0},
            "nextSwitchpoint": {"time": "2026-09-15T22:00:00+02:00", "targetTemperature_C": next_target},
            "weeklySchedule": [],
        }],
    }


def state(actual_target=20.0):
    return {
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "generatedAt": "2026-09-15T19:48:00Z",
        "zones": [{
            "key": "woonkamer",
            "displayName": "Woonkamer",
            "roomTemperature_C": 18.4,
            "targetTemperature_C": actual_target,
            "setpointMode": "TEMPORARY_OVERRIDE",
        }],
    }


def build(s=None, st=None):
    return module.build_model(
        s or schedule(),
        st or state(),
        generated_at=datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc),
    )


def test_validated_woonkamer_transition_is_down_and_local_time_is_preserved():
    model = build()
    room = model["rooms"][0]
    assert model["schema"] == "EMS_HEATING_ROOM_MODEL_V0.1"
    assert model["timezone"] == "Europe/Amsterdam"
    assert room["baseline"] == {
        "currentTarget_C": 19.0,
        "currentSince": "2026-09-15T19:30:00+02:00",
        "nextChangeAt": "2026-09-15T22:00:00+02:00",
        "nextTarget_C": 15.5,
        "direction": "DOWN",
    }


def test_actual_override_does_not_rewrite_baseline_transition():
    room = build(st=state(actual_target=21.0))["rooms"][0]
    assert room["current"]["targetTemperature_C"] == 21.0
    assert room["baseline"]["currentTarget_C"] == 19.0
    assert room["baseline"]["direction"] == "DOWN"


def test_up_and_none_are_classified_from_schedule_only():
    assert build(s=schedule(next_target=20.0))["rooms"][0]["baseline"]["direction"] == "UP"
    assert build(s=schedule(next_target=19.0))["rooms"][0]["baseline"]["direction"] == "NONE"


def test_non_ok_schedule_fails_closed():
    with pytest.raises(module.ModelError, match="schedule not OK"):
        build(s=schedule(status="INVALID_OR_UNAVAILABLE"))


def test_room_key_mismatch_fails_closed():
    st = state()
    st["zones"][0]["key"] = "keuken"
    with pytest.raises(module.ModelError, match="room key mismatch"):
        build(st=st)


def test_naive_switchpoint_timestamp_is_rejected():
    s = schedule()
    s["zones"][0]["nextSwitchpoint"]["time"] = "2026-09-15T22:00:00"
    with pytest.raises(module.ModelError, match="offset-aware"):
        build(s=s)

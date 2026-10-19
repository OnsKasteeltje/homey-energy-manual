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
            "weeklySchedule": [{
                "day_of_week": "tuesday",
                "switchpoints": [
                    {"time_of_day": "06:00:00", "heat_setpoint": 16.0},
                    {"time_of_day": "19:30:00", "heat_setpoint": 19.0},
                    {"time_of_day": "22:00:00", "heat_setpoint": next_target},
                ],
            }],
        }],
    }


def state(
    actual_target=19.0,
    mode="follow_schedule",
    override_until=None,
    system_mode="auto",
):
    return {
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "generatedAt": "2026-09-15T19:48:00Z",
        "location": {"systemMode": system_mode},
        "zones": [{
            "key": "woonkamer",
            "displayName": "Woonkamer",
            "roomTemperature_C": 18.4,
            "targetTemperature_C": actual_target,
            "setpointMode": mode,
            "overrideUntil": override_until,
        }],
    }


def build(s=None, st=None):
    return module.build_model(
        s or schedule(),
        st or state(),
        generated_at=datetime(2026, 9, 15, 19, 0, tzinfo=timezone.utc),  # 21:00 Europe/Amsterdam
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


def test_temporary_override_becomes_effective_target_without_rewriting_schedule():
    room = build(st=state(
        actual_target=21.0,
        mode="temporary_override",
        override_until="2026-09-15T22:30:00+02:00",
    ))["rooms"][0]
    assert room["current"]["targetTemperature_C"] == 21.0
    assert room["current"]["setpointMode"] == "temporary_override"
    assert room["effective"] == {
        "currentTarget_C": 21.0,
        "source": "TEMPORARY_OVERRIDE",
        "systemMode": "auto",
        "setpointMode": "temporary_override",
        "overrideUntil": "2026-09-15T22:30:00+02:00",
        "scheduleAligned": False,
        "preheatAdvanceAllowed": False,
        "reason": "HONEYWELL_TEMPORARY_OVERRIDE_ACTIVE",
    }
    assert room["baseline"]["currentTarget_C"] == 19.0
    assert room["baseline"]["direction"] == "DOWN"


def test_permanent_override_blocks_schedule_preheat_semantics():
    room = build(st=state(actual_target=16.0, mode="permanent_override"))["rooms"][0]
    assert room["effective"]["currentTarget_C"] == 16.0
    assert room["effective"]["source"] == "PERMANENT_OVERRIDE"
    assert room["effective"]["overrideUntil"] is None
    assert room["effective"]["preheatAdvanceAllowed"] is False
    assert room["effective"]["reason"] == "HONEYWELL_PERMANENT_OVERRIDE_ACTIVE"


def test_follow_schedule_aligned_target_allows_schedule_preheat_semantics():
    room = build(st=state(actual_target=19.0, mode="follow_schedule"))["rooms"][0]
    assert room["effective"]["source"] == "SCHEDULE"
    assert room["effective"]["scheduleAligned"] is True
    assert room["effective"]["preheatAdvanceAllowed"] is True
    assert room["effective"]["reason"] == "FOLLOW_SCHEDULE"


def test_follow_schedule_target_mismatch_fails_closed_for_preheat():
    room = build(st=state(actual_target=18.5, mode="follow_schedule"))["rooms"][0]
    assert room["effective"]["source"] == "SCHEDULE"
    assert room["effective"]["scheduleAligned"] is False
    assert room["effective"]["preheatAdvanceAllowed"] is False
    assert room["effective"]["reason"] == "FOLLOW_SCHEDULE_TARGET_MISMATCH"


def test_non_auto_system_mode_fails_closed_for_preheat():
    room = build(st=state(actual_target=16.0, mode="follow_schedule", system_mode="away"))["rooms"][0]
    assert room["effective"]["source"] == "SYSTEM_MODE"
    assert room["effective"]["systemMode"] == "away"
    assert room["effective"]["preheatAdvanceAllowed"] is False
    assert room["effective"]["reason"] == "HONEYWELL_SYSTEM_MODE_ACTIVE"


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


def test_naive_schedule_generated_at_is_rejected():
    s = schedule()
    s["generatedAt"] = "2026-09-15T19:49:03"
    with pytest.raises(module.ModelError, match="offset-aware"):
        build(s=s)


def test_naive_temporary_override_until_is_rejected():
    with pytest.raises(module.ModelError, match="offset-aware"):
        build(st=state(
            actual_target=20.0,
            mode="temporary_override",
            override_until="2026-09-15T22:30:00",
        ))


def test_three_hour_lookahead_includes_all_upcoming_honeywell_changes():
    weekly = schedule()
    weekly["zones"][0]["weeklySchedule"][0]["switchpoints"] = [
        {"time_of_day": "06:00:00", "heat_setpoint": 15.5},
        {"time_of_day": "17:30:00", "heat_setpoint": 18.0},
        {"time_of_day": "18:30:00", "heat_setpoint": 18.5},
        {"time_of_day": "19:30:00", "heat_setpoint": 19.0},
        {"time_of_day": "22:00:00", "heat_setpoint": 15.5},
    ]
    model = module.build_model(
        weekly, state(actual_target=15.5),
        generated_at=datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc),
    )
    room = model["rooms"][0]
    assert room["baseline"]["nextTarget_C"] == 18.0
    points = room["lookahead"]["switchpoints"]
    assert [p["targetTemperature_C"] for p in points] == [18.0, 18.5, 19.0]
    assert all(p["direction"] == "UP" for p in points)
    assert points[-1]["time"] == "2026-09-15T19:30:00+02:00"

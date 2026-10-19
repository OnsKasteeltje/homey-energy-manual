import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[3] / "services/pi/planner/heating/build_heating_preheat_plan.py"
spec = importlib.util.spec_from_file_location("build_heating_preheat_plan", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def room(
    key="woonkamer",
    direction="UP",
    current_temp=17.2,
    current_target=15.5,
    target=19.0,
    change_at="2026-09-16T17:30:00+02:00",
    effective_target=None,
    preheat_allowed=True,
    effective_reason="FOLLOW_SCHEDULE",
    effective_source="SCHEDULE",
    setpoint_mode="follow_schedule",
    override_until=None,
):
    effective_target = current_target if effective_target is None else effective_target
    return {
        "key": key,
        "displayName": key.title(),
        "valid": True,
        "current": {
            "temperature_C": current_temp,
            "targetTemperature_C": effective_target,
            "setpointMode": setpoint_mode,
            "overrideUntil": override_until,
        },
        "effective": {
            "currentTarget_C": effective_target,
            "source": effective_source,
            "systemMode": "auto",
            "setpointMode": setpoint_mode,
            "overrideUntil": override_until,
            "scheduleAligned": abs(effective_target - current_target) <= 1e-9,
            "preheatAdvanceAllowed": preheat_allowed,
            "reason": effective_reason,
        },
        "baseline": {
            "currentTarget_C": current_target,
            "currentSince": "2026-09-16T08:00:00+02:00",
            "nextChangeAt": change_at,
            "nextTarget_C": target,
            "direction": direction,
        },
    }


def room_model(rooms=None):
    return {
        "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": "2026-09-16T12:00:00Z",
        "timezone": "Europe/Amsterdam",
        "baselineAuthority": "HONEYWELL",
        "valid": True,
        "rooms": rooms or [room()],
    }


def build(model=None, now=None):
    return module.build_plan(
        model or room_model(),
        generated_at=now or datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc),  # 15:00 local
    )


def test_v02_eligible_up_inside_three_hour_window_with_heat_demand():
    plan = build()
    r = plan["rooms"][0]
    assert plan["schema"] == "EMS_HEATING_PREHEAT_PLAN_V0.2"
    assert plan["policy"]["maxAdvanceMinutes"] == 180
    assert r["candidate"]["status"] == "ELIGIBLE_UP_TRANSITION"
    assert r["candidate"]["earliestStartAt"] == "2026-09-16T14:30:00+02:00"
    assert r["candidate"]["startAt"] is None
    assert r["candidate"]["reason"] == "AWAITING_PV_OPPORTUNITY_EVALUATION"
    assert r["effective"]["preheatAdvanceAllowed"] is True


@pytest.mark.parametrize(
    ("mode", "source", "reason"),
    [
        ("temporary_override", "TEMPORARY_OVERRIDE", "HONEYWELL_TEMPORARY_OVERRIDE_ACTIVE"),
        ("permanent_override", "PERMANENT_OVERRIDE", "HONEYWELL_PERMANENT_OVERRIDE_ACTIVE"),
    ],
)
def test_active_honeywell_override_blocks_preheat(mode, source, reason):
    r = build(room_model([room(
        direction="UP",
        effective_target=18.0,
        preheat_allowed=False,
        effective_reason=reason,
        effective_source=source,
        setpoint_mode=mode,
        override_until="2026-09-16T18:00:00+02:00" if mode == "temporary_override" else None,
    )]))["rooms"][0]
    assert r["candidate"]["status"] == "NOT_ELIGIBLE"
    assert r["candidate"]["reason"] == reason
    assert r["candidate"]["steps_C"] == []
    assert r["baseline"]["currentTargetTemperature_C"] == 18.0
    assert r["baseline"]["scheduledCurrentTargetTemperature_C"] == 15.5


def test_follow_schedule_target_mismatch_blocks_preheat():
    r = build(room_model([room(
        effective_target=16.0,
        preheat_allowed=False,
        effective_reason="FOLLOW_SCHEDULE_TARGET_MISMATCH",
    )]))["rooms"][0]
    assert r["candidate"]["status"] == "NOT_ELIGIBLE"
    assert r["candidate"]["reason"] == "FOLLOW_SCHEDULE_TARGET_MISMATCH"
    assert r["candidate"]["steps_C"] == []


def test_actual_temperature_at_or_above_future_target_blocks_preheat():
    r = build(room_model([room(current_temp=20.0)]))["rooms"][0]
    assert r["candidate"]["status"] == "NOT_ELIGIBLE"
    assert r["candidate"]["reason"] == "NO_HEAT_DEMAND_AT_CURRENT_TEMPERATURE"
    assert r["candidate"]["steps_C"] == []


def test_large_baseline_rise_is_split_into_half_degree_steps_and_satisfied_steps_are_skipped():
    r = build(room_model([room(current_temp=17.2, current_target=15.5, target=19.0)]))["rooms"][0]
    assert r["candidate"]["steps_C"] == [17.5, 18.0, 18.5, 19.0]
    assert all(b - a <= 0.5 + 1e-9 for a, b in zip([17.0] + r["candidate"]["steps_C"][:-1], r["candidate"]["steps_C"]))


def test_more_than_three_hours_early_is_not_eligible():
    now = datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc)  # 13:00 local, 4.5h early
    r = build(now=now)["rooms"][0]
    assert r["candidate"]["reason"] == "OUTSIDE_MAX_ADVANCE_WINDOW"


def test_past_transition_is_not_eligible():
    now = datetime(2026, 9, 16, 16, 0, tzinfo=timezone.utc)  # 18:00 local
    r = build(now=now)["rooms"][0]
    assert r["candidate"]["reason"] == "OUTSIDE_MAX_ADVANCE_WINDOW"


@pytest.mark.parametrize("key", ["woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe"])
def test_six_selected_rooms_are_in_scope(key):
    r = build(room_model([room(key=key)]))["rooms"][0]
    assert r["preheatScope"] is True


@pytest.mark.parametrize("key", ["master_bedroom", "krijn_slaapkamer"])
def test_other_rooms_are_explicitly_out_of_preheat_scope(key):
    r = build(room_model([room(key=key)]))["rooms"][0]
    assert r["preheatScope"] is False
    assert r["candidate"]["reason"] == "ROOM_OUT_OF_PREHEAT_SCOPE"


@pytest.mark.parametrize("key", ["douwe_slaapkamer", "erker_douwe"])
def test_douwe_rooms_remain_independent(key):
    r = build(room_model([room(key=key)]))["rooms"][0]
    assert r["group"] is None
    assert r["candidate"]["status"] == "ELIGIBLE_UP_TRANSITION"


def test_woonkamer_and_eetkamer_share_living_area_group():
    plan = build(room_model([room(key="woonkamer"), room(key="eetkamer")]))
    assert {r["group"] for r in plan["rooms"]} == {"living_area"}


@pytest.mark.parametrize("direction", ["DOWN", "NONE"])
def test_non_up_transition_is_not_eligible(direction):
    r = build(room_model([room(direction=direction)]))["rooms"][0]
    assert r["candidate"]["reason"] == f"BASELINE_{direction}"


def test_candidate_target_never_exceeds_honeywell_target():
    r = build(room_model([room(target=20.5)]))["rooms"][0]
    assert r["candidate"]["targetTemperature_C"] == 20.5
    assert max(r["candidate"]["steps_C"]) == 20.5


def test_invalid_source_fails_closed():
    model = room_model()
    model["valid"] = False
    with pytest.raises(module.PlanError, match="room model is not valid"):
        build(model)


def test_naive_baseline_timestamp_is_rejected():
    model = room_model([room(change_at="2026-09-16T17:30:00")])
    with pytest.raises(module.PlanError, match="offset-aware"):
        build(model)


def test_three_hour_lookahead_selects_later_rise_and_uses_half_degree_steps():
    model = room_model([room(
        current_temp=18.0, current_target=15.5, target=18.0,
        change_at="2026-09-16T17:30:00+02:00",
    )])
    model["rooms"][0]["lookahead"] = {
        "windowMinutes": 180,
        "switchpoints": [
            {"time": "2026-09-16T17:30:00+02:00", "targetTemperature_C": 18.0},
            {"time": "2026-09-16T18:30:00+02:00", "targetTemperature_C": 18.5},
            {"time": "2026-09-16T19:30:00+02:00", "targetTemperature_C": 19.0},
        ],
    }
    r = build(model, now=datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc))["rooms"][0]
    assert r["baseline"]["targetTemperature_C"] == 19.0
    assert r["candidate"]["targetChangeAt"] == "2026-09-16T19:30:00+02:00"
    assert r["candidate"]["steps_C"] == [18.5, 19.0]
    assert r["candidate"]["lookaheadSelected"] is True


def test_lookahead_does_not_jump_over_a_setback():
    model = room_model([room(
        current_temp=17.5, current_target=15.5, target=18.0,
        change_at="2026-09-16T17:30:00+02:00",
    )])
    model["rooms"][0]["lookahead"] = {
        "windowMinutes": 180,
        "switchpoints": [
            {"time": "2026-09-16T17:30:00+02:00", "targetTemperature_C": 18.0},
            {"time": "2026-09-16T18:30:00+02:00", "targetTemperature_C": 16.0},
            {"time": "2026-09-16T19:30:00+02:00", "targetTemperature_C": 19.0},
        ],
    }
    r = build(model, now=datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc))["rooms"][0]
    assert r["candidate"]["targetTemperature_C"] == 18.0
    assert r["candidate"]["targetChangeAt"] == "2026-09-16T17:30:00+02:00"

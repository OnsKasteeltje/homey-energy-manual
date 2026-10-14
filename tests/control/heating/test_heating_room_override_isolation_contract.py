"""Cross-layer proof: Honeywell room overrides never block or reset other rooms.

All scenarios are offline, shadow-only; no Homey/Easee/Honeywell API access.
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
ROOMS = (
    "woonkamer", "eetkamer", "keuken", "serre",
    "douwe_slaapkamer", "erker_douwe",
)
T0 = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


def load(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model_mod = load("override_room_model", "services/pi/state/heating/build_heating_room_model.py")
plan_mod = load("override_candidate", "services/pi/planner/heating/build_heating_preheat_plan.py")
shadow_mod = load("override_v03", "services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py")
progress_mod = load("override_v04", "services/pi/planner/heating/build_heating_preheat_progression_shadow_v0_4.py")
gate_mod = load("override_v05", "services/pi/control/heating/build_heating_control_gate_shadow_v0_5.py")


def stamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def inputs(now, overridden=None, mode="temporary_override", system_mode="auto"):
    weekly = [
        {
            "day_of_week": day,
            "switchpoints": [
                {"time_of_day": "06:00:00", "heat_setpoint": 16.0},
                {"time_of_day": "13:00:00", "heat_setpoint": 19.0},
                {"time_of_day": "23:00:00", "heat_setpoint": 16.0},
            ],
        }
        for day in ("monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday")
    ]
    schedule = {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "generatedAt": stamp(now - timedelta(minutes=20)),
        "zones": [
            {
                "key": key, "displayName": key,
                "scheduleStatus": "OK",
                "weeklySchedule": weekly,
            }
            for key in ROOMS
        ],
    }
    state = {
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "generatedAt": stamp(now),
        "location": {"systemMode": system_mode},
        "zones": [
            {
                "key": key, "displayName": key,
                "roomTemperature_C": 17.0,
                # Override demand is deliberately real (target 20 > 17):
                # it must not contaminate every other room's preheat grant.
                "targetTemperature_C": 20.0 if key == overridden else 16.0,
                "setpointMode": mode if key == overridden else "follow_schedule",
                "overrideUntil": (
                    stamp(now + timedelta(hours=1))
                    if key == overridden and mode == "temporary_override"
                    else None
                ),
            }
            for key in ROOMS
        ],
    }
    return schedule, state


def quatt(now):
    return {
        "schema": "EMS_QUATT_CURRENT_STATE_V0.1",
        "generatedAt": stamp(now),
        "mode": "READ_ONLY",
        "observerOnly": {
            "cvActive": {
                "value": False,
                "observedAt": stamp(now),
                "sourceLastUpdated": stamp(now),
            }
        },
    }


def grant(now, ready):
    return {
        "schema": "EMS_PI_DYNAMIC_HEATING_GRANT_V0.1",
        "mode": "PRODUCTION_PLANNER_GRANT",
        "generatedAt": stamp(now + timedelta(seconds=10)),
        "validUntil": stamp(now + timedelta(minutes=4)),
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "allocationAuthority": "DYNAMIC_PI_PLANNER",
        "baselineAuthority": "HONEYWELL",
        "heating": {
            "readyRooms": list(ready),
            "grant": "PRODUCTION_GRANT",
            "reason": "TEST_ROOM_ISOLATED_GRANT",
            "priorityReason": "TEST_ROOM_ISOLATED_GRANT",
            "priorityOwner": "HEATING",
        },
    }


def per_room(payload):
    return {room["key"]: room for room in payload["rooms"]}


def cycle(*, now=T0, override=None, mode="temporary_override",
          system_mode="auto", previous_v04=None, previous_v05=None):
    schedule, state = inputs(now, override, mode, system_mode)
    model = model_mod.build_model(schedule, state, generated_at=now)
    candidate = plan_mod.build_plan(model, generated_at=now)
    heating = shadow_mod.build_shadow(model, candidate, quatt(now), generated_at=now)
    ready = [
        key for key, room in per_room(heating).items()
        if room["shadow"]["state"] == "PREHEAT_READY_FOR_GRANT"
    ]
    progression = progress_mod.build_progression(
        heating, grant(now, ready), previous_v04,
        generated_at=now + timedelta(seconds=20),
    )
    gate = gate_mod.build_gate(
        heating, progression, previous_v05,
        generated_at=now + timedelta(seconds=30),
    )
    for artifact in (heating, progression, gate):
        assert artifact["controlWrites"] is False
    for artifact in (progression, gate):
        assert artifact["physicalWriteAllowed"] is False
    assert all(
        r["command"]["physicalWrite"] is False for r in gate["rooms"]
    )
    return model, candidate, heating, progression, gate


@pytest.mark.parametrize("room_key", ROOMS)
@pytest.mark.parametrize("mode", ("temporary_override", "permanent_override"))
def test_override_is_strictly_room_specific_even_when_override_requests_heating(room_key, mode):
    model, candidate, heating, progression, gate = cycle(override=room_key, mode=mode)
    models, candidates = per_room(model), per_room(candidate)
    shadow, progress, commands = map(per_room, (heating, progression, gate))

    assert heating["house"]["baselineHeatingDemandPresent"] is True
    assert heating["house"]["baselineDemandRooms"] == [room_key]
    assert heating["house"]["preheatBlockingBaselineDemandPresent"] is False
    assert heating["house"]["preheatBlockingBaselineDemandRooms"] == []

    expected_source = "TEMPORARY_OVERRIDE" if mode == "temporary_override" else "PERMANENT_OVERRIDE"
    for key in ROOMS:
        if key == room_key:
            assert models[key]["effective"]["source"] == expected_source
            assert models[key]["effective"]["preheatAdvanceAllowed"] is False
            assert candidates[key]["candidate"]["status"] == "NOT_ELIGIBLE"
            assert shadow[key]["shadow"]["state"] == "NOT_ELIGIBLE"
            assert progress[key]["progression"]["state"] == "INACTIVE"
            assert commands[key]["command"]["action"] == "HOLD"
            assert commands[key]["shadowOwnership"]["wouldOwnOverride"] is False
        else:
            assert models[key]["effective"]["source"] == "SCHEDULE"
            assert models[key]["effective"]["preheatAdvanceAllowed"] is True
            assert candidates[key]["candidate"]["status"] == "ELIGIBLE_UP_TRANSITION"
            assert shadow[key]["shadow"]["state"] == "PREHEAT_READY_FOR_GRANT"
            assert progress[key]["progression"]["state"] == "STEP_WAIT"
            assert commands[key]["command"]["action"] == "WOULD_SET_TEMP"
            assert commands[key]["shadowOwnership"]["wouldOwnOverride"] is True


@pytest.mark.parametrize("room_key", ROOMS)
def test_override_during_shadow_step_relinquishes_only_own_room_without_reset(room_key):
    _, _, _, old_progression, old_gate = cycle()
    assert all(
        r["command"]["action"] == "WOULD_SET_TEMP" for r in old_gate["rooms"]
    )

    _, _, _, progression, gate = cycle(
        now=T0 + timedelta(minutes=1),
        override=room_key,
        previous_v04=old_progression,
        previous_v05=old_gate,
    )
    commands = per_room(gate)
    for key in ROOMS:
        action = commands[key]["command"]["action"]
        ownership = commands[key]["shadowOwnership"]
        if key == room_key:
            assert action == "HOLD"
            assert commands[key]["command"]["reason"] == "HONEYWELL_TEMPORARY_OVERRIDE_ACTIVE"
            assert ownership["previouslyOwned"] is True
            assert ownership["wouldOwnOverride"] is False
            assert ownership["simulatedRollback"] is False
            assert ownership["physicalOwnershipProven"] is False
        else:
            assert action == "WOULD_KEEP_TEMP"
            assert ownership["wouldOwnOverride"] is True

    # Once Honeywell resumes its programme, only that room may re-enter
    # preheat after a fresh, valid grant. No reset or manual write is needed.
    _, _, _, resumed_progression, resumed_gate = cycle(
        now=T0 + timedelta(minutes=2),
        previous_v04=progression,
        previous_v05=gate,
    )
    resumed_commands = per_room(resumed_gate)
    assert resumed_commands[room_key]["command"]["action"] == "WOULD_SET_TEMP"
    assert all(
        resumed_commands[key]["command"]["action"] in ("WOULD_SET_TEMP", "WOULD_KEEP_TEMP")
        for key in ROOMS if key != room_key
    )
    assert resumed_progression["physicalWriteAllowed"] is False


def test_honeywell_system_mode_is_a_distinct_global_safety_guard():
    model, _, heating, _, gate = cycle(system_mode="away")
    assert model["systemMode"] == "away"
    for key in ROOMS:
        assert per_room(model)[key]["effective"]["source"] == "SYSTEM_MODE"
        assert per_room(heating)[key]["shadow"]["state"] != "PREHEAT_READY_FOR_GRANT"
        assert per_room(gate)[key]["command"]["action"] == "HOLD"

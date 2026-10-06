#!/usr/bin/env python3
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROOM_MODEL = ROOT / "services/pi/state/heating/build_heating_room_model.py"
V03 = ROOT / "services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py"
V03_RUNNER = ROOT / "services/pi/planner/heating/run_heating_preheat_shadow_v0_3.py"
FLEX = ROOT / "services/pi/planner/joint/build_flex_priority_shadow_v0_1.py"
V04 = ROOT / "services/pi/planner/heating/build_heating_preheat_progression_shadow_v0_4.py"

NOW = datetime(2026, 10, 6, 14, 14, 0, tzinfo=timezone.utc)
REASON = "HONEYWELL_SOURCE_OR_CONTRACT_ERROR_ModelError"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def invalid_schedule():
    weekly = []
    for name in (
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ):
        weekly.append({
            "day_of_week": name,
            "switchpoints": [
                {"time_of_day": "06:00:00", "heat_setpoint": 16.0},
                {"time_of_day": "17:00:00", "heat_setpoint": 19.0},
                {"time_of_day": "22:00:00", "heat_setpoint": 16.0},
            ],
        })
    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "generatedAt": "2026-10-06T04:00:00Z",
        "zones": [{
            "key": "erker_douwe",
            "displayName": "Erker Douwe",
            "scheduleStatus": "OK",
            "weeklySchedule": weekly,
        }],
    }


def invalid_state():
    return {
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "generatedAt": "2026-10-06T14:10:00Z",
        "zones": [{
            "key": "erker_douwe",
            "displayName": "Erker Douwe",
            "roomTemperature_C": None,
            "targetTemperature_C": 16.0,
            "setpointMode": "FOLLOW_SCHEDULE",
        }],
    }


def ev():
    return {
        "schema": "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2",
        "readOnly": True,
        "controlWrites": False,
        "active": False,
        "remainingKWh": 0.0,
        "status": "INACTIVE",
        "latestStartAt": None,
        "deadlineAt": None,
    }


def previous_v04():
    return {
        "schema": "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "rooms": [{
            "key": "woonkamer",
            "displayName": "Woonkamer",
            "preheatScope": True,
            "group": "living_area",
            "opportunityId": "woonkamer|2026-10-06T15:00:00Z|19.000",
            "opportunityHistory": [],
            "stepHistory": [],
            "progression": {
                "state": "STEP_WAIT",
                "reason": "WAITING_FOR_MEASURED_TEMPERATURE",
                "activeStepTarget_C": 17.5,
                "activeStepReached": False,
                "activeStepStartedAt": "2026-10-06T14:00:00Z",
                "nextStepTarget_C": 18.0,
                "completedSteps_C": [],
                "lastTransition": "STARTED_STEP",
                "lastTransitionAt": "2026-10-06T14:00:00Z",
                "physicalWritePerformed": False,
            },
        }],
    }


def main():
    room = load("room_model_invalid_honeywell", ROOM_MODEL)
    v03 = load("v03_invalid_honeywell", V03)
    flex = load("flex_invalid_honeywell", FLEX)
    v04 = load("v04_invalid_honeywell", V04)

    try:
        room.build_model(invalid_schedule(), invalid_state(), generated_at=NOW)
        raise AssertionError("null Honeywell room temperature must remain invalid")
    except room.ModelError as exc:
        assert "erker_douwe.roomTemperature_C must be numeric" in str(exc)
        detail = str(exc)

    shadow = v03.build_source_fail_closed(
        reason=REASON,
        detail=detail,
        generated_at=NOW,
    )
    assert shadow["schema"] == "EMS_HEATING_PREHEAT_SHADOW_V0.3"
    assert shadow["controlWrites"] is False
    assert shadow["generatedAt"] == "2026-10-06T14:14:00Z"
    assert shadow["sourceStatus"]["status"] == "INVALID"
    assert shadow["sourceStatus"]["reason"] == REASON
    assert shadow["sourceStatus"]["reusedPreviousRoomData"] is False
    assert shadow["rooms"] == []
    assert shadow["house"]["baselineHeatingDemandPresent"] is None

    priority = flex.build_priority(
        shadow,
        ev(),
        generated_at=NOW,
    )
    assert priority["decision"]["priorityOwner"] == "HOLD_UNKNOWN"
    assert priority["decision"]["heatingShadowGrant"] == "HOLD"
    assert priority["decision"]["physicalWriteAllowed"] is False
    assert priority["decision"]["reason"] == REASON
    assert priority["heating"]["readyRooms"] == []
    assert priority["sourceFreshness"]["heatingSourceStatus"]["status"] == "INVALID"

    progression = v04.build_progression(
        shadow,
        priority,
        previous_v04(),
        generated_at=NOW,
    )
    assert progression["controlWrites"] is False
    assert progression["physicalWriteAllowed"] is False
    assert progression["sourceFreshness"]["heating"]["status"] == "INVALID"
    assert len(progression["rooms"]) == 1
    p = progression["rooms"][0]["progression"]
    assert p["state"] == "BLOCKED_SOURCE_INVALID"
    assert p["activeStepTarget_C"] is None
    assert p["nextStepTarget_C"] is None
    assert p["physicalWritePerformed"] is False
    assert progression["rooms"][0]["currentTemperature_C"] is None
    assert progression["rooms"][0]["stepHistory"][-1]["outcome"] == "SOURCE_INVALID"

    runner_source = V03_RUNNER.read_text(encoding="utf-8")
    assert "room_mod.ModelError" in runner_source
    assert "build_source_fail_closed" in runner_source
    assert "PASS_FAIL_CLOSED" in runner_source

    print("PASS: Heating V0.3 invalid Honeywell input publishes fresh fail-closed chain")


if __name__ == "__main__":
    main()

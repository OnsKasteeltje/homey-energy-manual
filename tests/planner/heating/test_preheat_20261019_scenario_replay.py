"""Deterministic schedule-scenario replay; NOT historical measured Pi telemetry.

Reproduces the 19 Oct 2026 user-discussed Honeywell switchpoints at two
snapshots. Checks the canonical room-model -> candidate -> V0.3 safety chain.
No actual actuator commands, PV consumption, thermal savings or gas are inferred.
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load(tag, relative_path):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(tag, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOM_MODEL = load("replay_room_model", "services/pi/state/heating/build_heating_room_model.py")
PLAN = load("replay_preheat_plan", "services/pi/planner/heating/build_heating_preheat_plan.py")
SHADOW = load("replay_preheat_v03", "services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py")


def _schedule():
    def zone(key, points):
        return {
            "key": key,
            "displayName": key,
            "scheduleStatus": "OK",
            "weeklySchedule": [{
                "day_of_week": "monday",
                "switchpoints": [
                    {"time_of_day": time, "heat_setpoint": temp}
                    for time, temp in points
                ],
            }],
        }

    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "generatedAt": "2026-10-19T13:00:00Z",
        "zones": [
            zone("woonkamer", [
                ("06:00:00", 15.5),
                ("17:30:00", 18.0),
                ("18:30:00", 18.5),
                ("19:30:00", 19.0),
                ("22:00:00", 15.5),
            ]),
            zone("eetkamer", [
                ("06:00:00", 17.5),
                ("19:00:00", 18.0),
                ("22:00:00", 15.5),
            ]),
        ],
    }


def _snapshot(hour, minute, *, woonkamer_temp, woonkamer_setpoint,
              eetkamer_temp=17.5, eetkamer_setpoint=17.5, cv_active=False):
    now = datetime(2026, 10, 19, hour - 2, minute, tzinfo=timezone.utc)
    iso = now.isoformat().replace("+00:00", "Z")
    observed = {
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "generatedAt": iso,
        "location": {"systemMode": "auto"},
        "zones": [
            {
                "key": key,
                "displayName": key,
                "roomTemperature_C": temp,
                "targetTemperature_C": target,
                "setpointMode": "follow_schedule",
                "overrideUntil": None,
            }
            for key, temp, target in (
                ("woonkamer", woonkamer_temp, woonkamer_setpoint),
                ("eetkamer", eetkamer_temp, eetkamer_setpoint),
            )
        ],
    }
    quatt = {
        "schema": "EMS_QUATT_CURRENT_STATE_V0.1",
        "generatedAt": iso,
        "observerOnly": {
            "cvActive": {
                "value": cv_active,
                "observedAt": iso,
                "sourceLastUpdated": iso,
            },
        },
    }
    model = ROOM_MODEL.build_model(_schedule(), observed, generated_at=now)
    plan = PLAN.build_plan(model, generated_at=now)
    heating = SHADOW.build_shadow(model, plan, quatt, generated_at=now)
    return {x["key"]: x for x in heating["rooms"]}, heating


def test_19_oct_1700_three_hour_lookahead_then_1845_paired_guard():
    early, h_early = _snapshot(
        17, 0, woonkamer_temp=18.0, woonkamer_setpoint=15.5
    )
    living = early["woonkamer"]
    assert h_early["house"]["preheatBlockingBaselineDemandPresent"] is False
    assert living["candidate"]["status"] == "ELIGIBLE_UP_TRANSITION"
    assert living["baseline"]["targetTemperature_C"] == 19.0
    assert living["baseline"]["changeAt"] == "2026-10-19T19:30:00+02:00"
    assert living["shadow"]["state"] == "PREHEAT_READY_FOR_GRANT"
    assert living["shadow"]["nextStepTarget_C"] == 18.5
    # READY does not mean a grant, P1 permission, heating, or savings.
    assert living["shadow"]["plannerGrant"] == "NOT_EVALUATED"
    assert h_early["controlWrites"] is False

    late, h_late = _snapshot(
        18, 45, woonkamer_temp=18.0, woonkamer_setpoint=18.5
    )
    dining = late["eetkamer"]
    assert h_late["house"]["preheatBlockingBaselineDemandRooms"] == ["woonkamer"]
    assert late["woonkamer"]["shadow"]["state"] == "BASELINE_HEATING"
    assert dining["shadow"]["state"] == "PREHEAT_READY_FOR_GRANT"
    assert dining["shadow"]["pairedBaselineException"] is True
    assert dining["shadow"]["pairedDemandRoom"] == "woonkamer"
    assert dining["baseline"]["currentTargetTemperature_C"] == 17.5
    assert dining["baseline"]["targetTemperature_C"] == 18.0
    assert dining["shadow"]["nextStepTarget_C"] == 18.0
    assert h_late["controlWrites"] is False


def test_19_oct_paired_exception_does_not_bypass_cv_guard():
    rooms, _ = _snapshot(
        18, 45, woonkamer_temp=18.0, woonkamer_setpoint=18.5,
        cv_active=True,
    )
    assert rooms["eetkamer"]["shadow"]["pairedBaselineException"] is True
    assert rooms["eetkamer"]["shadow"]["state"] == "PREHEAT_BLOCKED_CV_ASSIST"

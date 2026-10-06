import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parents[3] / "services/pi/planner/heating/build_heating_preheat_progression_shadow_v0_4.py"
spec = importlib.util.spec_from_file_location("heating_preheat_progression_v04", MODULE)
m = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def room(key="woonkamer", actual=17.2, future=19.0, state="PREHEAT_READY_FOR_GRANT",
         reason="AWAITING_CENTRAL_PV_PRIORITY", next_step=17.5, group="living_area",
         close="2026-09-26T15:00:00Z"):
    return {
        "key": key,
        "displayName": key.title(),
        "preheatScope": True,
        "group": group,
        "current": {"temperature_C": actual, "baselineDemand": False},
        "baseline": {
            "currentTargetTemperature_C": 15.5,
            "changeAt": close,
            "targetTemperature_C": future,
            "direction": "UP",
        },
        "candidate": {
            "status": "ELIGIBLE_UP_TRANSITION" if state == "PREHEAT_READY_FOR_GRANT" else "NOT_ELIGIBLE",
            "reason": "AWAITING_PV_OPPORTUNITY_EVALUATION",
            "opportunityOpensAt": "2026-09-26T12:00:00Z",
            "opportunityClosesAt": close,
            "steps_C": [17.5, 18.0, 18.5, 19.0],
        },
        "shadow": {
            "state": state,
            "reason": reason,
            "plannerGrant": "NOT_EVALUATED",
            "activeStepTarget_C": None,
            "activeStepReached": None,
            "nextStepTarget_C": next_step,
        },
    }


def heating(*rooms, generated="2026-09-26T11:59:00Z"):
    if not rooms:
        rooms = (room(),)
    return {
        "schema": "EMS_HEATING_PREHEAT_SHADOW_V0.3",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "generatedAt": generated,
        "baselineAuthority": "HONEYWELL",
        "rooms": list(rooms),
    }


def planner_grant(*, grant=True, ready=None, generated="2026-09-26T11:59:30Z",
                  reason="HEATING_WINDOW_CLOSES_FIRST"):
    if ready is None:
        ready = ["woonkamer"]
    return {
        "schema": "EMS_PI_DYNAMIC_HEATING_GRANT_V0.1",
        "generatedAt": generated,
        "validUntil": "2026-09-26T12:05:00Z",
        "mode": "PRODUCTION_PLANNER_GRANT",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "allocationAuthority": "DYNAMIC_PI_PLANNER",
        "baselineAuthority": "HONEYWELL",
        "heating": {
            "readyRooms": ready,
            "grant": "PRODUCTION_GRANT" if grant else "HOLD",
            "reason": reason,
            "priorityReason": reason,
            "priorityOwner": "HEATING" if grant else "EV",
        },
    }


def previous_room(key="woonkamer", target=17.5, state="STEP_WAIT", group="living_area",
                  close="2026-09-26T15:00:00Z", future=19.0, completed=None,
                  reason="WAITING_FOR_MEASURED_TEMPERATURE", history=None,
                  opportunity_history=None):
    return {
        "key": key,
        "group": group,
        "opportunityId": f"{key}|{close}|{future:.3f}",
        "opportunityHistory": list(opportunity_history or []),
        "stepHistory": list(history or []),
        "progression": {
            "state": state,
            "reason": reason,
            "activeStepTarget_C": target,
            "activeStepReached": False,
            "activeStepStartedAt": "2026-09-26T11:55:00Z",
            "nextStepTarget_C": target + 0.5 if target is not None else None,
            "completedSteps_C": list(completed or []),
            "lastTransition": "STARTED_STEP",
            "lastTransitionAt": "2026-09-26T11:55:00Z",
            "physicalWritePerformed": False,
        },
    }


def previous(*rooms):
    return {
        "schema": "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "rooms": list(rooms),
    }


def build(h=None, g=None, prev=None):
    return m.build_progression(
        h or heating(),
        g or planner_grant(),
        prev,
        generated_at=NOW,
    )


def progression(out, key="woonkamer"):
    return next(r for r in out["rooms"] if r["key"] == key)["progression"]


def test_grant_starts_first_shadow_step_without_physical_write():
    out = build()
    p = progression(out)
    assert p["state"] == "STEP_WAIT"
    assert p["activeStepTarget_C"] == 17.5
    assert p["activeStepReached"] is False
    assert p["lastTransition"] == "STARTED_STEP"
    assert p["physicalWritePerformed"] is False
    assert out["controlWrites"] is False
    assert out["physicalWriteAllowed"] is False


def test_without_grant_no_step_is_started():
    out = build(g=planner_grant(grant=False, reason="EV_SLACK_CLOSES_BEFORE_HEATING_WINDOW"))
    p = progression(out)
    assert p["state"] == "WAITING_FOR_GRANT"
    assert p["activeStepTarget_C"] is None


def test_active_step_waits_until_measured_temperature_reaches_target():
    prev = previous(previous_room(target=17.5))
    out = build(h=heating(room(actual=17.4)), prev=prev)
    p = progression(out)
    assert p["state"] == "STEP_WAIT"
    assert p["activeStepTarget_C"] == 17.5
    assert p["activeStepReached"] is False
    assert p["lastTransition"] == "STARTED_STEP"


def test_reached_step_advances_by_at_most_half_degree():
    prev = previous(previous_room(target=17.5))
    out = build(h=heating(room(actual=17.5, next_step=18.0)), prev=prev)
    p = progression(out)
    assert p["state"] == "STEP_WAIT"
    assert p["activeStepTarget_C"] == 18.0
    assert p["activeStepReached"] is False
    assert p["completedSteps_C"] == [17.5]
    assert p["lastTransition"] == "ADVANCED_STEP"


def test_up_opportunity_window_is_persisted_even_without_planner_grant():
    out = build(g=planner_grant(grant=False, reason="EV_SLACK_CLOSES_BEFORE_HEATING_WINDOW"))
    r = next(r for r in out["rooms"] if r["key"] == "woonkamer")

    assert r["opportunityHistory"] == [{
        "opportunityId": "woonkamer|2026-09-26T15:00:00Z|19.000",
        "opensAt": "2026-09-26T12:00:00Z",
        "closesAt": "2026-09-26T15:00:00Z",
        "target_C": 19.0,
    }]


def test_opportunity_window_survives_after_honeywell_moves_to_next_transition():
    first = build()
    later_room = room(
        state="NOT_ELIGIBLE",
        reason="BASELINE_DOWN",
        next_step=None,
        close="2026-09-26T16:00:00Z",
    )
    later_room["baseline"]["direction"] = "DOWN"
    later_room["candidate"]["status"] = "NOT_ELIGIBLE"
    later_room["candidate"]["opportunityOpensAt"] = "2026-09-26T13:00:00Z"
    later_room["candidate"]["opportunityClosesAt"] = "2026-09-26T16:00:00Z"

    second = m.build_progression(
        heating(later_room, generated="2026-09-26T12:00:30Z"),
        planner_grant(
            grant=False,
            ready=[],
            generated="2026-09-26T12:00:45Z",
            reason="NO_HEATING_GRANT",
        ),
        first,
        generated_at=datetime(2026, 9, 26, 12, 1, tzinfo=timezone.utc),
    )
    r = next(r for r in second["rooms"] if r["key"] == "woonkamer")

    assert len(r["opportunityHistory"]) == 1
    assert r["opportunityHistory"][0]["opportunityId"] == "woonkamer|2026-09-26T15:00:00Z|19.000"
    assert r["opportunityHistory"][0]["opensAt"] == "2026-09-26T12:00:00Z"
    assert r["opportunityHistory"][0]["closesAt"] == "2026-09-26T15:00:00Z"


def test_advanced_step_archives_previous_shadow_intent_interval():
    prev = previous(previous_room(target=17.5))
    out = build(h=heating(room(actual=17.5, next_step=18.0)), prev=prev)
    r = next(r for r in out["rooms"] if r["key"] == "woonkamer")

    assert r["stepHistory"] == [{
        "opportunityId": "woonkamer|2026-09-26T15:00:00Z|19.000",
        "target_C": 17.5,
        "startedAt": "2026-09-26T11:55:00Z",
        "endedAt": "2026-09-26T12:00:00Z",
        "outcome": "ADVANCED_STEP",
        "reason": "ADVANCED_AFTER_MEASURED_STEP_COMPLETION",
    }]
    assert r["progression"]["activeStepTarget_C"] == 18.0
    assert r["progression"]["activeStepStartedAt"] == "2026-09-26T12:00:00Z"


def test_completed_final_step_remains_available_as_interval_history():
    prev = previous(previous_room(target=19.0, future=19.0, completed=[17.5, 18.0, 18.5]))
    out = build(h=heating(room(actual=19.0, future=19.0, next_step=None)), prev=prev)
    r = next(r for r in out["rooms"] if r["key"] == "woonkamer")

    assert r["progression"]["state"] == "COMPLETE_TARGET_REACHED"
    assert r["progression"]["activeStepTarget_C"] is None
    assert r["progression"]["activeStepStartedAt"] is None
    assert r["stepHistory"][-1]["target_C"] == 19.0
    assert r["stepHistory"][-1]["startedAt"] == "2026-09-26T11:55:00Z"
    assert r["stepHistory"][-1]["endedAt"] == "2026-09-26T12:00:00Z"
    assert r["stepHistory"][-1]["outcome"] == "TARGET_REACHED"


def test_step_history_survives_new_honeywell_opportunity_and_closes_old_active_step():
    prev = previous(previous_room(
        target=17.5,
        close="2026-09-26T15:00:00Z",
        future=19.0,
        history=[{
            "opportunityId": "woonkamer|2026-09-25T15:00:00Z|18.500",
            "target_C": 18.0,
            "startedAt": "2026-09-26T10:00:00Z",
            "endedAt": "2026-09-26T10:20:00Z",
            "outcome": "TARGET_REACHED",
            "reason": "FUTURE_HONEYWELL_TARGET_REACHED",
        }],
    ))
    out = build(
        h=heating(room(close="2026-09-26T16:00:00Z")),
        prev=prev,
    )
    r = next(r for r in out["rooms"] if r["key"] == "woonkamer")

    assert len(r["stepHistory"]) == 2
    assert r["stepHistory"][0]["target_C"] == 18.0
    assert r["stepHistory"][1]["target_C"] == 17.5
    assert r["stepHistory"][1]["outcome"] == "OPPORTUNITY_CHANGED"
    assert r["stepHistory"][1]["endedAt"] == "2026-09-26T12:00:00Z"


def test_unchanged_active_step_does_not_duplicate_history():
    history = [{
        "opportunityId": "woonkamer|2026-09-26T15:00:00Z|19.000",
        "target_C": 17.0,
        "startedAt": "2026-09-26T11:00:00Z",
        "endedAt": "2026-09-26T11:15:00Z",
        "outcome": "ADVANCED_STEP",
        "reason": "ADVANCED_AFTER_MEASURED_STEP_COMPLETION",
    }]
    prev = previous(previous_room(target=17.5, history=history))
    out = build(h=heating(room(actual=17.4)), prev=prev)
    r = next(r for r in out["rooms"] if r["key"] == "woonkamer")

    assert r["stepHistory"] == history


def test_grant_loss_holds_existing_step_and_never_advances():
    prev = previous(previous_room(target=17.5))
    out = build(
        h=heating(room(actual=17.6, next_step=18.0)),
        g=planner_grant(grant=False, reason="EV_DEADLINE_MUST"),
        prev=prev,
    )
    p = progression(out)
    assert p["state"] == "STEP_HOLD_NO_GRANT"
    assert p["activeStepTarget_C"] == 17.5
    assert p["lastTransition"] == "HOLD"


def test_cv_assist_blocks_progression_and_retains_shadow_evidence():
    prev = previous(previous_room(target=17.5))
    blocked = room(
        actual=17.4,
        state="PREHEAT_BLOCKED_CV_ASSIST",
        reason="CV_ASSIST_DURING_PURE_PREHEAT",
        next_step=None,
    )
    out = build(h=heating(blocked), prev=prev)
    p = progression(out)
    assert p["state"] == "BLOCKED_CV_ASSIST"
    assert p["activeStepTarget_C"] == 17.5
    assert p["lastTransition"] == "BLOCKED"


def test_baseline_heating_ends_preheat_progression():
    prev = previous(previous_room(target=17.5))
    baseline = room(
        actual=17.4,
        state="BASELINE_HEATING",
        reason="BASELINE_HEATING_DEMAND_PRESENT",
        next_step=None,
    )
    out = build(h=heating(baseline), prev=prev)
    p = progression(out)
    assert p["state"] == "ENDED_BASELINE_HEATING"
    assert p["activeStepTarget_C"] is None


def test_stale_or_pre_dating_priority_fails_closed_for_new_step():
    out = build(
        h=heating(generated="2026-09-26T11:59:45Z"),
        g=planner_grant(generated="2026-09-26T11:59:30Z"),
    )
    p = progression(out)
    assert p["state"] == "WAITING_FOR_FRESH_PRIORITY"
    assert p["activeStepTarget_C"] is None
    assert p["reason"] == "PRODUCTION_GRANT_PRE_DATES_HEATING_STATE"


def test_living_group_waits_until_both_selected_rooms_reach_active_step():
    w = room(key="woonkamer", actual=17.5, next_step=18.0)
    e = room(key="eetkamer", actual=17.4, next_step=18.0)
    prev = previous(
        previous_room(key="woonkamer", target=17.5),
        previous_room(key="eetkamer", target=17.5),
    )
    out = build(
        h=heating(w, e),
        g=planner_grant(ready=["woonkamer", "eetkamer"]),
        prev=prev,
    )
    wp = progression(out, "woonkamer")
    ep = progression(out, "eetkamer")
    assert wp["state"] == "STEP_REACHED_GROUP_WAIT"
    assert wp["activeStepTarget_C"] == 17.5
    assert ep["state"] == "STEP_WAIT"
    assert ep["activeStepTarget_C"] == 17.5


def test_living_group_advances_together_after_both_reach():
    w = room(key="woonkamer", actual=17.5, next_step=18.0)
    e = room(key="eetkamer", actual=17.6, next_step=18.0)
    prev = previous(
        previous_room(key="woonkamer", target=17.5),
        previous_room(key="eetkamer", target=17.5),
    )
    out = build(
        h=heating(w, e),
        g=planner_grant(ready=["woonkamer", "eetkamer"]),
        prev=prev,
    )
    assert progression(out, "woonkamer")["activeStepTarget_C"] == 18.0
    assert progression(out, "eetkamer")["activeStepTarget_C"] == 18.0
    assert progression(out, "woonkamer")["lastTransition"] == "ADVANCED_STEP"
    assert progression(out, "eetkamer")["lastTransition"] == "ADVANCED_STEP"



def test_unchanged_inactive_state_preserves_last_transition_event_time():
    first = build(
        h=heating(room(state="NOT_ELIGIBLE", reason="OUTSIDE_MAX_ADVANCE_WINDOW", next_step=None)),
        g=planner_grant(grant=False, ready=[]),
    )
    first_room = next(r for r in first["rooms"] if r["key"] == "woonkamer")
    assert first_room["progression"]["lastTransition"] == "RESET"
    first_time = first_room["progression"]["lastTransitionAt"]

    second = m.build_progression(
        heating(room(state="NOT_ELIGIBLE", reason="OUTSIDE_MAX_ADVANCE_WINDOW", next_step=None)),
        planner_grant(grant=False, ready=[]),
        first,
        generated_at=datetime(2026, 9, 26, 12, 1, tzinfo=timezone.utc),
    )
    p = progression(second)
    assert p["state"] == "INACTIVE"
    assert p["lastTransition"] == "RESET"
    assert p["lastTransitionAt"] == first_time


def test_unchanged_step_wait_preserves_last_transition_event_time():
    prev = previous(previous_room(target=17.5))
    out = build(h=heating(room(actual=17.4)), prev=prev)
    p = progression(out)
    assert p["state"] == "STEP_WAIT"
    assert p["lastTransition"] == "STARTED_STEP"
    assert p["lastTransitionAt"] == "2026-09-26T11:55:00Z"

def test_policy_keeps_shadow_boundaries_explicit():
    policy = build()["policy"]
    assert policy["maxStep_C"] == 0.5
    assert policy["advanceOnlyAfterMeasuredStepReached"] is True
    assert policy["groupAdvanceRequiresAllSelectedRoomsReached"] is True
    assert policy["plannerGrantRequiredForStartAndAdvance"] is True
    assert policy["intentionalGridImportAllowed"] is False
    assert policy["rollbackBehavior"] == "NOT_DEFINED_SHADOW_ONLY"
    assert policy["stepHistoryRetentionHours"] == 48
    assert policy["opportunityHistoryRetentionHours"] == 48

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


def priority(*, grant=True, ready=None, generated="2026-09-26T11:59:30Z",
             reason="HEATING_WINDOW_CLOSES_FIRST"):
    if ready is None:
        ready = ["woonkamer"]
    return {
        "schema": "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "generatedAt": generated,
        "heating": {
            "readyRooms": ready,
            "earliestOpportunityClosesAt": "2026-09-26T15:00:00Z",
        },
        "decision": {
            "priorityOwner": "HEATING" if grant else "EV",
            "heatingShadowGrant": "SHADOW_GRANT" if grant else "HOLD",
            "evRole": "RESIDUAL_OPPORTUNITY" if grant else "PRIMARY_OPPORTUNITY",
            "reason": reason,
            "appliesOnlyWhenPvOpportunityExists": True,
            "physicalWriteAllowed": False,
        },
    }


def previous_room(key="woonkamer", target=17.5, state="STEP_WAIT", group="living_area",
                  close="2026-09-26T15:00:00Z", future=19.0, completed=None):
    return {
        "key": key,
        "group": group,
        "opportunityId": f"{key}|{close}|{future:.3f}",
        "progression": {
            "state": state,
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


def build(h=None, p=None, prev=None):
    return m.build_progression(
        h or heating(),
        p or priority(),
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
    out = build(p=priority(grant=False, reason="EV_SLACK_CLOSES_BEFORE_HEATING_WINDOW"))
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
    assert p["lastTransition"] == "NONE"


def test_reached_step_advances_by_at_most_half_degree():
    prev = previous(previous_room(target=17.5))
    out = build(h=heating(room(actual=17.5, next_step=18.0)), prev=prev)
    p = progression(out)
    assert p["state"] == "STEP_WAIT"
    assert p["activeStepTarget_C"] == 18.0
    assert p["activeStepReached"] is False
    assert p["completedSteps_C"] == [17.5]
    assert p["lastTransition"] == "ADVANCED_STEP"


def test_grant_loss_holds_existing_step_and_never_advances():
    prev = previous(previous_room(target=17.5))
    out = build(
        h=heating(room(actual=17.6, next_step=18.0)),
        p=priority(grant=False, reason="EV_DEADLINE_MUST"),
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
        p=priority(generated="2026-09-26T11:59:30Z"),
    )
    p = progression(out)
    assert p["state"] == "WAITING_FOR_FRESH_PRIORITY"
    assert p["activeStepTarget_C"] is None
    assert p["reason"] == "PRIORITY_PRE_DATES_HEATING_STATE"


def test_living_group_waits_until_both_selected_rooms_reach_active_step():
    w = room(key="woonkamer", actual=17.5, next_step=18.0)
    e = room(key="eetkamer", actual=17.4, next_step=18.0)
    prev = previous(
        previous_room(key="woonkamer", target=17.5),
        previous_room(key="eetkamer", target=17.5),
    )
    out = build(
        h=heating(w, e),
        p=priority(ready=["woonkamer", "eetkamer"]),
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
        p=priority(ready=["woonkamer", "eetkamer"]),
        prev=prev,
    )
    assert progression(out, "woonkamer")["activeStepTarget_C"] == 18.0
    assert progression(out, "eetkamer")["activeStepTarget_C"] == 18.0
    assert progression(out, "woonkamer")["lastTransition"] == "ADVANCED_STEP"
    assert progression(out, "eetkamer")["lastTransition"] == "ADVANCED_STEP"


def test_policy_keeps_shadow_boundaries_explicit():
    policy = build()["policy"]
    assert policy["maxStep_C"] == 0.5
    assert policy["advanceOnlyAfterMeasuredStepReached"] is True
    assert policy["groupAdvanceRequiresAllSelectedRoomsReached"] is True
    assert policy["plannerGrantRequiredForStartAndAdvance"] is True
    assert policy["intentionalGridImportAllowed"] is False
    assert policy["rollbackBehavior"] == "NOT_DEFINED_SHADOW_ONLY"

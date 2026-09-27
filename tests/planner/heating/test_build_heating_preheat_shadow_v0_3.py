import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).parents[3] / "services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py"
spec = importlib.util.spec_from_file_location("heating_preheat_shadow_v03", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def room_model(actual=17.2, baseline=15.5, future=19.0, key="woonkamer"):
    return {
        "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": "2026-09-26T11:59:00Z",
        "timezone": "Europe/Amsterdam",
        "baselineAuthority": "HONEYWELL",
        "valid": True,
        "rooms": [{
            "key": key,
            "displayName": key.title(),
            "valid": True,
            "current": {
                "temperature_C": actual,
                "targetTemperature_C": baseline,
                "setpointMode": "FOLLOW_SCHEDULE",
            },
            "baseline": {
                "currentTarget_C": baseline,
                "currentSince": "2026-09-26T08:00:00+02:00",
                "nextChangeAt": "2026-09-26T16:00:00+02:00",
                "nextTarget_C": future,
                "direction": "UP",
            },
        }],
    }


def candidate(status="ELIGIBLE_UP_TRANSITION", reason="AWAITING_PV_OPPORTUNITY_EVALUATION", steps=None, key="woonkamer"):
    return {
        "schema": "EMS_HEATING_PREHEAT_PLAN_V0.2",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": "2026-09-26T12:00:00Z",
        "timezone": "Europe/Amsterdam",
        "baselineAuthority": "HONEYWELL",
        "policy": {"maxAdvanceMinutes": 180},
        "rooms": [{
            "key": key,
            "displayName": key.title(),
            "preheatScope": True,
            "group": "living_area" if key in {"woonkamer", "eetkamer"} else None,
            "candidate": {
                "status": status,
                "earliestStartAt": "2026-09-26T13:00:00+02:00",
                "startAt": None,
                "targetTemperature_C": 19.0,
                "steps_C": steps if steps is not None else [17.5, 18.0, 18.5, 19.0],
                "reason": reason,
            },
        }],
    }


def quatt(
    assist=False,
    generated="2026-09-26T11:59:30Z",
    observed_at=None,
    source_last_updated=None,
):
    observed_at = observed_at or generated
    source_last_updated = source_last_updated or generated
    return {
        "schema": "EMS_QUATT_CURRENT_STATE_V0.1",
        "generatedAt": generated,
        "mode": "READ_ONLY",
        "observerOnly": {
            "cvActive": {
                "value": assist,
                "observedAt": observed_at,
                "sourceLastUpdated": source_last_updated,
            },
        },
    }


def build(model=None, plan=None, q=None):
    return module.build_shadow(
        model or room_model(),
        plan or candidate(),
        q or quatt(),
        generated_at=NOW,
    )


def test_v03_is_read_only_and_never_grants_or_activates_a_step_itself():
    result = build()
    r = result["rooms"][0]
    assert result["schema"] == "EMS_HEATING_PREHEAT_SHADOW_V0.3"
    assert result["mode"] == "READ_ONLY"
    assert result["controlMode"] == "SHADOW"
    assert result["controlWrites"] is False
    assert r["shadow"]["state"] == "PREHEAT_READY_FOR_GRANT"
    assert r["shadow"]["plannerGrant"] == "NOT_EVALUATED"
    assert r["shadow"]["activeStepTarget_C"] is None
    assert r["shadow"]["nextStepTarget_C"] == 17.5


def test_normal_baseline_heating_blocks_new_preheat_but_is_not_cv_fault():
    result = build(model=room_model(actual=17.0, baseline=18.0), q=quatt(assist=True))
    r = result["rooms"][0]
    assert result["house"]["baselineHeatingDemandPresent"] is True
    assert result["house"]["baselineDemandRooms"] == ["woonkamer"]
    assert r["shadow"]["state"] == "BASELINE_HEATING"
    assert r["shadow"]["reason"] == "BASELINE_HEATING_DEMAND_PRESENT"


def test_cv_assist_during_pure_preheat_blocks_further_preheat():
    result = build(q=quatt(assist=True))
    r = result["rooms"][0]
    assert result["house"]["baselineHeatingDemandPresent"] is False
    assert result["cvGuard"]["cvActive"] is True
    assert r["shadow"]["state"] == "PREHEAT_BLOCKED_CV_ASSIST"
    assert r["shadow"]["reason"] == "CV_ASSIST_DURING_PURE_PREHEAT"


def test_stale_cv_status_fails_closed_for_new_preheat_increment():
    result = build(q=quatt(assist=False, generated="2026-09-26T11:45:00Z"))
    r = result["rooms"][0]
    assert result["cvGuard"]["status"] == "STALE"
    assert r["shadow"]["state"] == "PREHEAT_BLOCKED_CV_STATUS_UNKNOWN"


def test_old_source_change_time_does_not_make_fresh_observation_stale():
    result = build(q=quatt(
        assist=False,
        generated="2026-09-26T11:59:30Z",
        observed_at="2026-09-26T11:59:30Z",
        source_last_updated="2026-09-24T07:15:32Z",
    ))
    guard = result["cvGuard"]
    assert guard["status"] == "OK"
    assert guard["cvActive"] is False
    assert guard["ageSeconds"] == 30.0
    assert guard["sourceLastUpdated"] == "2026-09-24T07:15:32Z"


def test_observed_at_must_match_same_successful_collector_fetch():
    result = build(q=quatt(
        assist=False,
        generated="2026-09-26T11:59:30Z",
        observed_at="2026-09-26T11:59:20Z",
        source_last_updated="2026-09-24T07:15:32Z",
    ))
    guard = result["cvGuard"]
    r = result["rooms"][0]
    assert guard["status"] == "UNKNOWN"
    assert guard["reason"] == "CV_ACTIVE_OBSERVATION_MISMATCH"
    assert guard["cvActive"] is None
    assert r["shadow"]["state"] == "PREHEAT_BLOCKED_CV_STATUS_UNKNOWN"


def test_missing_cv_observation_time_fails_closed():
    q = quatt()
    del q["observerOnly"]["cvActive"]["observedAt"]
    result = build(q=q)
    guard = result["cvGuard"]
    assert guard["status"] == "UNKNOWN"
    assert guard["reason"] == "CV_ACTIVE_OBSERVED_AT_INVALID"
    assert result["rooms"][0]["shadow"]["state"] == "PREHEAT_BLOCKED_CV_STATUS_UNKNOWN"


def test_noneligible_v02_candidate_stays_noneligible():
    p = candidate(status="NOT_ELIGIBLE", reason="OUTSIDE_MAX_ADVANCE_WINDOW", steps=[])
    r = build(plan=p)["rooms"][0]
    assert r["shadow"]["state"] == "NOT_ELIGIBLE"
    assert r["shadow"]["reason"] == "OUTSIDE_MAX_ADVANCE_WINDOW"
    assert r["shadow"]["nextStepTarget_C"] is None


def test_policy_records_iteration_and_step_guards():
    policy = build()["policy"]
    assert policy["maxAdvanceMinutes"] == 180.0
    assert policy["maxStep_C"] == 0.5
    assert policy["cvCheckedEveryIteration"] is True
    assert policy["advanceOnlyAfterCurrentStepReached"] is True
    assert policy["normalBaselineCvIsNotPreheatFault"] is True
    assert policy["purePreheatCvAssistBlocksFurtherSteps"] is True
    assert policy["plannerGrantRequiredBeforeAnyFutureWrite"] is True
    assert policy["intentionalGridImportAllowed"] is False

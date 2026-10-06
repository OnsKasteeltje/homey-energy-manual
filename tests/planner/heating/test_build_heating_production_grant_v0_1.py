import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "services/pi/planner/heating/build_heating_production_grant_v0_1.py"

spec = importlib.util.spec_from_file_location("heating_production_grant_v01", MODULE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 10, 6, 12, 7, tzinfo=timezone.utc)


def dynamic_plan(
    *,
    generated="2026-10-06T12:00:00Z",
    valid_until="2026-10-06T12:20:00Z",
    residual=1800,
    after=300,
    ev_w=1500,
):
    return {
        "schema": "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3",
        "generated_at": generated,
        "validUntil": valid_until,
        "mode": "PURE_SHADOW",
        "readOnly": True,
        "control_writes": False,
        "plannerOwner": "PI",
        "slots": [{
            "slot_start_utc": "2026-10-06T12:00:00Z",
            "evResidualExportW": residual,
            "evPlanW": ev_w,
            "gridExportAfterFlexW": after,
        }],
    }


def heating(*, generated="2026-10-06T12:05:00Z", state="PREHEAT_READY_FOR_GRANT"):
    return {
        "schema": "EMS_HEATING_PREHEAT_SHADOW_V0.3",
        "generatedAt": generated,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "baselineAuthority": "HONEYWELL",
        "rooms": [{
            "key": "woonkamer",
            "shadow": {"state": state},
        }],
    }


def priority(
    *,
    generated="2026-10-06T12:05:10Z",
    owner="HEATING",
    grant="SHADOW_GRANT",
    ready=None,
    reason="HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE",
):
    return {
        "schema": "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1",
        "generatedAt": generated,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "heating": {
            "readyRooms": ["woonkamer"] if ready is None else ready,
        },
        "decision": {
            "priorityOwner": owner,
            "heatingShadowGrant": grant,
            "physicalWriteAllowed": False,
            "reason": reason,
        },
    }


def energy_state(
    *,
    generated="2026-10-06T12:06:30Z",
    export_w=900,
    import_w=0,
):
    return {
        "generatedAt": generated,
        "grid": {
            "export_w": export_w,
            "import_w": import_w,
        },
    }


def build(d=None, h=None, p=None, e=None, now=NOW):
    return m.build_heating_grant(
        d or dynamic_plan(),
        h or heating(),
        p or priority(),
        e or energy_state(),
        generated_at=now,
    )


def test_fresh_p1_export_plus_heating_priority_yields_production_grant():
    out = build()
    assert out["schema"] == "EMS_PI_DYNAMIC_HEATING_GRANT_V0.1"
    assert out["mode"] == "PRODUCTION_PLANNER_GRANT"
    assert out["allocationAuthority"] == "DYNAMIC_PI_PLANNER"
    assert out["realtimeAuthority"] == "P1"
    assert out["baselineAuthority"] == "HONEYWELL"
    assert out["heating"]["grant"] == "PRODUCTION_GRANT"
    assert out["heating"]["readyRooms"] == ["woonkamer"]
    assert out["heating"]["reason"] == "PRODUCTION_GRANT_PLANNED_SHARED_PV_OPPORTUNITY"
    assert out["physicalWriteAllowed"] is False
    assert out["controlWrites"] is False


def test_shared_planner_opportunity_is_before_ev_residual_consumption():
    out = build()
    f = out["forecastOpportunity"]
    assert f["sharedResidualBeforeEvW"] == 1800
    assert f["evPlannedW"] == 1500
    assert f["exportAfterExistingFlexW"] == 300
    assert f["roleOfEvWhenHeatingFirst"] == "RESIDUAL_OPPORTUNITY"
    assert f["powerReservationW"] == 0


def test_forecast_alone_never_grants_without_current_p1_export():
    out = build(e=energy_state(export_w=0, import_w=0))
    assert out["forecastOpportunity"]["plannedOpportunityPresent"] is True
    assert out["realtimePermission"]["allowed"] is False
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "NO_P1_EXPORT"


def test_fresh_unforecast_p1_export_may_still_grant():
    out = build(d=dynamic_plan(residual=0, after=0, ev_w=0))
    assert out["forecastOpportunity"]["plannedOpportunityPresent"] is False
    assert out["realtimePermission"]["allowed"] is True
    assert out["heating"]["grant"] == "PRODUCTION_GRANT"
    assert out["heating"]["reason"] == "PRODUCTION_GRANT_UNPLANNED_P1_EXPORT"
    assert out["policy"]["freshP1MayAuthorizeUnforecastExport"] is True


def test_any_p1_import_blocks_heating_grant():
    out = build(e=energy_state(export_w=0, import_w=250))
    assert out["realtimePermission"]["allowed"] is False
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "P1_IMPORT_PRESENT"


def test_ev_priority_blocks_heating_even_with_export():
    out = build(
        p=priority(
            owner="EV",
            grant="HOLD",
            reason="EV_DEADLINE_MUST",
        )
    )
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "EV_DEADLINE_MUST"


def test_stale_p1_fails_closed():
    out = build(e=energy_state(generated="2026-10-06T12:04:00Z"))
    assert out["sourceFreshness"]["p1"]["status"] == "STALE"
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "P1_STATE_STALE"


def test_priority_must_not_pre_date_heating_state():
    out = build(
        h=heating(generated="2026-10-06T12:05:20Z"),
        p=priority(generated="2026-10-06T12:05:10Z"),
    )
    assert out["sourceFreshness"]["priorityConsistentWithHeating"] is False
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "FLEX_PRIORITY_PRE_DATES_HEATING"


def test_expired_dynamic_plan_fails_closed():
    out = build(d=dynamic_plan(valid_until="2026-10-06T12:06:59Z"))
    assert out["sourceFreshness"]["dynamicPlan"]["status"] == "STALE"
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "DYNAMIC_PLAN_STALE_OR_NOT_CURRENT"


def test_grant_validity_is_bounded_by_current_slot_and_source_freshness():
    out = build()
    # Earliest expiry wins: Flex Priority at 12:05:10 + 120 s = 12:07:10,
    # before P1 (12:08:30), Heating (12:12:00), slot end (12:15) and plan TTL.
    assert out["validUntil"] == "2026-10-06T12:07:10Z"


def test_revision_is_stable_for_identical_semantics():
    first = build()
    second = build()
    assert first["grantRevision"] == second["grantRevision"]

    changed = build(e=energy_state(export_w=901))
    assert changed["grantRevision"] != first["grantRevision"]


def test_no_ready_heating_candidate_holds():
    out = build(h=heating(state="NOT_ELIGIBLE"), p=priority(ready=[]))
    assert out["heating"]["grant"] == "HOLD"
    assert out["heating"]["reason"] == "NO_HEATING_PREHEAT_CANDIDATE"


def test_contract_rejects_wrong_planner_owner():
    bad = dynamic_plan()
    bad["plannerOwner"] = "HOMEY"
    try:
        build(d=bad)
    except m.HeatingGrantError as exc:
        assert "plannerOwner=PI" in str(exc)
    else:
        raise AssertionError("expected HeatingGrantError")

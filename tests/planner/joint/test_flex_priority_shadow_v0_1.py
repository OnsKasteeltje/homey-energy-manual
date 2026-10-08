import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parents[3] / "services/pi/planner/joint/build_flex_priority_shadow_v0_1.py"
spec = importlib.util.spec_from_file_location("flex_priority_shadow", MODULE)
m = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def heating(
    state="PREHEAT_READY_FOR_GRANT",
    closes="2026-09-26T15:00:00Z",
    key="woonkamer",
    generated="2026-09-26T11:59:00Z",
):
    return {
        "schema": "EMS_HEATING_PREHEAT_SHADOW_V0.3",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "generatedAt": generated,
        "rooms": [{
            "key": key,
            "group": "living_area",
            "candidate": {"opportunityClosesAt": closes},
            "shadow": {"state": state},
        }],
    }


def ev(*, active=False, remaining=0.0, status="INACTIVE",
       latest="2026-09-26T16:00:00Z", deadline="2026-09-26T18:00:00Z"):
    return {
        "schema": "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2",
        "readOnly": True,
        "controlWrites": False,
        "active": active,
        "remainingKWh": remaining,
        "status": status,
        "latestStartAt": latest,
        "deadlineAt": deadline,
    }


def build(h=None, e=None):
    return m.build_priority(h or heating(), e or ev(), generated_at=NOW)


def test_no_ev_deadline_gives_scarce_heating_window_first_claim():
    out = build()
    assert out["decision"]["priorityOwner"] == "HEATING"
    assert out["decision"]["heatingShadowGrant"] == "SHADOW_GRANT"
    assert out["decision"]["evRole"] == "RESIDUAL_OPPORTUNITY"
    assert out["policy"]["powerReservationW"] == 0
    assert out["decision"]["physicalWriteAllowed"] is False


def test_ev_must_overrides_heating():
    out = build(e=ev(active=True, remaining=4.0, status="TRACKING", latest="2026-09-26T11:59:00Z"))
    assert out["ev"]["urgency"] == "MUST"
    assert out["decision"]["priorityOwner"] == "EV"
    assert out["decision"]["heatingShadowGrant"] == "HOLD"
    assert out["decision"]["evRole"] == "MUST"


def test_expired_deadline_never_becomes_must_or_blocks_heating():
    out = build(
        e=ev(
            active=True,
            remaining=4.0,
            status="EXPIRED",
            latest="2026-09-26T11:00:00Z",
            deadline="2026-09-26T11:30:00Z",
        )
    )
    assert out["ev"]["urgency"] == "EXPIRED"
    assert out["ev"]["deadlineActive"] is False
    assert out["decision"]["priorityOwner"] == "HEATING"
    assert out["decision"]["heatingShadowGrant"] == "SHADOW_GRANT"
    assert out["decision"]["evRole"] == "RESIDUAL_OPPORTUNITY"
    assert out["decision"]["reason"] == "HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE"


def test_heating_first_when_its_window_closes_before_ev_latest_start():
    out = build(e=ev(active=True, remaining=4.0, status="TRACKING", latest="2026-09-26T16:00:00Z"))
    assert out["heating"]["earliestOpportunityClosesAt"] == "2026-09-26T15:00:00Z"
    assert out["ev"]["latestSafeStartAt"] == "2026-09-26T16:00:00Z"
    assert out["decision"]["priorityOwner"] == "HEATING"
    assert out["decision"]["reason"] == "HEATING_WINDOW_CLOSES_FIRST"


def test_ev_first_when_deadline_slack_closes_before_heating_window():
    out = build(
        h=heating(closes="2026-09-26T17:00:00Z"),
        e=ev(active=True, remaining=4.0, status="TRACKING", latest="2026-09-26T14:00:00Z"),
    )
    assert out["decision"]["priorityOwner"] == "EV"
    assert out["decision"]["heatingShadowGrant"] == "HOLD"
    assert out["decision"]["reason"] == "EV_SLACK_CLOSES_BEFORE_HEATING_WINDOW"


def test_invalid_active_deadline_fails_closed_for_heating_priority():
    out = build(e=ev(active=True, remaining=4.0, status="WAITING_FOR_CANONICAL_TELEMETRY"))
    assert out["ev"]["urgency"] == "INVALID_OR_UNCERTAIN"
    assert out["decision"]["priorityOwner"] == "HOLD_UNKNOWN"
    assert out["decision"]["heatingShadowGrant"] == "HOLD"


def test_no_heating_candidate_leaves_ev_as_primary_opportunity():
    out = build(h=heating(state="NOT_ELIGIBLE"))
    assert out["decision"]["priorityOwner"] == "EV"
    assert out["decision"]["evRole"] == "PRIMARY_OPPORTUNITY"


def test_earliest_ready_heating_window_drives_domain_priority():
    h = heating(closes="2026-09-26T17:00:00Z", key="woonkamer")
    h["rooms"].append({
        "key": "keuken",
        "group": None,
        "candidate": {"opportunityClosesAt": "2026-09-26T14:30:00Z"},
        "shadow": {"state": "PREHEAT_READY_FOR_GRANT"},
    })
    out = build(h=h, e=ev(active=True, remaining=4.0, status="TRACKING", latest="2026-09-26T15:30:00Z"))
    assert out["heating"]["readyRooms"] == ["keuken", "woonkamer"]
    assert out["heating"]["earliestOpportunityClosesAt"] == "2026-09-26T14:30:00Z"
    assert out["decision"]["priorityOwner"] == "HEATING"


def test_stale_heating_source_cannot_create_new_heating_grant():
    out = build(h=heating(generated="2026-09-26T11:52:00Z"))
    assert out["sourceFreshness"]["heating"]["status"] == "STALE"
    assert out["sourceFreshness"]["heating"]["reason"] == "HEATING_SHADOW_STALE"
    assert out["heating"]["readyRooms"] == []
    assert out["decision"]["priorityOwner"] == "HOLD_UNKNOWN"
    assert out["decision"]["heatingShadowGrant"] == "HOLD"
    assert out["decision"]["reason"] == "HEATING_SHADOW_STALE"


def test_ev_must_remains_authoritative_even_when_heating_source_is_stale():
    out = build(
        h=heating(generated="2026-09-26T11:52:00Z"),
        e=ev(active=True, remaining=4.0, status="TRACKING", latest="2026-09-26T11:59:00Z"),
    )
    assert out["sourceFreshness"]["heating"]["status"] == "STALE"
    assert out["decision"]["priorityOwner"] == "EV"
    assert out["decision"]["heatingShadowGrant"] == "HOLD"
    assert out["decision"]["evRole"] == "MUST"


def test_output_is_explicitly_read_only_shadow():
    out = build()
    assert out["schema"] == "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"
    assert out["mode"] == "READ_ONLY"
    assert out["controlMode"] == "SHADOW"
    assert out["controlWrites"] is False
    assert out["sourceFreshness"]["heating"]["status"] == "OK"
    assert out["policy"]["realtimeOpportunityAuthority"] == "P1"

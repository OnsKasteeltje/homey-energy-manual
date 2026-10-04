import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "services/pi/control/heating/build_heating_control_gate_shadow_v0_5.py"
INSTALLER = ROOT / "deploy/install/install_heating_control_gate_shadow_v0_5.sh"
SERVICE = ROOT / "deploy/systemd/ems-heating-control-gate-shadow.service"
TIMER = ROOT / "deploy/systemd/ems-heating-control-gate-shadow.timer"

spec = importlib.util.spec_from_file_location("heating_control_gate_v05", MODULE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 10, 4, 10, 0, 0, tzinfo=timezone.utc)
CLOSE = "2026-10-04T14:00:00+02:00"
OPPORTUNITY = f"woonkamer|{CLOSE}|19.000"


def heating(generated="2026-10-04T09:59:00Z"):
    return {
        "schema": "EMS_HEATING_PREHEAT_SHADOW_V0.3",
        "mode": "READ_ONLY", "controlMode": "SHADOW", "controlWrites": False,
        "generatedAt": generated, "baselineAuthority": "HONEYWELL",
        "cvGuard": {"status": "OK", "cvActive": False},
        "rooms": [{
            "key": "woonkamer", "displayName": "Woonkamer",
            "preheatScope": True, "group": "living_area",
            "baseline": {
                "currentTargetTemperature_C": 16.0, "changeAt": CLOSE,
                "targetTemperature_C": 19.0, "direction": "UP",
            },
            "shadow": {
                "state": "PREHEAT_READY_FOR_GRANT",
                "reason": "AWAITING_CENTRAL_PV_PRIORITY",
            },
        }],
    }


def progression(
    generated="2026-10-04T09:59:30Z",
    grant="SHADOW_GRANT",
    state="STEP_WAIT",
    target=17.5,
    opportunity=OPPORTUNITY,
):
    return {
        "schema": "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4",
        "mode": "READ_ONLY", "controlMode": "SHADOW", "controlWrites": False,
        "physicalWriteAllowed": False, "generatedAt": generated,
        "baselineAuthority": "HONEYWELL",
        "sourceFreshness": {
            "heating": {"status": "OK"}, "priority": {"status": "OK"},
            "priorityConsistentWithHeating": True,
        },
        "policy": {
            "maxStep_C": 0.5,
            "plannerGrantRequiredForStartAndAdvance": True,
            "intentionalGridImportAllowed": False,
        },
        "rooms": [{
            "key": "woonkamer", "displayName": "Woonkamer",
            "preheatScope": True, "group": "living_area",
            "opportunityId": opportunity,
            "heatingEligibility": {"state": "PREHEAT_READY_FOR_GRANT"},
            "planner": {"domainGrant": grant, "priorityReason": "HEATING_WINDOW_CLOSES_FIRST"},
            "progression": {
                "state": state, "reason": "SHADOW_STEP_STARTED",
                "activeStepTarget_C": target, "physicalWritePerformed": False,
            },
        }],
    }


def build(h=None, p=None, previous=None, now=NOW):
    return m.build_gate(h or heating(), p or progression(), previous, generated_at=now)


def room(out):
    return out["rooms"][0]


def test_valid_active_step_is_hypothetical_set_only():
    out = build()
    r = room(out)
    assert out["schema"] == "EMS_HEATING_CONTROL_GATE_SHADOW_V0.5"
    assert out["controlWrites"] is False
    assert out["physicalWriteAllowed"] is False
    assert r["command"]["action"] == "WOULD_SET_TEMP"
    assert r["command"]["target_C"] == 17.5
    assert r["command"]["physicalWrite"] is False
    assert r["shadowOwnership"]["wouldOwnOverride"] is True
    assert r["shadowOwnership"]["physicalOwnershipProven"] is False


def test_same_step_is_idempotent_keep():
    first = build()
    second = build(previous=first, now=NOW + timedelta(seconds=30))
    assert room(second)["command"]["action"] == "WOULD_KEEP_TEMP"


def test_loss_of_grant_resets_only_previous_shadow_owner():
    first = build()
    out = build(
        p=progression(grant="HOLD", state="STEP_HOLD_NO_GRANT"),
        previous=first,
        now=NOW + timedelta(seconds=30),
    )
    assert room(out)["command"]["action"] == "WOULD_RESET_TO_SCHEDULE"
    assert room(out)["shadowOwnership"]["simulatedRollback"] is True
    assert room(out)["shadowOwnership"]["wouldOwnOverride"] is False


def test_loss_of_grant_without_previous_owner_holds():
    out = build(p=progression(grant="HOLD", state="WAITING_FOR_GRANT", target=None))
    assert room(out)["command"]["action"] == "HOLD"


def test_future_target_ceiling_is_hard():
    first = build()
    out = build(p=progression(target=19.5), previous=first, now=NOW + timedelta(seconds=30))
    assert room(out)["checks"]["targetWithinFuture"] is False
    assert room(out)["command"]["reason"] == "TARGET_EXCEEDS_HONEYWELL_FUTURE_TARGET"
    assert room(out)["command"]["action"] == "WOULD_RESET_TO_SCHEDULE"


def test_half_degree_progression_bound_is_rechecked():
    first = build()
    out = build(p=progression(target=18.5), previous=first, now=NOW + timedelta(seconds=30))
    assert room(out)["checks"]["stepBound"] is False
    assert room(out)["command"]["reason"] == "TARGET_STEP_EXCEEDS_0_5C"


def test_stale_progression_resets_previous_shadow_owner():
    first = build()
    out = build(p=progression(generated="2026-10-04T09:57:00Z"), previous=first)
    assert out["sourceFreshness"]["progression"]["status"] == "STALE"
    assert room(out)["command"]["action"] == "WOULD_RESET_TO_SCHEDULE"
    assert room(out)["command"]["reason"] == "SOURCE_NOT_FRESH"


def test_progression_cannot_pre_date_heating():
    first = build()
    out = build(
        h=heating(generated="2026-10-04T09:59:40Z"),
        p=progression(generated="2026-10-04T09:59:30Z"),
        previous=first,
    )
    assert out["sourceFreshness"]["progressionConsistentWithHeating"] is False
    assert room(out)["command"]["reason"] == "PROGRESSION_PRE_DATES_HEATING"


def test_opportunity_change_requires_reset_before_new_command():
    first = build()
    h = heating()
    h["rooms"][0]["baseline"]["changeAt"] = "2026-10-05T07:00:00+02:00"
    h["rooms"][0]["baseline"]["targetTemperature_C"] = 18.5
    out = build(
        h=h,
        p=progression(
            opportunity="woonkamer|2026-10-05T07:00:00+02:00|18.500",
            target=17.5,
        ),
        previous=first,
        now=NOW + timedelta(seconds=30),
    )
    assert room(out)["command"]["action"] == "WOULD_RESET_TO_SCHEDULE"
    assert room(out)["command"]["reason"] == "OPPORTUNITY_CHANGED_BEFORE_NEW_COMMAND"


def test_fail_closed_output_never_claims_physical_ownership():
    first = build()
    out = m.build_fail_closed(
        first,
        reason="SOURCE_OR_CONTRACT_ERROR_FileNotFoundError",
        generated_at=NOW + timedelta(seconds=30),
    )
    r = room(out)
    assert r["command"]["action"] == "WOULD_RESET_TO_SCHEDULE"
    assert r["command"]["physicalWrite"] is False
    assert r["shadowOwnership"]["physicalOwnershipProven"] is False


def test_deploy_contract_is_shadow_only():
    installer = INSTALLER.read_text()
    assert 'physicalWriteAllowed") is False' in installer
    assert 'cmd.get("physicalWrite") is False' in installer
    assert "ReadWritePaths=/home/jeroen/ems/data" in SERVICE.read_text()
    assert "OnCalendar=*-*-* *:*:30" in TIMER.read_text()

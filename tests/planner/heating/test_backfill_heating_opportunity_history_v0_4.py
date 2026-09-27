import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parents[3] / "deploy/migrations/backfill_heating_preheat_opportunity_history_v0_4.py"
spec = importlib.util.spec_from_file_location("heating_opportunity_backfill", MODULE)
m = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(m)

NOW = datetime(2026, 9, 27, 17, 54, tzinfo=timezone.utc)


def schedule():
    days = []
    for name in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        days.append({
            "day_of_week": name,
            "switchpoints": [
                {"time_of_day": "00:00:00", "heat_setpoint": 15.5},
                {"time_of_day": "18:30:00", "heat_setpoint": 20.0},
                {"time_of_day": "22:00:00", "heat_setpoint": 15.5},
            ],
        })
    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "mode": "READ_ONLY",
        "zones": [{
            "key": "woonkamer",
            "scheduleStatus": "OK",
            "weeklySchedule": days,
        }],
    }


def progression(history=None):
    return {
        "schema": "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4",
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "baselineAuthority": "HONEYWELL",
        "policy": {"opportunityHistoryRetentionHours": 48},
        "rooms": [{
            "key": "woonkamer",
            "preheatScope": True,
            "opportunityHistory": list(history or []),
        }],
    }


def test_backfill_recovers_already_passed_honeywell_up_window():
    out, added = m.backfill(schedule(), progression(), now=NOW)
    room = out["rooms"][0]

    sunday = next(
        item for item in room["opportunityHistory"]
        if item["closesAt"] == "2026-09-27T18:30:00+02:00"
    )
    assert sunday["opensAt"] == "2026-09-27T15:30:00+02:00"
    assert sunday["target_C"] == 20.0
    assert sunday["opportunityId"] == (
        "woonkamer|2026-09-27T18:30:00+02:00|20.000"
    )
    assert added >= 1


def test_backfill_is_idempotent_for_same_schedule_window():
    first, _ = m.backfill(schedule(), progression(), now=NOW)
    second, added = m.backfill(schedule(), first, now=NOW)

    assert added == 0
    assert second["rooms"][0]["opportunityHistory"] == first["rooms"][0]["opportunityHistory"]


def test_backfill_never_creates_window_for_down_transition():
    out, _ = m.backfill(schedule(), progression(), now=NOW)
    closes = {item["closesAt"] for item in out["rooms"][0]["opportunityHistory"]}

    assert "2026-09-26T22:00:00+02:00" not in closes


def test_backfill_refuses_write_capable_progression():
    source = progression()
    source["physicalWriteAllowed"] = True

    try:
        m.backfill(schedule(), source, now=NOW)
    except m.BackfillError:
        pass
    else:
        raise AssertionError("write-capable progression must fail closed")

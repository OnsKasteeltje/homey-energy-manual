#!/usr/bin/env python3
import importlib.util
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/history/archive_semantic_events.py"


def load_module():
    spec = importlib.util.spec_from_file_location("semantic_event_history_contract", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def fixtures(root, *, changed=False):
    energy = {
        "meta": {
            "source_sample_at": (
                "2026-10-04T10:01:00Z" if changed else "2026-10-04T10:00:00Z"
            ),
            "generated_at": (
                "2026-10-04T10:01:01Z" if changed else "2026-10-04T10:00:01Z"
            ),
        },
        "tesla": {
            "connected": changed,
            "charging": changed,
        },
        "hot_water": {
            "mode": True if changed else False,
        },
    }
    command = {
        "requestId": "req-2" if changed else "req-1",
        "requestedAt": (
            "2026-10-04T10:01:10Z" if changed else "2026-10-04T10:00:10Z"
        ),
        "active": changed,
        "deadline": "2026-10-04T18:00:00+02:00",
        "currentSoc": 40,
        "targetSoc": 80,
        "goalKWh": 24.8,
        "maxA": 11,
    }
    deadline = {
        "schema": "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2",
        "generatedAt": (
            "2026-10-04T10:01:20Z" if changed else "2026-10-04T10:00:20Z"
        ),
        "requestId": "req-2" if changed else "req-1",
        "active": changed,
        "status": "TRACKING" if changed else "INACTIVE",
        "remainingKWh": 24.8 if changed else 0.0,
        "deadlineAt": "2026-10-04T16:00:00Z",
    }
    priority = {
        "schema": "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1",
        "generatedAt": (
            "2026-10-04T10:01:30Z" if changed else "2026-10-04T10:00:30Z"
        ),
        "decision": {
            "priorityOwner": "EV" if changed else "HEATING",
            "heatingShadowGrant": "HOLD" if changed else "SHADOW_GRANT",
            "evRole": "MUST" if changed else "RESIDUAL_OPPORTUNITY",
            "reason": "EV_DEADLINE_MUST" if changed else "HEATING_WINDOW_CLOSES_FIRST",
            "physicalWriteAllowed": False,
        },
    }
    progression = {
        "schema": "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4",
        "generatedAt": (
            "2026-10-04T10:01:40Z" if changed else "2026-10-04T10:00:40Z"
        ),
        "rooms": [{
            "key": "serre",
            "heatingEligibility": {
                "state": "PREHEAT_READY_FOR_GRANT",
                "reason": "AWAITING_CENTRAL_PV_PRIORITY",
            },
            "planner": {
                "domainGrant": "HOLD" if changed else "SHADOW_GRANT",
                "priorityReason": "EV_DEADLINE_MUST" if changed else "HEATING_WINDOW_CLOSES_FIRST",
            },
            "progression": {
                "state": "STEP_WAIT" if changed else "STEP_STARTED",
                "reason": "WAITING_FOR_TARGET" if changed else "SHADOW_STEP_STARTED",
                "activeStepTarget_C": 20.5,
                "activeStepReached": False,
                "physicalWritePerformed": False,
            },
        }],
    }

    write(root / "energy-state-v2.json", energy)
    write(root / "tesla-deadline-command.json", command)
    write(root / "ev-deadline-shadow-state.json", deadline)
    write(root / "flex-priority-shadow-v0.1.json", priority)
    write(root / "heating-preheat-progression-shadow-v0.4.json", progression)


def main():
    module = load_module()

    source_text = SOURCE.read_text(encoding="utf-8")
    for forbidden in ("Homey.", "requests", "urlopen", "http://", "https://"):
        assert forbidden not in source_text, forbidden

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        db = root / "ems-history.sqlite"

        module.ENERGY_STATE_FILE = root / "energy-state-v2.json"
        module.EV_DEADLINE_COMMAND_FILE = root / "tesla-deadline-command.json"
        module.EV_DEADLINE_STATE_FILE = root / "ev-deadline-shadow-state.json"
        module.FLEX_PRIORITY_FILE = root / "flex-priority-shadow-v0.1.json"
        module.HEATING_PROGRESSION_FILE = root / "heating-preheat-progression-shadow-v0.4.json"

        fixtures(root, changed=False)
        baseline = module.archive(
            db_path=db,
            now=datetime(2026, 10, 4, 10, 0, 50, tzinfo=timezone.utc),
        )
        assert baseline["historicalBackfill"] is False
        assert baseline["baselineCount"] == 7, baseline
        assert baseline["insertedEventCount"] == 0, baseline
        with sqlite3.connect(db) as con:
            ww_baseline = con.execute(
                """
                SELECT value_json FROM semantic_event_state
                WHERE state_key='warm_water.source_mode'
                """
            ).fetchone()[0]
        assert json.loads(ww_baseline) == "CV", ww_baseline

        fixtures(root, changed=True)
        changed = module.archive(
            db_path=db,
            now=datetime(2026, 10, 4, 10, 1, 50, tzinfo=timezone.utc),
        )
        assert changed["insertedEventCount"] == 7, changed
        expected = {
            "EV_CONNECTED",
            "EV_CHARGING_STARTED",
            "WW_SOURCE_CHANGED",
            "EV_DEADLINE_SET",
            "EV_DEADLINE_TRACKING",
            "FLEX_PRIORITY_CHANGED",
            "HEATING_SHADOW_STATE_CHANGED",
        }
        assert set(changed["insertedEventTypes"]) == expected, changed

        duplicate = module.archive(
            db_path=db,
            now=datetime(2026, 10, 4, 10, 2, 50, tzinfo=timezone.utc),
        )
        assert duplicate["insertedEventCount"] == 0, duplicate
        assert duplicate["unchangedCount"] == 7, duplicate

        with sqlite3.connect(db) as con:
            rows = con.execute(
                """
                SELECT event_type,domain,provenance_class,before_json,after_json
                FROM semantic_events
                ORDER BY ts_utc,event_type
                """
            ).fetchall()
            commissioned = con.execute(
                """
                SELECT value_text FROM semantic_event_meta
                WHERE key='commissioned_at_utc'
                """
            ).fetchone()[0]

        assert len(rows) == 7
        assert commissioned == "2026-10-04T10:00:50Z"

        by_type = {row[0]: row for row in rows}
        assert by_type["EV_DEADLINE_SET"][2] == "USER_INTENT_COMMAND"
        assert by_type["FLEX_PRIORITY_CHANGED"][2] == "SHADOW_DECISION"
        assert by_type["HEATING_SHADOW_STATE_CHANGED"][2] == "SHADOW_DECISION"

        deadline_after = json.loads(by_type["EV_DEADLINE_SET"][4])
        assert deadline_after["requestId"] == "req-2"
        assert deadline_after["active"] is True

        ww_before = json.loads(by_type["WW_SOURCE_CHANGED"][3])
        ww_after = json.loads(by_type["WW_SOURCE_CHANGED"][4])
        assert ww_before == "CV"
        assert ww_after == "BOILER"

        # Upgrade compatibility: a pre-normalization boolean baseline must be
        # silently normalized in-place when the physical source did not change.
        compat_db = root / "compat.sqlite"
        fixtures(root, changed=False)
        module.archive(
            db_path=compat_db,
            now=datetime(2026, 10, 4, 9, 59, 50, tzinfo=timezone.utc),
        )
        with sqlite3.connect(compat_db) as con:
            con.execute(
                """
                UPDATE semantic_event_state
                SET value_json='false'
                WHERE state_key='warm_water.source_mode'
                """
            )
            con.commit()
        compatible = module.archive(
            db_path=compat_db,
            now=datetime(2026, 10, 4, 10, 0, 50, tzinfo=timezone.utc),
        )
        assert compatible["insertedEventCount"] == 0, compatible
        with sqlite3.connect(compat_db) as con:
            value = con.execute(
                """
                SELECT value_json FROM semantic_event_state
                WHERE state_key='warm_water.source_mode'
                """
            ).fetchone()[0]
            event_count = con.execute(
                """
                SELECT COUNT(*) FROM semantic_events
                WHERE event_type='WW_SOURCE_CHANGED'
                """
            ).fetchone()[0]
        assert json.loads(value) == "CV"
        assert event_count == 0

    print("PASS: semantic event history contract")


if __name__ == "__main__":
    main()

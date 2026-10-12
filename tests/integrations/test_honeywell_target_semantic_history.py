import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/history/archive_semantic_events.py"


def load_module():
    spec = importlib.util.spec_from_file_location("semantic_events_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_observations_adds_observed_honeywell_targets(tmp_path):
    module = load_module()

    for name in (
        "ENERGY_STATE_FILE",
        "EV_DEADLINE_COMMAND_FILE",
        "EV_DEADLINE_STATE_FILE",
        "FLEX_PRIORITY_FILE",
        "HEATING_PROGRESSION_FILE",
    ):
        setattr(module, name, tmp_path / f"missing-{name}.json")

    honeywell = tmp_path / "honeywell-state.json"
    honeywell.write_text(json.dumps({
        "schema": "EMS_HONEYWELL_STATE_V0.2",
        "generatedAt": "2026-10-12T11:40:00Z",
        "location": {"systemMode": "auto"},
        "zones": [
            {
                "key": "keuken",
                "targetTemperature_C": 19.0,
                "setpointMode": "temporary_override",
                "overrideUntil": "2026-10-12T16:30:00+02:00",
            },
            {
                "key": "douwe_slaapkamer",
                "targetTemperature_C": 16.0,
                "setpointMode": "permanent_override",
                "overrideUntil": None,
            },
            {
                "key": "invalid",
                "targetTemperature_C": None,
                "setpointMode": "follow_schedule",
                "overrideUntil": None,
            },
        ],
    }), encoding="utf-8")
    module.HONEYWELL_STATE_FILE = honeywell

    observations = module.build_observations(
        datetime(2026, 10, 12, 11, 41, tzinfo=timezone.utc)
    )
    by_key = {item["stateKey"]: item for item in observations}

    kitchen = by_key["heating.honeywell_target.keuken"]
    assert kitchen["domain"] == "HEATING"
    assert kitchen["subject"] == "keuken"
    assert kitchen["sourceName"] == "honeywell-state.json"
    assert kitchen["sourceAt"] == "2026-10-12T11:40:00Z"
    assert kitchen["provenanceClass"] == "OBSERVED_STATE"
    assert kitchen["value"] == {
        "targetTemperature_C": 19.0,
        "setpointMode": "temporary_override",
        "overrideUntil": "2026-10-12T16:30:00+02:00",
        "systemMode": "auto",
    }

    douwe = by_key["heating.honeywell_target.douwe_slaapkamer"]
    assert douwe["value"]["targetTemperature_C"] == 16.0
    assert douwe["value"]["setpointMode"] == "permanent_override"
    assert "heating.honeywell_target.invalid" not in by_key


def test_honeywell_target_change_is_sparse_semantic_event(tmp_path):
    module = load_module()
    db = tmp_path / "history.sqlite"

    baseline = {
        "stateKey": "heating.honeywell_target.keuken",
        "domain": "HEATING",
        "subject": "keuken",
        "value": {
            "targetTemperature_C": 18.0,
            "setpointMode": "follow_schedule",
            "overrideUntil": None,
            "systemMode": "auto",
        },
        "sourceName": "honeywell-state.json",
        "sourceAt": "2026-10-12T10:00:00Z",
        "provenanceClass": "OBSERVED_STATE",
    }
    changed = {
        **baseline,
        "value": {
            "targetTemperature_C": 19.0,
            "setpointMode": "temporary_override",
            "overrideUntil": "2026-10-12T16:30:00+02:00",
            "systemMode": "auto",
        },
        "sourceAt": "2026-10-12T10:05:00Z",
    }

    first = module.archive(
        [baseline],
        db_path=db,
        now=datetime(2026, 10, 12, 10, 1, tzinfo=timezone.utc),
    )
    second = module.archive(
        [changed],
        db_path=db,
        now=datetime(2026, 10, 12, 10, 6, tzinfo=timezone.utc),
    )

    assert first["baselineCount"] == 1
    assert first["insertedEventCount"] == 0
    assert second["insertedEventCount"] == 1
    assert second["insertedEventTypes"] == ["HEATING_HONEYWELL_TARGET_CHANGED"]

    with sqlite3.connect(db) as con:
        row = con.execute(
            """
            SELECT event_type,ts_utc,before_json,after_json
            FROM semantic_events
            WHERE state_key='heating.honeywell_target.keuken'
            """
        ).fetchone()

    assert row[0] == "HEATING_HONEYWELL_TARGET_CHANGED"
    assert row[1] == "2026-10-12T10:05:00Z"
    assert json.loads(row[2])["targetTemperature_C"] == 18.0
    assert json.loads(row[3])["targetTemperature_C"] == 19.0

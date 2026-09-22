import importlib.util
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[3]
    / "services/pi/planner/heating/build_thermal_learning_episodes.py"
)

spec = importlib.util.spec_from_file_location("thermal_learning", MODULE)
m = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(m)


def schedule():
    """Small deterministic Honeywell weekly schedule for V0.1 tests."""
    return {
        "schema": "EMS_HONEYWELL_SCHEDULE_V0.2",
        "zones": [
            {
                "key": "keuken",
                "displayName": "Keuken",
                "scheduleStatus": "OK",
                "weeklySchedule": [
                    {
                        "day_of_week": "monday",
                        "switchpoints": [
                            {
                                "time_of_day": "06:30:00",
                                "heat_setpoint": 18.0,
                            },
                            {
                                "time_of_day": "07:30:00",
                                "heat_setpoint": 18.5,
                            },
                            {
                                # Equal target: deliberately NOT an UP.
                                "time_of_day": "16:30:00",
                                "heat_setpoint": 18.5,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                    {
                        "day_of_week": "tuesday",
                        "switchpoints": [
                            {
                                "time_of_day": "06:30:00",
                                "heat_setpoint": 18.0,
                            },
                            {
                                "time_of_day": "07:30:00",
                                "heat_setpoint": 18.5,
                            },
                            {
                                "time_of_day": "16:30:00",
                                "heat_setpoint": 18.5,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                    {
                        "day_of_week": "wednesday",
                        "switchpoints": [
                            {
                                "time_of_day": "06:30:00",
                                "heat_setpoint": 18.0,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                    {
                        "day_of_week": "thursday",
                        "switchpoints": [
                            {
                                "time_of_day": "06:30:00",
                                "heat_setpoint": 18.0,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                    {
                        "day_of_week": "friday",
                        "switchpoints": [
                            {
                                "time_of_day": "06:30:00",
                                "heat_setpoint": 18.0,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                    {
                        "day_of_week": "saturday",
                        "switchpoints": [
                            {
                                "time_of_day": "08:00:00",
                                "heat_setpoint": 18.5,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                    {
                        "day_of_week": "sunday",
                        "switchpoints": [
                            {
                                "time_of_day": "08:00:00",
                                "heat_setpoint": 18.5,
                            },
                            {
                                "time_of_day": "19:30:00",
                                "heat_setpoint": 17.5,
                            },
                        ],
                    },
                ],
            },
            {
                # Outside V0.1 scope: must never create an episode.
                "key": "master_bedroom",
                "displayName": "Master bedroom",
                "scheduleStatus": "OK",
                "weeklySchedule": [],
            },
        ],
    }


def empty_db():
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE devices (
          id INTEGER PRIMARY KEY,
          device_key TEXT
        );

        CREATE TABLE metrics (
          id INTEGER PRIMARY KEY,
          metric_key TEXT,
          unit TEXT
        );

        CREATE TABLE measurements_15m (
          slot_start_utc TEXT,
          device_id INTEGER,
          metric_id INTEGER,
          value_avg REAL,
          value_min REAL,
          value_max REAL,
          sample_count INTEGER,
          energy_wh REAL,
          quality TEXT
        );
        """
    )
    return con


def test_counter_delta():
    s = [{"avg": 10.0}, {"avg": 10.2}, {"avg": 10.5}]
    assert m._counter_delta(s) == 0.5


def test_counter_reset_fails_closed():
    s = [{"avg": 10.0}, {"avg": 9.0}]
    assert m._counter_delta(s) is None


def test_energy_sum():
    s = [
        {"energyWh": 10.0},
        {"energyWh": 20.0},
        {"energyWh": None},
    ]
    assert m._energy_sum(s) == 30.0


def test_room_scope():
    assert m._room_key("honeywell_woonkamer") == "woonkamer"
    assert m._room_key("honeywell_master_bedroom") is None


def test_living_area_group():
    assert m._group_for("woonkamer") == "living_area"
    assert m._group_for("eetkamer") == "living_area"
    assert m._group_for("keuken") is None


def test_schedule_is_transition_authority():
    transitions = m._scheduled_up_transitions(
        schedule(),
        start=datetime(
            2026, 9, 21, 0, 0, tzinfo=timezone.utc
        ),
        end=datetime(
            2026, 9, 21, 18, 0, tzinfo=timezone.utc
        ),
    )

    assert len(transitions) == 2

    assert transitions[0]["room"] == "keuken"
    assert transitions[0]["baselineBefore_C"] == 17.5
    assert transitions[0]["baselineAfter_C"] == 18.0
    assert transitions[0]["quality"] == "scheduled"

    assert transitions[1]["baselineBefore_C"] == 18.0
    assert transitions[1]["baselineAfter_C"] == 18.5


def test_equal_target_does_not_create_episode():
    transitions = m._scheduled_up_transitions(
        schedule(),
        start=datetime(
            2026, 9, 21, 12, 0, tzinfo=timezone.utc
        ),
        end=datetime(
            2026, 9, 21, 17, 0, tzinfo=timezone.utc
        ),
    )

    # Monday 16:30 Europe/Amsterdam is 14:30 UTC.
    # It is 18.5 -> 18.5 and therefore not an UP transition.
    assert transitions == []


def test_previous_day_baseline_crosses_day_boundary():
    transitions = m._scheduled_up_transitions(
        schedule(),
        start=datetime(
            2026, 9, 22, 3, 0, tzinfo=timezone.utc
        ),
        end=datetime(
            2026, 9, 22, 5, 0, tzinfo=timezone.utc
        ),
    )

    assert len(transitions) == 1
    assert transitions[0]["baselineBefore_C"] == 17.5
    assert transitions[0]["baselineAfter_C"] == 18.0


def test_shadow_contract_with_schedule_authority():
    con = empty_db()

    try:
        result = m.build_episodes(
            con,
            schedule=schedule(),
            start=datetime(
                2026, 9, 21, 4, 0, tzinfo=timezone.utc
            ),
            end=datetime(
                2026, 9, 21, 5, 0, tzinfo=timezone.utc
            ),
            generated_at=datetime(
                2026, 9, 22, 20, 0, tzinfo=timezone.utc
            ),
        )
    finally:
        con.close()

    assert (
        result["schema"]
        == "EMS_HEATING_THERMAL_LEARNING_EPISODES_V0.1"
    )
    assert result["mode"] == "READ_ONLY"
    assert result["controlMode"] == "SHADOW"
    assert result["baselineAuthority"] == "HONEYWELL"

    assert (
        result["policy"]["intentionalGridImportAllowed"]
        is False
    )
    assert result["policy"]["physicalWritesAllowed"] is False
    assert result["policy"]["assessmentMode"] == "EVIDENCE_ONLY"

    # 04:00-05:00 UTC is 06:00-07:00 CEST.
    # The canonical Honeywell weekly schedule contains the planned
    # kitchen UP transition at 06:30 CEST: 17.5 -> 18.0 C.
    assert result["episodeCount"] == 1

    episode = result["episodes"][0]

    assert episode["room"] == "keuken"
    assert episode["transition"]["baselineBefore_C"] == 17.5
    assert episode["transition"]["baselineAfter_C"] == 18.0
    assert episode["transition"]["direction"] == "UP"
    assert episode["transition"]["sourceQuality"] == "scheduled"

    # Empty history is allowed for construction of a SHADOW evidence
    # episode, but it must never be mistaken for assessed evidence.
    assert episode["assessment"]["status"] == "UNASSESSED"
    assert (
        episode["assessment"]["reason"]
        == "RAW_EPISODE_EVIDENCE_ONLY"
    )
    assert episode["assessment"]["usefulThermalBuffering"] is None
    assert episode["assessment"]["avoidedLaterHeating"] is None
    assert episode["assessment"]["incrementalGridImport_kWh"] is None


def test_wrong_schedule_schema_fails_closed():
    bad = schedule()
    bad["schema"] = "WRONG"

    try:
        m._scheduled_up_transitions(
            bad,
            start=datetime(
                2026, 9, 21, 0, 0, tzinfo=timezone.utc
            ),
            end=datetime(
                2026, 9, 21, 23, 0, tzinfo=timezone.utc
            ),
        )
    except m.EpisodeError:
        pass
    else:
        raise AssertionError(
            "invalid Honeywell schedule schema must fail closed"
        )

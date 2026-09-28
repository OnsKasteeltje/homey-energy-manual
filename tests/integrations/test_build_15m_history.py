import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "services/pi/history/build_15m_history.py"
)
spec = importlib.util.spec_from_file_location(
    "build_15m_history",
    MODULE_PATH,
)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)

UTC = timezone.utc


def test_one_minute_samples_do_not_each_count_as_five_minutes():
    start = datetime(2026, 9, 20, 2, 30, tzinfo=UTC)
    samples = [
        (
            start + timedelta(minutes=i),
            5600.0,
            300,
        )
        for i in range(15)
    ]

    result = history.aggregate_power_series(
        samples,
        now=start + timedelta(minutes=15),
    )
    slot = result[start]

    assert slot["sample_count"] == 15
    assert slot["coverage_seconds"] == 900
    assert slot["quality"] == "complete"
    assert abs(slot["value_avg"] - 5600.0) < 1e-9
    assert abs(slot["energy_wh"] - 1400.0) < 1e-6


def test_source_resolution_caps_gap_instead_of_filling_it():
    start = datetime(2026, 9, 20, 2, 30, tzinfo=UTC)
    samples = [
        (start, 1000.0, 300),
        (start + timedelta(minutes=10), 1000.0, 300),
    ]

    result = history.aggregate_power_series(
        samples,
        now=start + timedelta(minutes=15),
    )
    slot = result[start]

    assert slot["coverage_seconds"] == 600
    assert slot["quality"] == "partial"
    assert abs(slot["energy_wh"] - (1000 * 600 / 3600)) < 1e-6


def test_power_interval_is_split_at_quarter_hour_boundary():
    start = datetime(2026, 9, 20, 2, 14, tzinfo=UTC)
    samples = [
        (start, 1000.0, 300),
        (start + timedelta(minutes=5), 1000.0, 300),
    ]

    result = history.aggregate_power_series(
        samples,
        now=start + timedelta(minutes=10),
    )

    first = result[datetime(2026, 9, 20, 2, 0, tzinfo=UTC)]
    second = result[datetime(2026, 9, 20, 2, 15, tzinfo=UTC)]

    assert abs(first["energy_wh"] - (1000 * 60 / 3600)) < 1e-6
    assert abs(second["energy_wh"] - (1000 * 540 / 3600)) < 1e-6


def test_latest_sample_never_projects_beyond_now():
    start = datetime(2026, 9, 20, 2, 30, tzinfo=UTC)
    samples = [(start, 3000.0, 300)]

    result = history.aggregate_power_series(
        samples,
        now=start + timedelta(seconds=60),
    )
    slot = result[start]

    assert slot["coverage_seconds"] == 60
    assert abs(slot["energy_wh"] - 50.0) < 1e-6
    assert slot["quality"] == "partial"

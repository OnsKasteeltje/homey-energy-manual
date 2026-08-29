from datetime import datetime, timedelta, timezone

from ems.models import Observation, Quality
from ems.state import CentralState


def test_missing_grid_blocks_positive_writes() -> None:
    state = CentralState()
    assert state.positive_writes_allowed() is False
    assert "GRID_POWER_MISSING" in state.snapshot().degraded_reasons


def test_good_fresh_grid_allows_baseline_state() -> None:
    state = CentralState()
    state.update_grid_power(
        Observation(
            value=250.0,
            observed_at=datetime.now(timezone.utc),
            source="test:p1",
            quality=Quality.GOOD,
            stale_after_s=30,
        )
    )
    assert state.positive_writes_allowed() is True


def test_stale_grid_blocks() -> None:
    state = CentralState()
    state.update_grid_power(
        Observation(
            value=250.0,
            observed_at=datetime.now(timezone.utc) - timedelta(seconds=60),
            source="test:p1",
            quality=Quality.GOOD,
            stale_after_s=30,
        )
    )
    assert state.positive_writes_allowed() is False
    assert "GRID_POWER_STALE" in state.snapshot().degraded_reasons

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ems.replay import replay_projection, state_from_fixture

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime.fromisoformat("2026-08-29T12:00:20+00:00")


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_good_snapshot_projection_is_deterministic() -> None:
    payload = load_fixture("core_snapshot_good.json")
    state = state_from_fixture(payload)

    first = replay_projection(state, NOW)
    second = replay_projection(state, NOW)

    assert first == second
    assert first["grid_quality"] == payload["expected"]["quality"]
    assert first["positive_writes_allowed"] is True
    assert first["pv_total_W"] == payload["expected"]["pv_total_W"]
    assert first["house_power_W"] == payload["expected"]["house_power_W"]


def test_stale_grid_fails_closed() -> None:
    payload = load_fixture("core_snapshot_stale_grid.json")
    state = state_from_fixture(payload)
    result = replay_projection(state, NOW)

    assert result["grid_quality"] == payload["expected"]["quality"]
    assert result["positive_writes_allowed"] is False
    assert payload["expected"]["block_reason"] in result["block_reasons"]

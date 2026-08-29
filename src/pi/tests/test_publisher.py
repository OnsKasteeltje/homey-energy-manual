from datetime import datetime, timedelta, timezone

import pytest

from publisher import build_payload, decide_publish

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def state(revision: int):
    return {"meta": {"state_revision": revision}, "grid": {"power_W": 1234}}


def test_revision_mismatch_blocks_publish():
    with pytest.raises(ValueError, match="REVISION_MISMATCH"):
        decide_publish(
            state(11),
            {"revision": 12},
            last_published_revision=10,
            last_publish_at=NOW - timedelta(minutes=20),
            now=NOW,
        )


def test_minimum_interval_suppresses_publish():
    decision = decide_publish(
        state(11),
        {"revision": 11},
        last_published_revision=10,
        last_publish_at=NOW - timedelta(minutes=5),
        now=NOW,
    )
    assert decision.due is False


def test_revision_change_publishes_after_gate():
    decision = decide_publish(
        state(11),
        {"revision": 11},
        last_published_revision=10,
        last_publish_at=NOW - timedelta(minutes=20),
        now=NOW,
    )
    assert decision.due is True
    assert decision.reason == "REVISION_EVENT"


def test_heartbeat_publishes_same_revision_after_gate():
    decision = decide_publish(
        state(11),
        {"revision": 11},
        last_published_revision=11,
        last_publish_at=NOW - timedelta(minutes=20),
        now=NOW,
    )
    assert decision.due is True
    assert decision.reason == "HEARTBEAT_EVENT"


def test_payload_contains_publication_metadata():
    decision = decide_publish(
        state(11),
        {"revision": 11},
        last_published_revision=10,
        last_publish_at=NOW - timedelta(minutes=20),
        now=NOW,
    )
    payload = build_payload(state(11), decision, now=NOW)
    assert payload["meta"]["state_revision"] == 11
    assert payload["meta"]["publish_reason"] == "REVISION_EVENT"
    assert payload["meta"]["min_publish_interval_sec"] == 900

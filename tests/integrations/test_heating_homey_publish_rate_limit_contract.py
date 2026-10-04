#!/usr/bin/env python3
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py"

spec = importlib.util.spec_from_file_location("heating_homey_publisher_rate_limit", SOURCE)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def main():
    now = datetime(2026, 10, 4, 14, 30, tzinfo=timezone.utc)

    decision, retry = m._publish_decision({}, "hcs1-a", now)
    assert decision == "PUBLISH"
    assert retry is None

    success = m._success_cache({}, {"controlRevision": "hcs1-a"}, now)
    assert success["lastPublishedRevision"] == "hcs1-a"
    assert success["rateLimitCount"] == 0
    assert success["retryNotBefore"] is None

    decision, retry = m._publish_decision(success, "hcs1-a", now + timedelta(minutes=1))
    assert decision == "SUPPRESS_UNCHANGED"
    assert retry is None

    limited = m._rate_limit_cache(success, now + timedelta(minutes=2))
    assert limited["rateLimitCount"] == 1
    retry_at = datetime.fromisoformat(limited["retryNotBefore"].replace("Z", "+00:00"))
    assert retry_at - (now + timedelta(minutes=2)) == timedelta(seconds=300)

    decision, retry = m._publish_decision(
        limited, "hcs1-b", now + timedelta(minutes=3)
    )
    assert decision == "COOLDOWN_RATE_LIMIT"
    assert retry == limited["retryNotBefore"]

    decision, retry = m._publish_decision(
        limited, "hcs1-b", retry_at + timedelta(seconds=1)
    )
    assert decision == "PUBLISH"
    assert retry is None

    limited2 = m._rate_limit_cache(limited, retry_at + timedelta(seconds=1))
    assert limited2["rateLimitCount"] == 2
    retry2 = datetime.fromisoformat(limited2["retryNotBefore"].replace("Z", "+00:00"))
    assert retry2 - (retry_at + timedelta(seconds=1)) == timedelta(seconds=900)

    recovered = m._success_cache(
        limited2,
        {"controlRevision": "hcs1-b"},
        retry2 + timedelta(seconds=1),
    )
    assert recovered["lastPublishedRevision"] == "hcs1-b"
    assert recovered["rateLimitCount"] == 0
    assert recovered["retryNotBefore"] is None

    print("PASS: Heating Homey publisher suppresses unchanged writes and backs off 429")


if __name__ == "__main__":
    main()

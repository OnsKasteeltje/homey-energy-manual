from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

MIN_PUBLISH_INTERVAL = timedelta(minutes=15)
PUBLISHER_VERSION = "PI_PUBLISHER_REPLAY_V0.1"


@dataclass(frozen=True)
class PublishDecision:
    due: bool
    reason: str | None
    revision: int


def _revision(payload: dict[str, Any]) -> int | None:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    for candidate in (
        meta.get("state_revision"),
        payload.get("state_revision"),
        payload.get("revision"),
        payload.get("sourceRevision"),
    ):
        try:
            if candidate is not None:
                return int(candidate)
        except (TypeError, ValueError):
            pass
    return None


def decide_publish(
    public_state: dict[str, Any],
    authoritative_state: dict[str, Any],
    *,
    last_published_revision: int | None,
    last_publish_at: datetime | None,
    now: datetime,
) -> PublishDecision:
    public_revision = _revision(public_state)
    if public_revision is None:
        raise ValueError("PUBLIC_STATE_REVISION_MISSING")

    state_revision = _revision(authoritative_state)
    if state_revision is not None and state_revision != public_revision:
        raise ValueError(
            f"REVISION_MISMATCH public={public_revision} state={state_revision}"
        )

    now = now.astimezone(timezone.utc)
    age = None if last_publish_at is None else now - last_publish_at.astimezone(timezone.utc)
    if age is not None and age < MIN_PUBLISH_INTERVAL:
        return PublishDecision(False, None, public_revision)

    revision_due = last_published_revision != public_revision
    heartbeat_due = last_publish_at is None or age is None or age >= MIN_PUBLISH_INTERVAL
    if revision_due:
        return PublishDecision(True, "REVISION_EVENT", public_revision)
    if heartbeat_due:
        return PublishDecision(True, "HEARTBEAT_EVENT", public_revision)
    return PublishDecision(False, None, public_revision)


def build_payload(
    public_state: dict[str, Any], decision: PublishDecision, *, now: datetime
) -> dict[str, Any]:
    if not decision.due or decision.reason is None:
        raise ValueError("PUBLISH_NOT_DUE")

    payload = deepcopy(public_state)
    payload.setdefault("meta", {})
    stamp = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["meta"].update(
        {
            "generated_at": stamp,
            "heartbeat_at": stamp,
            "publisher_version": PUBLISHER_VERSION,
            "state_revision": decision.revision,
            "publish_reason": decision.reason,
            "min_publish_interval_sec": 900,
        }
    )
    return payload

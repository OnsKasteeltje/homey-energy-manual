"""Authenticated LAN ingest for Homey Core energy-state snapshots.

Runtime direction is deliberately one-way for state transport:
Homey Core -> Pi status API -> local runtime file + local history -> Pi planners.

This module performs no Homey polling, no GitHub calls and no device writes.
"""

import hmac
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

from history_archive import archive_state_history

ENERGY_STATE_FILE = "/home/jeroen/ems/data/energy-state-v2.json"
TOKEN_ENV = "EMS_STATE_INGEST_TOKEN"
MAX_BODY_BYTES = 256 * 1024
MAX_SOURCE_SAMPLE_AGE_SECONDS = 20 * 60
MAX_FUTURE_SKEW_SECONDS = 60
EXPECTED_SCHEMA_VERSION = "2.12"
PUBLISHER_PREFIX = "EM2_CORE_STATE_"
REQUIRED_OBJECTS = ("meta", "grid", "tesla", "hot_water")


def _parse_utc(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _load_current():
    try:
        with open(ENERGY_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        # A broken current file must never authorize relaxed replay handling.
        return None


def _validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("STATE_NOT_OBJECT")

    for key in REQUIRED_OBJECTS:
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"STATE_MISSING_{key.upper()}")

    meta = payload["meta"]
    if meta.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("STATE_SCHEMA_VERSION")

    publisher = meta.get("publisher_version")
    if not isinstance(publisher, str) or not publisher.startswith(PUBLISHER_PREFIX):
        raise ValueError("STATE_PUBLISHER_VERSION")

    revision = meta.get("state_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ValueError("STATE_REVISION")

    generated = _parse_utc(meta.get("generated_at"))
    heartbeat = _parse_utc(meta.get("heartbeat_at"))
    sample = _parse_utc(meta.get("source_sample_at"))
    if generated is None or heartbeat is None or sample is None:
        raise ValueError("STATE_TIMESTAMP")

    now = datetime.now(timezone.utc)
    sample_age = (now - sample).total_seconds()
    if sample_age < -MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("STATE_SAMPLE_FROM_FUTURE")
    if sample_age > MAX_SOURCE_SAMPLE_AGE_SECONDS:
        raise ValueError("STATE_SAMPLE_STALE")

    if generated < sample:
        raise ValueError("STATE_GENERATED_BEFORE_SAMPLE")
    if heartbeat < sample:
        raise ValueError("STATE_HEARTBEAT_BEFORE_SAMPLE")

    current = _load_current()
    if current:
        current_meta = current.get("meta") or {}
        current_revision = current_meta.get("state_revision")
        current_heartbeat = _parse_utc(current_meta.get("heartbeat_at"))

        if isinstance(current_revision, int):
            if revision < current_revision:
                raise ValueError("STATE_REVISION_REPLAY")
            if revision == current_revision:
                if current_heartbeat is None or heartbeat <= current_heartbeat:
                    raise ValueError("STATE_HEARTBEAT_REPLAY")

    return {
        "revision": revision,
        "generated_at": meta.get("generated_at"),
        "heartbeat_at": meta.get("heartbeat_at"),
        "source_sample_at": meta.get("source_sample_at"),
        "publisher_version": publisher,
    }


def _atomic_write(payload):
    directory = os.path.dirname(ENERGY_STATE_FILE)
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=".energy-state-v2.", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, ENERGY_STATE_FILE)
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def _authorized(handler):
    expected = os.environ.get(TOKEN_ENV, "")
    if not expected:
        raise RuntimeError("STATE_INGEST_TOKEN_NOT_CONFIGURED")
    supplied = handler.headers.get("Authorization", "")
    prefix = "Bearer "
    if not supplied.startswith(prefix):
        return False
    return hmac.compare_digest(supplied[len(prefix):], expected)


def handle_state_ingest(handler, send_json):
    """Handle exactly one authenticated POST /state/energy request."""
    try:
        if not _authorized(handler):
            send_json(handler, 401, {
                "status": "REJECTED",
                "reason": "UNAUTHORIZED",
                "stateWritten": False,
            })
            return
    except RuntimeError as exc:
        send_json(handler, 503, {
            "status": "FAIL_CLOSED",
            "reason": str(exc),
            "stateWritten": False,
        })
        return

    raw_length = handler.headers.get("Content-Length")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        send_json(handler, 411, {
            "status": "REJECTED",
            "reason": "CONTENT_LENGTH_REQUIRED",
            "stateWritten": False,
        })
        return

    if length <= 0 or length > MAX_BODY_BYTES:
        send_json(handler, 413, {
            "status": "REJECTED",
            "reason": "BODY_SIZE",
            "stateWritten": False,
        })
        return

    try:
        body = handler.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        send_json(handler, 400, {
            "status": "REJECTED",
            "reason": "INVALID_JSON",
            "stateWritten": False,
        })
        return

    try:
        accepted = _validate(payload)
        _atomic_write(payload)
    except ValueError as exc:
        send_json(handler, 409, {
            "status": "REJECTED",
            "reason": str(exc),
            "stateWritten": False,
        })
        return
    except Exception:
        send_json(handler, 500, {
            "status": "FAIL_CLOSED",
            "reason": "STATE_WRITE_FAILED",
            "stateWritten": False,
        })
        return

    history = {
        "archived": False,
        "inserted": 0,
        "skipped": 0,
    }
    try:
        history = archive_state_history(payload)
    except Exception as exc:
        # Historical persistence is deliberately decoupled from the live state
        # acceptance path. A local archive failure must be visible in the journal
        # but must not make a fresh, valid Homey state unavailable to the planner.
        print(f"WARN: state history archive failed: {exc}", file=sys.stderr)

    send_json(handler, 202, {
        "status": "ACCEPTED",
        "stateWritten": True,
        "historyArchived": history.get("archived") is True,
        "historyInserted": history.get("inserted", 0),
        "historySkipped": history.get("skipped", 0),
        **accepted,
    })

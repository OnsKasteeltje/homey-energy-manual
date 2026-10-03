"""Authenticated LAN ingest for Homey EV control observability.

Direction is one-way and control-neutral:
Homey EV observability -> Pi status API -> local SQLite evidence.

This module performs no Homey calls, no GitHub calls and no device writes.
"""

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HISTORY_DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
TOKEN_ENV = "EMS_STATE_INGEST_TOKEN"
SCHEMA = "EMS_HOMEY_EV_CONTROL_EVIDENCE_V0.1"
MAX_BODY_BYTES = 96 * 1024
MAX_AGE_SECONDS = 10 * 60
MAX_FUTURE_SKEW_SECONDS = 60


def _parse_utc(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _authorized(handler):
    expected = os.environ.get(TOKEN_ENV, "")
    if not expected:
        raise RuntimeError("STATE_INGEST_TOKEN_NOT_CONFIGURED")
    supplied = handler.headers.get("Authorization", "")
    prefix = "Bearer "
    if not supplied.startswith(prefix):
        return False
    return hmac.compare_digest(supplied[len(prefix):], expected)


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("EV_CONTROL_NOT_OBJECT")
    if payload.get("schema") != SCHEMA:
        raise ValueError("EV_CONTROL_SCHEMA")
    if payload.get("readOnly") is not True:
        raise ValueError("EV_CONTROL_READ_ONLY")
    if payload.get("observabilityOnly") is not True:
        raise ValueError("EV_CONTROL_OBSERVABILITY_ONLY")
    if payload.get("controlImpact") != "NONE":
        raise ValueError("EV_CONTROL_IMPACT")

    generated = _parse_utc(payload.get("generatedAt"))
    if generated is None:
        raise ValueError("EV_CONTROL_TIMESTAMP")
    age = (datetime.now(timezone.utc) - generated).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("EV_CONTROL_FROM_FUTURE")
    if age > MAX_AGE_SECONDS:
        raise ValueError("EV_CONTROL_STALE")

    for key in ("intent", "adapter", "gate", "actuator", "deviceHealth"):
        value = payload.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError("EV_CONTROL_" + key.upper())

    if not any(isinstance(payload.get(key), dict) for key in ("gate", "actuator", "deviceHealth")):
        raise ValueError("EV_CONTROL_EVIDENCE_EMPTY")

    return generated


def _ensure_schema(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ev_control_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_hash TEXT NOT NULL UNIQUE,
            ts_utc TEXT NOT NULL,
            source_revision INTEGER,
            control_revision TEXT,
            target_w REAL,
            requested_a REAL,
            phase_mode TEXT,
            gate_status TEXT,
            gate_errors_json TEXT,
            actuator_status TEXT,
            actuator_reason TEXT,
            actuator_target_a REAL,
            actuator_phase_mode TEXT,
            actuator_confirmed_mode TEXT,
            transition_stage TEXT,
            transition_failure TEXT,
            charge_state TEXT,
            device_health_status TEXT,
            device_health_reason TEXT,
            physical_write_performed INTEGER,
            raw_json TEXT NOT NULL,
            collected_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ev_control_events_time
        ON ev_control_events(ts_utc)
        """
    )


def _extract(payload):
    intent = payload.get("intent") or {}
    adapter = payload.get("adapter") or {}
    gate = payload.get("gate") or {}
    actuator = payload.get("actuator") or {}
    health = payload.get("deviceHealth") or {}

    ev = intent.get("targets", {}).get("ev", {}) if isinstance(intent.get("targets"), dict) else {}
    cmd = adapter.get("command") or {}
    transition = actuator.get("transition") or {}
    observed = actuator.get("observed") or {}
    easee = health.get("easee") or {}

    source_revision = (
        adapter.get("sourceRevision")
        if adapter.get("sourceRevision") is not None
        else intent.get("sourceRevision")
    )
    try:
        source_revision = int(source_revision) if source_revision is not None else None
    except (TypeError, ValueError):
        source_revision = None

    errors = gate.get("errors")
    if not isinstance(errors, list):
        errors = []

    return {
        "source_revision": source_revision,
        "control_revision": str(
            intent.get("controlRevision")
            or adapter.get("controlRevision")
            or gate.get("controlRevision")
            or actuator.get("controlRevision")
            or ""
        ) or None,
        "target_w": _number(ev.get("target_W") if ev else actuator.get("targetW")),
        "requested_a": _number(cmd.get("requested_A") if cmd else gate.get("requested_A")),
        "phase_mode": str(
            (cmd.get("mode") if cmd else gate.get("phaseMode")) or ""
        ) or None,
        "gate_status": str(gate.get("finalStatus") or gate.get("status") or "") or None,
        "gate_errors_json": json.dumps(errors, separators=(",", ":"), ensure_ascii=False),
        "actuator_status": str(actuator.get("status") or "") or None,
        "actuator_reason": str(actuator.get("reason") or "") or None,
        "actuator_target_a": _number(actuator.get("targetA")),
        "actuator_phase_mode": str(actuator.get("phaseMode") or "") or None,
        "actuator_confirmed_mode": str(actuator.get("confirmedMode") or "") or None,
        "transition_stage": str(transition.get("stage") or "") or None,
        "transition_failure": str(transition.get("failure") or "") or None,
        "charge_state": str(
            observed.get("chargeState")
            or easee.get("chargeState")
            or ""
        ) or None,
        "device_health_status": str(health.get("status") or "") or None,
        "device_health_reason": str(health.get("reason") or "") or None,
        "physical_write_performed": 1 if actuator.get("physicalWritePerformed") is True else 0,
    }


def archive_ev_control(payload, db_path=HISTORY_DB):
    generated = _validate(payload)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    # Deduplicate semantic evidence, not transport timestamps. Gate and actuator
    # changes remain distinct because their payload content changes; a repeated
    # trigger with identical runtime contracts does not create event noise.
    hash_payload = dict(payload)
    hash_payload.pop("generatedAt", None)
    hash_canonical = json.dumps(
        hash_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    event_hash = hashlib.sha256(hash_canonical.encode("utf-8")).hexdigest()
    data = _extract(payload)

    con = sqlite3.connect(str(db_path), timeout=2.0)
    con.execute("PRAGMA busy_timeout=2000")
    try:
        _ensure_schema(con)
        cur = con.execute(
            """
            INSERT OR IGNORE INTO ev_control_events (
                event_hash, ts_utc, source_revision, control_revision,
                target_w, requested_a, phase_mode,
                gate_status, gate_errors_json,
                actuator_status, actuator_reason, actuator_target_a,
                actuator_phase_mode, actuator_confirmed_mode,
                transition_stage, transition_failure,
                charge_state, device_health_status, device_health_reason,
                physical_write_performed, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_hash,
                generated.isoformat().replace("+00:00", "Z"),
                data["source_revision"],
                data["control_revision"],
                data["target_w"],
                data["requested_a"],
                data["phase_mode"],
                data["gate_status"],
                data["gate_errors_json"],
                data["actuator_status"],
                data["actuator_reason"],
                data["actuator_target_a"],
                data["actuator_phase_mode"],
                data["actuator_confirmed_mode"],
                data["transition_stage"],
                data["transition_failure"],
                data["charge_state"],
                data["device_health_status"],
                data["device_health_reason"],
                data["physical_write_performed"],
                canonical,
            ),
        )
        con.commit()
        return {
            "archived": True,
            "inserted": cur.rowcount == 1,
            "eventHash": event_hash,
            "generatedAt": payload.get("generatedAt"),
        }
    finally:
        con.close()


def handle_ev_control_ingest(handler, send_json):
    try:
        if not _authorized(handler):
            send_json(handler, 401, {
                "status": "REJECTED",
                "reason": "UNAUTHORIZED",
                "evidenceWritten": False,
            })
            return
    except RuntimeError as exc:
        send_json(handler, 503, {
            "status": "FAIL_CLOSED",
            "reason": str(exc),
            "evidenceWritten": False,
        })
        return

    try:
        length = int(handler.headers.get("Content-Length") or "0")
    except ValueError:
        length = 0
    if length <= 0 or length > MAX_BODY_BYTES:
        send_json(handler, 413, {
            "status": "REJECTED",
            "reason": "BODY_SIZE",
            "evidenceWritten": False,
        })
        return

    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        result = archive_ev_control(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        send_json(handler, 400, {
            "status": "REJECTED",
            "reason": "INVALID_JSON",
            "evidenceWritten": False,
        })
        return
    except ValueError as exc:
        send_json(handler, 409, {
            "status": "REJECTED",
            "reason": str(exc),
            "evidenceWritten": False,
        })
        return
    except Exception as exc:
        print(f"WARN: EV control archive failed: {exc}")
        send_json(handler, 500, {
            "status": "FAIL_CLOSED",
            "reason": "EV_CONTROL_ARCHIVE_FAILED",
            "evidenceWritten": False,
        })
        return

    send_json(handler, 202, {
        "status": "ACCEPTED",
        "evidenceWritten": True,
        **result,
    })

"""Authenticated LAN ingest for Homey Quooker observability.

Direction is one-way and control-neutral:
Homey Quooker observability -> Pi status API -> local SQLite evidence.

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
SCHEMA = "EMS_HOMEY_QUOOKER_EVIDENCE_V0.1"
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
    if not supplied.startswith("Bearer "):
        return False
    return hmac.compare_digest(supplied[7:], expected)


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


def _bool_int(value):
    if value is True:
        return 1
    if value is False:
        return 0
    return None


def _text(value):
    if value is None:
        return None
    value = str(value)
    return value if value else None


def _validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("QUOOKER_EVIDENCE_NOT_OBJECT")
    if payload.get("schema") != SCHEMA:
        raise ValueError("QUOOKER_EVIDENCE_SCHEMA")
    if payload.get("readOnly") is not True:
        raise ValueError("QUOOKER_EVIDENCE_READ_ONLY")
    if payload.get("observabilityOnly") is not True:
        raise ValueError("QUOOKER_EVIDENCE_OBSERVABILITY_ONLY")
    if payload.get("controlImpact") != "NONE":
        raise ValueError("QUOOKER_EVIDENCE_IMPACT")

    generated = _parse_utc(payload.get("generatedAt"))
    if generated is None:
        raise ValueError("QUOOKER_EVIDENCE_TIMESTAMP")
    age = (datetime.now(timezone.utc) - generated).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("QUOOKER_EVIDENCE_FROM_FUTURE")
    if age > MAX_AGE_SECONDS:
        raise ValueError("QUOOKER_EVIDENCE_STALE")

    for key in ("control", "actuator", "detector"):
        value = payload.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError("QUOOKER_EVIDENCE_" + key.upper())

    if not any(isinstance(payload.get(key), dict) for key in ("control", "actuator", "detector")):
        raise ValueError("QUOOKER_EVIDENCE_EMPTY")

    return generated


def _ensure_schema(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS quooker_control_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_hash TEXT NOT NULL UNIQUE,
            ts_utc TEXT NOT NULL,
            control_mode TEXT,
            control_target_on INTEGER,
            control_reason TEXT,
            modeled_power_w REAL,
            avg_grid_w REAL,
            p1_fresh INTEGER,
            start_export_w REAL,
            stop_import_w REAL,
            actuator_control_valid INTEGER,
            actuator_control_fresh INTEGER,
            actuator_desired_on INTEGER,
            actuator_actual_on INTEGER,
            actuator_would_write INTEGER,
            actuator_reason TEXT,
            detector_valid INTEGER,
            detector_switch_on INTEGER,
            detector_active INTEGER,
            detector_status TEXT,
            detector_power_w REAL,
            detector_reason TEXT,
            detector_last_heating_at TEXT,
            detector_last_heating_power_w REAL,
            physical_write_performed INTEGER,
            raw_json TEXT NOT NULL,
            collected_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quooker_control_events_time
        ON quooker_control_events(ts_utc)
        """
    )


def _extract(payload):
    control = payload.get("control") or {}
    actuator = payload.get("actuator") or {}
    detector = payload.get("detector") or {}
    thresholds = control.get("thresholds") if isinstance(control.get("thresholds"), dict) else {}
    p1 = control.get("p1") if isinstance(control.get("p1"), dict) else {}
    actuator_safety = actuator.get("safety") if isinstance(actuator.get("safety"), dict) else {}
    detector_safety = detector.get("safety") if isinstance(detector.get("safety"), dict) else {}

    physical = (
        actuator_safety.get("physicalWritePerformed") is True
        or detector_safety.get("physicalWritePerformed") is True
    )

    return {
        "control_mode": _text(control.get("mode")),
        "control_target_on": _bool_int(control.get("target_on")),
        "control_reason": _text(control.get("reason")),
        "modeled_power_w": _number(control.get("modeledPowerW")),
        "avg_grid_w": _number(p1.get("avgGridW")),
        "p1_fresh": _bool_int(p1.get("p1Fresh")),
        "start_export_w": _number(thresholds.get("startExportW")),
        "stop_import_w": _number(thresholds.get("stopImportW")),
        "actuator_control_valid": _bool_int(actuator.get("controlValid")),
        "actuator_control_fresh": _bool_int(actuator.get("controlFresh")),
        "actuator_desired_on": _bool_int(actuator.get("desiredOn")),
        "actuator_actual_on": _bool_int(actuator.get("actualOn")),
        "actuator_would_write": _bool_int(actuator.get("wouldWrite")),
        "actuator_reason": _text(actuator.get("reason")),
        "detector_valid": _bool_int(detector.get("valid")),
        "detector_switch_on": _bool_int(detector.get("switchOn")),
        "detector_active": _bool_int(detector.get("active")),
        "detector_status": _text(detector.get("status")),
        "detector_power_w": _number(detector.get("powerW")),
        "detector_reason": _text(detector.get("reason")),
        "detector_last_heating_at": _text(detector.get("lastHeatingAt")),
        "detector_last_heating_power_w": _number(detector.get("lastHeatingPowerW")),
        "physical_write_performed": 1 if physical else 0,
    }


NORMALIZED_COLUMNS = (
    "control_mode",
    "control_target_on",
    "control_reason",
    "modeled_power_w",
    "avg_grid_w",
    "p1_fresh",
    "start_export_w",
    "stop_import_w",
    "actuator_control_valid",
    "actuator_control_fresh",
    "actuator_desired_on",
    "actuator_actual_on",
    "actuator_would_write",
    "actuator_reason",
    "detector_valid",
    "detector_switch_on",
    "detector_active",
    "detector_status",
    "detector_power_w",
    "detector_reason",
    "detector_last_heating_at",
    "detector_last_heating_power_w",
    "physical_write_performed",
)

# P1 watts and detector pulse watts are evidence values, but not event identity.
# A new row is needed when control reasoning, actuator state or detector state
# changes. This prevents high-rate observability triggers from turning normal
# P1 variation into an event stream.
DEDUPE_COLUMNS = (
    "control_mode",
    "control_target_on",
    "control_reason",
    "p1_fresh",
    "actuator_control_valid",
    "actuator_control_fresh",
    "actuator_desired_on",
    "actuator_actual_on",
    "actuator_would_write",
    "actuator_reason",
    "detector_valid",
    "detector_switch_on",
    "detector_active",
    "detector_status",
    "detector_reason",
    "detector_last_heating_at",
    "physical_write_performed",
)


def _normalized_tuple(data):
    return tuple(data[key] for key in NORMALIZED_COLUMNS)


def _dedupe_tuple(data):
    return tuple(data[key] for key in DEDUPE_COLUMNS)


def _latest_dedupe_tuple(con):
    row = con.execute(
        f"""
        SELECT {",".join(DEDUPE_COLUMNS)}
        FROM quooker_control_events
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return tuple(row) if row is not None else None


def archive_quooker_evidence(payload, db_path=HISTORY_DB):
    generated = _validate(payload)
    data = _extract(payload)
    hash_canonical = json.dumps(
        {key: data[key] for key in DEDUPE_COLUMNS},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    event_hash = hashlib.sha256(hash_canonical.encode("utf-8")).hexdigest()
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )

    con = sqlite3.connect(str(db_path), timeout=2.0)
    con.execute("PRAGMA busy_timeout=2000")
    try:
        _ensure_schema(con)
        if _latest_dedupe_tuple(con) == _dedupe_tuple(data):
            return {
                "archived": True,
                "inserted": False,
                "eventHash": event_hash,
                "generatedAt": payload.get("generatedAt"),
                "dedupe": "LATEST_NORMALIZED_EVIDENCE",
            }

        columns = ",".join(NORMALIZED_COLUMNS)
        placeholders = ",".join("?" for _ in NORMALIZED_COLUMNS)
        cur = con.execute(
            f"""
            INSERT OR IGNORE INTO quooker_control_events
            (event_hash,ts_utc,{columns},raw_json)
            VALUES (?,?,{placeholders},?)
            """,
            (
                event_hash,
                generated.isoformat().replace("+00:00", "Z"),
                *_normalized_tuple(data),
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


def handle_quooker_evidence_ingest(handler, send_json):
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
        result = archive_quooker_evidence(payload)
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
        print(f"WARN: Quooker evidence archive failed: {exc}")
        send_json(handler, 500, {
            "status": "FAIL_CLOSED",
            "reason": "QUOOKER_EVIDENCE_ARCHIVE_FAILED",
            "evidenceWritten": False,
        })
        return

    send_json(handler, 202, {
        "status": "ACCEPTED",
        "evidenceWritten": True,
        **result,
    })

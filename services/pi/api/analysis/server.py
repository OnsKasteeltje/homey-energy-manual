#!/usr/bin/env python3
"""Read-only EMS AI analysis API.

The service is deliberately outside the realtime control path. It builds a
bounded evidence package from canonical Pi history and sends only that package
plus the user's question to a configured language model. It never writes EMS
state or physical devices.
"""

import json
import os
import sqlite3
import subprocess
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

HOST = os.environ.get("EMS_AI_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMS_AI_PORT", "3210"))
MODEL = os.environ.get("EMS_AI_MODEL", "gpt-6-luna")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_RESPONSES_URL = os.environ.get("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")
HISTORY_DB = os.environ.get("EMS_HISTORY_DB", "/home/jeroen/ems/data/ems-history.sqlite")
PERFORMANCE_COMMAND = os.environ.get("EMS_PERFORMANCE_COMMAND", "/usr/local/bin/ems-performance")
HEALTH_COMMAND = os.environ.get("EMS_HEALTH_COMMAND", "/usr/local/bin/ems-health")
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

SCHEMA = "EMS_AI_ANALYSIS_V0.2"
EVIDENCE_SCHEMA = "EMS_AI_EVIDENCE_V0.2"
MAX_BODY_BYTES = 16 * 1024
MAX_QUESTION_CHARS = 1200

SYSTEM_INSTRUCTIONS = """You are the read-only analysis layer for a household Energy Management System.
Answer in Dutch unless the user's question is clearly in another language.
Use ONLY the supplied EMS evidence. Never claim facts that are not present.
Clearly distinguish:
1. Feit: directly observed or recorded evidence.
2. Afleiding: a conclusion supported by the evidence.
3. Advies: a possible improvement, explicitly marked as advice.
When evidence is insufficient, say exactly what is missing.
Do not issue commands, suggest bypassing safety gates, or claim that any device was changed.
Prefer exact local timestamps and quantitative values.
An observed export window is not automatically an EMS fault; constraints may explain it.
Keep the answer concise but diagnostic."""

def _iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _bounds(day):
    start = datetime.combine(day, time.min, LOCAL_TZ)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

def _resolve_day(value):
    if value in (None, "", "today"):
        return datetime.now(LOCAL_TZ).date()
    if value == "yesterday":
        return datetime.now(LOCAL_TZ).date() - timedelta(days=1)
    return date.fromisoformat(str(value))

def _load_performance(day):
    proc = subprocess.run(
        [PERFORMANCE_COMMAND, day.isoformat()],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        detail = ""
        try:
            failed = json.loads(proc.stdout)
            detail = str(failed.get("error") or "").strip()
        except (json.JSONDecodeError, TypeError, AttributeError):
            detail = proc.stderr.strip()
        raise RuntimeError(
            "EMS_PERFORMANCE_FAILED" + (": " + detail if detail else "")
        )
    payload = json.loads(proc.stdout)
    if payload.get("schema") != "EMS_PI_DAY_PERFORMANCE_V0.1":
        raise RuntimeError("EMS_PERFORMANCE_SCHEMA_INVALID")
    return payload

def _load_health():
    proc = subprocess.run(
        [HEALTH_COMMAND],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return {
            "schema": "EMS_PI_HEALTH_V0.1",
            "status": "UNAVAILABLE",
            "error": (proc.stderr or proc.stdout).strip()[:400],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "schema": "EMS_PI_HEALTH_V0.1",
            "status": "UNAVAILABLE",
            "error": "HEALTH_JSON_INVALID",
        }
    return payload

def _observed_phase_mode(values):
    charging_value = values.get("ev_charging")
    if charging_value == 0.0:
        return "OFF"
    if charging_value != 1.0:
        return "UNKNOWN"
    currents = [
        values.get("ev_l1_a"),
        values.get("ev_l2_a"),
        values.get("ev_l3_a"),
    ]
    active = sum(
        1 for value in currents
        if isinstance(value, (int, float)) and abs(value) >= 2.0
    )
    if active >= 2:
        return "3P"
    if active == 1:
        return "1P"
    return "UNKNOWN"

def _ev_telemetry(day):
    start, end = _bounds(day)
    wanted_metrics = (
        "ev_connected", "ev_charging", "ev_requested_a", "ev_offered_a",
        "ev_l1_a", "ev_l2_a", "ev_l3_a", "ev_deadline_active",
        "ev_deadline_max_a", "ev_remaining_kwh", "ev_charge_state", "ev_need",
        "manager_decision", "manager_reason", "manager_priority",
    )
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(
            f"""
            SELECT m.ts_utc, x.metric_key, m.value_real, m.value_text
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            JOIN metrics x ON x.id=m.metric_id
            WHERE m.ts_utc>=? AND m.ts_utc<?
              AND d.device_key IN ('tesla','ems_manager')
              AND x.metric_key IN ({','.join('?' for _ in wanted_metrics)})
            ORDER BY m.ts_utc
            """,
            (_iso_z(start), _iso_z(end), *wanted_metrics),
        ).fetchall()

    buckets = {}
    for ts_text, metric_key, value_real, value_text in rows:
        ts = datetime.fromisoformat(ts_text.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        minute = (ts.minute // 5) * 5
        stamp = ts.replace(minute=minute, second=0, microsecond=0)
        item = buckets.setdefault(stamp, {})
        item[metric_key] = value_text if value_text is not None else value_real

    out = []
    for stamp in sorted(buckets):
        values = buckets[stamp]
        if not values:
            continue
        out.append({
            "atLocal": stamp.isoformat(),
            "connected": (
                None if values.get("ev_connected") is None
                else values.get("ev_connected") == 1.0
            ),
            "charging": (
                None if values.get("ev_charging") is None
                else values.get("ev_charging") == 1.0
            ),
            "requestedA": values.get("ev_requested_a"),
            "offeredA": values.get("ev_offered_a"),
            "phaseCurrentsA": {
                "l1": values.get("ev_l1_a"),
                "l2": values.get("ev_l2_a"),
                "l3": values.get("ev_l3_a"),
            },
            "observedPhaseMode": _observed_phase_mode(values),
            "chargeState": values.get("ev_charge_state"),
            "deadlineActive": (
                None if values.get("ev_deadline_active") is None
                else values.get("ev_deadline_active") == 1.0
            ),
            "deadlineMaxA": values.get("ev_deadline_max_a"),
            "remainingKWh": values.get("ev_remaining_kwh"),
            "need": values.get("ev_need"),
            "managerDecision": values.get("manager_decision"),
            "managerReason": values.get("manager_reason"),
            "managerPriority": values.get("manager_priority"),
        })
    return out[-180:]

def _ev_control_events(day):
    start, end = _bounds(day)
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ev_control_events'"
        ).fetchone()
        if not exists:
            return []
        rows = db.execute(
            """
            SELECT
                ts_utc, source_revision, control_revision, target_w,
                requested_a, phase_mode, gate_status, gate_errors_json,
                actuator_status, actuator_reason, actuator_target_a,
                actuator_phase_mode, actuator_confirmed_mode,
                transition_stage, transition_failure, charge_state,
                device_health_status, device_health_reason,
                physical_write_performed
            FROM ev_control_events
            WHERE ts_utc>=? AND ts_utc<?
            ORDER BY ts_utc
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()

    out = []
    for row in rows[-240:]:
        (
            ts_text, source_revision, control_revision, target_w,
            requested_a, phase_mode, gate_status, gate_errors_json,
            actuator_status, actuator_reason, actuator_target_a,
            actuator_phase_mode, actuator_confirmed_mode,
            transition_stage, transition_failure, charge_state,
            health_status, health_reason, physical_write,
        ) = row
        try:
            gate_errors = json.loads(gate_errors_json or "[]")
        except json.JSONDecodeError:
            gate_errors = []
        local = datetime.fromisoformat(
            ts_text.replace("Z", "+00:00")
        ).astimezone(LOCAL_TZ)
        out.append({
            "atLocal": local.isoformat(),
            "sourceRevision": source_revision,
            "controlRevision": control_revision,
            "targetW": target_w,
            "requestedA": requested_a,
            "phaseMode": phase_mode,
            "gateStatus": gate_status,
            "gateErrors": gate_errors,
            "actuatorStatus": actuator_status,
            "actuatorReason": actuator_reason,
            "actuatorTargetA": actuator_target_a,
            "actuatorPhaseMode": actuator_phase_mode,
            "actuatorConfirmedMode": actuator_confirmed_mode,
            "transitionStage": transition_stage,
            "transitionFailure": transition_failure,
            "chargeState": charge_state,
            "deviceHealthStatus": health_status,
            "deviceHealthReason": health_reason,
            "physicalWritePerformed": physical_write == 1,
        })
    return out

def _timeline(day):
    start, end = _bounds(day)
    wanted = ("grid_p1", "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000", "tesla")
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        device_ids = dict(db.execute(
            "SELECT device_key,id FROM devices WHERE device_key IN (%s)" %
            ",".join("?" for _ in wanted),
            wanted,
        ).fetchall())
        metric = db.execute(
            "SELECT id FROM metrics WHERE metric_key='electrical_power_w'"
        ).fetchone()
        if metric is None or any(k not in device_ids for k in wanted):
            raise RuntimeError("TIMELINE_SOURCE_INCOMPLETE")
        rows = db.execute(
            f"""
            SELECT m.ts_utc,d.device_key,m.value_real
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            WHERE m.metric_id=? AND m.ts_utc>=? AND m.ts_utc<?
              AND m.device_id IN ({','.join('?' for _ in wanted)})
            ORDER BY m.ts_utc
            """,
            (
                metric[0],
                _iso_z(start),
                _iso_z(end),
                *[device_ids[k] for k in wanted],
            ),
        ).fetchall()

    buckets = defaultdict(lambda: defaultdict(list))
    for ts_text, device_key, value in rows:
        if value is None:
            continue
        ts = datetime.fromisoformat(ts_text.replace("Z", "+00:00"))
        local = ts.astimezone(LOCAL_TZ)
        minute = (local.minute // 5) * 5
        key = local.replace(minute=minute, second=0, microsecond=0)
        buckets[key][device_key].append(float(value))

    out = []
    for stamp in sorted(buckets):
        b = buckets[stamp]
        if any(k not in b for k in wanted):
            continue
        avg = {k: sum(b[k]) / len(b[k]) for k in wanted}
        pv = max(0.0, avg["pv_solaredge"] + avg["pv_goodwe4200"] + avg["pv_goodwe2000"])
        grid = avg["grid_p1"]
        tesla = max(0.0, avg["tesla"])
        export = max(0.0, -grid)
        house = max(0.0, pv + grid)
        # Keep only intervals that materially help answer EV/PV/export questions.
        if export < 150 and tesla < 200:
            continue
        out.append({
            "atLocal": stamp.isoformat(),
            "gridW": round(grid),
            "pvW": round(pv),
            "houseW": round(house),
            "teslaW": round(tesla),
            "exportW": round(export),
        })
    # Bound model context. The newest intervals are generally most useful for "today".
    return out[-180:]

def build_evidence(day):
    performance = _load_performance(day)
    ev_telemetry = _ev_telemetry(day)
    ev_control = _ev_control_events(day)
    health = _load_health()
    return {
        "schema": EVIDENCE_SCHEMA,
        "generatedAt": _iso_z(datetime.now(timezone.utc)),
        "dateLocal": day.isoformat(),
        "sourceAuthority": {
            "measurements": "ems-history.sqlite",
            "evTelemetry": "Homey canonical state push -> ems-history.sqlite",
            "evControlEvents": "Homey observability LAN push -> ems-history.sqlite",
            "planner": "planner-history.sqlite via ems-performance",
            "performance": "EMS_PI_DAY_PERFORMANCE_V0.1",
            "currentHealth": "EMS_PI_HEALTH_V0.1 via ems-health",
        },
        "performance": performance,
        "timeline5m": _timeline(day),
        "evTelemetry5m": ev_telemetry,
        "evControlEvents": ev_control,
        "piHealthCurrent": health,
        "limitations": [
            "EV telemetry and control-event history only exist from their V0.2 commissioning onward; earlier gaps must not be backfilled by inference.",
            "Observed phase mode is derived from measured phase currents; use explicit actuator/gate phase fields when control-event evidence exists.",
            "Current Pi health does not prove health at an earlier historical decision timestamp.",
            "Recent incident evidence is best-effort journal coverage until durable incident history is implemented.",
            "Export windows are observations and require constraint context before classifying them as missed opportunities.",
        ],
    }

def _extract_output_text(payload):
    texts = []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return "\n".join(texts).strip()

def ask_model(question, evidence):
    if not OPENAI_API_KEY:
        raise RuntimeError("MODEL_NOT_CONFIGURED")
    body = json.dumps({
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": "Vraag:\n" + question + "\n\nEMS evidence JSON:\n" + json.dumps(evidence, ensure_ascii=False),
        "max_output_tokens": 1200,
    }).encode("utf-8")
    req = urlrequest.Request(
        OPENAI_RESPONSES_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + OPENAI_API_KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        error_code = ""
        try:
            failure = json.loads(exc.read().decode("utf-8"))
            error_code = str((failure.get("error") or {}).get("code") or "").strip()
        except Exception:
            error_code = ""
        reason = f"MODEL_HTTP_{exc.code}"
        if error_code:
            reason += ":" + error_code
        raise RuntimeError(reason) from exc
    except (urlerror.URLError, TimeoutError) as exc:
        raise RuntimeError("MODEL_UNAVAILABLE") from exc

    answer = _extract_output_text(payload)
    if not answer:
        raise RuntimeError("MODEL_EMPTY_RESPONSE")
    return answer, payload.get("id")

def send_json(handler, status, payload):
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)

class Handler(BaseHTTPRequestHandler):
    server_version = "EMSAIAnalysis"
    sys_version = ""

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/agent/health" and not path.query:
            send_json(self, 200, {
                "schema": SCHEMA,
                "status": "READY" if OPENAI_API_KEY else "MODEL_NOT_CONFIGURED",
                "readOnly": True,
                "controlWrites": False,
                "model": MODEL,
            })
            return
        send_json(self, 404, {"schema": SCHEMA, "status": "ERROR", "reason": "NOT_FOUND"})

    def do_POST(self):
        path = urlsplit(self.path)
        if path.path != "/agent/ask" or path.query:
            send_json(self, 404, {"schema": SCHEMA, "status": "ERROR", "reason": "NOT_FOUND"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            send_json(self, 413, {"schema": SCHEMA, "status": "ERROR", "reason": "REQUEST_TOO_LARGE"})
            return
        try:
            request_payload = json.loads(self.rfile.read(length).decode("utf-8"))
            question = request_payload.get("question")
            if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS:
                raise ValueError("QUESTION_INVALID")
            day = _resolve_day(request_payload.get("day"))
            evidence = build_evidence(day)
            answer, response_id = ask_model(question.strip(), evidence)
            send_json(self, 200, {
                "schema": SCHEMA,
                "status": "OK",
                "readOnly": True,
                "controlWrites": False,
                "dateLocal": day.isoformat(),
                "model": MODEL,
                "modelResponseId": response_id,
                "answer": answer,
                "evidenceSummary": {
                    "performanceSchema": evidence["performance"].get("schema"),
                    "timelinePoints": len(evidence["timeline5m"]),
                    "evTelemetryPoints": len(evidence["evTelemetry5m"]),
                    "evControlEvents": len(evidence["evControlEvents"]),
                    "piHealthStatus": evidence["piHealthCurrent"].get("status"),
                    "limitations": evidence["limitations"],
                },
            })
        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json(self, 400, {"schema": SCHEMA, "status": "ERROR", "reason": "JSON_INVALID"})
        except ValueError as exc:
            send_json(self, 400, {"schema": SCHEMA, "status": "ERROR", "reason": str(exc)})
        except (OSError, sqlite3.Error, subprocess.SubprocessError, RuntimeError) as exc:
            reason = str(exc)
            status = 503 if reason in {
                "MODEL_NOT_CONFIGURED", "MODEL_UNAVAILABLE",
                "TIMELINE_SOURCE_INCOMPLETE", "MODEL_EMPTY_RESPONSE"
            } or reason.startswith("MODEL_HTTP_") or reason.startswith("EMS_PERFORMANCE_FAILED") else 500
            send_json(self, status, {"schema": SCHEMA, "status": "UNAVAILABLE", "reason": reason})

    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

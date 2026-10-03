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
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

SCHEMA = "EMS_AI_ANALYSIS_V0.1"
EVIDENCE_SCHEMA = "EMS_AI_EVIDENCE_V0.1"
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
        raise RuntimeError("EMS_PERFORMANCE_FAILED")
    payload = json.loads(proc.stdout)
    if payload.get("schema") != "EMS_PI_DAY_PERFORMANCE_V0.1":
        raise RuntimeError("EMS_PERFORMANCE_SCHEMA_INVALID")
    return payload

def _timeline(day):
    start, end = _bounds(day)
    wanted = ("grid_p1", "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000", "tesla")
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro&immutable=1", uri=True) as db:
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
    return {
        "schema": EVIDENCE_SCHEMA,
        "generatedAt": _iso_z(datetime.now(timezone.utc)),
        "dateLocal": day.isoformat(),
        "sourceAuthority": {
            "measurements": "ems-history.sqlite",
            "planner": "planner-history.sqlite via ems-performance",
            "performance": "EMS_PI_DAY_PERFORMANCE_V0.1",
        },
        "performance": performance,
        "timeline5m": _timeline(day),
        "limitations": [
            "V0.1 timeline contains grid, aggregate PV and Tesla electrical power only.",
            "Historical requested charging current, phase mode and actuator reason codes are not yet included.",
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
        raise RuntimeError(f"MODEL_HTTP_{exc.code}") from exc
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
                    "limitations": evidence["limitations"],
                },
            })
        except ValueError as exc:
            send_json(self, 400, {"schema": SCHEMA, "status": "ERROR", "reason": str(exc)})
        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json(self, 400, {"schema": SCHEMA, "status": "ERROR", "reason": "JSON_INVALID"})
        except (OSError, sqlite3.Error, subprocess.SubprocessError, RuntimeError) as exc:
            reason = str(exc)
            status = 503 if reason in {
                "MODEL_NOT_CONFIGURED", "MODEL_UNAVAILABLE", "EMS_PERFORMANCE_FAILED",
                "TIMELINE_SOURCE_INCOMPLETE", "MODEL_EMPTY_RESPONSE"
            } or reason.startswith("MODEL_HTTP_") else 500
            send_json(self, status, {"schema": SCHEMA, "status": "UNAVAILABLE", "reason": reason})

    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

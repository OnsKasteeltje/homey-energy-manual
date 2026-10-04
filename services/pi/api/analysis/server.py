#!/usr/bin/env python3
"""Read-only EMS AI analysis API.

The service is deliberately outside the realtime control path. It builds a
bounded evidence package from canonical Pi history and sends only that package
plus the user's question to a configured language model. It never writes EMS
state or physical devices.
"""

import json
import os
import re
import sqlite3
import subprocess
import threading
import zlib
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import monotonic
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

HOST = os.environ.get("EMS_AI_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMS_AI_PORT", "3210"))
MODEL = os.environ.get("EMS_AI_MODEL", "gpt-6-luna")
REASONING_EFFORT = os.environ.get("EMS_AI_REASONING_EFFORT", "medium")
MAX_OUTPUT_TOKENS = int(os.environ.get("EMS_AI_MAX_OUTPUT_TOKENS", "1200"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_RESPONSES_URL = os.environ.get("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")
HISTORY_DB = os.environ.get("EMS_HISTORY_DB", "/home/jeroen/ems/data/ems-history.sqlite")
PLANNER_DB = os.environ.get("EMS_PLANNER_DB", "/home/jeroen/ems/data/planner-history.sqlite")
JOBS_DB = os.environ.get("EMS_AI_JOBS_DB", "/home/jeroen/ems/data/ai-analysis-jobs.sqlite")
PERFORMANCE_COMMAND = os.environ.get("EMS_PERFORMANCE_COMMAND", "/usr/local/bin/ems-performance")
HEALTH_COMMAND = os.environ.get("EMS_HEALTH_COMMAND", "/usr/local/bin/ems-health")
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

SCHEMA = "EMS_AI_ANALYSIS_V0.4"
EVIDENCE_SCHEMA = "EMS_AI_EVIDENCE_V0.4"
MAX_BODY_BYTES = 16 * 1024
MAX_QUESTION_CHARS = 1200
MAX_REQUEST_ID_CHARS = 80
MAX_CONTEXT_MESSAGES = 4
MAX_CONTEXT_MESSAGE_CHARS = 1200
JOB_RETENTION_HOURS = 24
JOB_PENDING_STALE_SECONDS = 180
EXPLICIT_TIME_WINDOW_MINUTES = 30
DAY_SCOPE_LIMITS = {
    "timeline5m": 72,
    "evTelemetry5m": 48,
    "evControlEvents": 48,
    "quookerEvents": 36,
    "semanticEvents": 48,
    "flexContextWindow": 3,
}
MODEL_INPUT_TARGET_TOKENS = 80000
MODEL_INPUT_HARD_LIMIT_TOKENS = 100000
MODEL_INPUT_ESTIMATE_BYTES_PER_TOKEN = 2.5
MODEL_INPUT_BUDGET_STEPS = (
    {
        "timeline5m": 60,
        "evTelemetry5m": 40,
        "evControlEvents": 40,
        "quookerEvents": 30,
        "semanticEvents": 36,
        "flexContextWindow": 3,
        "plannerDecisionWindow": 12,
        "forecastSlots": 24,
    },
    {
        "timeline5m": 48,
        "evTelemetry5m": 32,
        "evControlEvents": 32,
        "quookerEvents": 24,
        "semanticEvents": 30,
        "flexContextWindow": 3,
        "plannerDecisionWindow": 10,
        "forecastSlots": 20,
    },
    {
        "timeline5m": 36,
        "evTelemetry5m": 24,
        "evControlEvents": 24,
        "quookerEvents": 18,
        "semanticEvents": 24,
        "flexContextWindow": 2,
        "plannerDecisionWindow": 8,
        "forecastSlots": 16,
    },
    {
        "timeline5m": 24,
        "evTelemetry5m": 16,
        "evControlEvents": 16,
        "quookerEvents": 12,
        "semanticEvents": 18,
        "flexContextWindow": 2,
        "plannerDecisionWindow": 6,
        "forecastSlots": 12,
    },
    {
        "timeline5m": 16,
        "evTelemetry5m": 12,
        "evControlEvents": 12,
        "quookerEvents": 8,
        "semanticEvents": 12,
        "flexContextWindow": 1,
        "plannerDecisionWindow": 4,
        "forecastSlots": 8,
    },
)
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_ACTIVE_JOB_IDS = set()
_ACTIVE_JOB_LOCK = threading.Lock()

SYSTEM_INSTRUCTIONS = """You are the read-only analysis layer for a household Energy Management System.
Answer in Dutch unless the user's question is clearly in another language.
Use ONLY the supplied EMS evidence for factual claims. Never claim facts that are not present.
Recent conversation context, when supplied, is referential context only: use it to resolve phrases such as "dit tijdslot", "die deadline" or "waarom dan", but do not treat prior user or assistant statements as EMS evidence and do not repeat factual claims unless the current EMS evidence supports them.
Clearly distinguish:
1. Feit: directly observed or recorded evidence.
2. Afleiding: a conclusion supported by the evidence.
3. Advies: a possible improvement, explicitly marked as advice.
When analysing a power event, inspect all directly observed device-state fields in the relevant timeline5m interval. If washerActive, dryerActive or another directly observed device state is true, mention that state as a Feit when it is relevant to the question. Relevance is mandatory: do not mention unrelated device-state observations merely because they are present in the evidence. For subsystem-specific questions such as whether the Tesla charged, omit washer/dryer state unless it materially explains or constrains the Tesla event being asked about. Never equate an active device state with measured power attribution unless separate device-power evidence supports that attribution.
When evidence is insufficient, say exactly what is missing.
Do not issue commands, suggest bypassing safety gates, or claim that any device was changed.
Prefer exact local timestamps and quantitative values.
An observed export window is not automatically an EMS fault; constraints may explain it.
Use plannerDecisionWindow as historical intent evidence and never judge an earlier planner decision using a forecast generated later.
Use forecastVsActual15m to distinguish forecast error from planner/control execution error when the evidence supports that distinction.
For EV control questions, evControlEvents[].intentReason, realtimePhaseReason and realtimeCurrentReason are recorded Homey control reasons, not model inference. If a zero target/IDLE event has one of these reasons, use it before saying the underlying cause is unknown. Rolling available-power fields in the same event may support that reason but must not be invented when absent.
When an EV is charging below a deadline/current request, compare the control requestedA/actuatorTargetA with Easee requestedA, Easee offeredA, measured Easee phase currents and Equalizer/P1 phase currents from evControlEvents before diagnosing a control failure. Easee requestedA matching the EMS request while offeredA is lower proves that the reduction occurred downstream of the EMS/Homey target. If fresh Equalizer evidence is present, describe the pattern as consistent with Equalizer/load-balancing constraint; do not claim the Equalizer as the unique cause unless the evidence explicitly proves that attribution.
Use flexContextWindow for historical Heating/WW eligibility and priority, and quookerEvents for Quooker adapter/actuator/detector evidence.
Use semanticEvents as durable historical state-change evidence. provenanceClass=USER_INTENT_COMMAND proves that a user-intent command was recorded, but not that a physical device action occurred. provenanceClass=OBSERVED_STATE proves an observed state transition but does not identify who or what caused it. provenanceClass=DERIVED_STATE is Pi-derived state, and provenanceClass=SHADOW_DECISION is never proof of a physical write. The semantic-event archive starts at semanticEventCoverage.commissionedAt; its initial baseline creates no synthetic event, so absence before commissioning or absence of an event at baseline is not proof that no earlier change occurred.
When evidenceSelection.mode is EXPLICIT_TIME_WINDOW or CONTEXT_TIME_WINDOW, timeline5m, evTelemetry5m, evControlEvents and quookerEvents are intentionally limited to the documented local window around the selected clock time. Do not interpret absence outside that selected window as evidence that no activity occurred elsewhere in the day.
When evidenceSelection.mode is TOPIC_DAY_SCOPE or DAY_SCOPE_COMPACT, listed compactedFields are bounded samples across the day and listed omittedFields were intentionally excluded as unrelated to the current question. Do not interpret omitted or unsampled records as proof that no activity occurred.
When evidenceSelection.inputBudget.status is COMPACTED_TO_BUDGET or WITHIN_HARD_LIMIT, budgetCompactedFields were additionally reduced before the model call to stay within the documented estimated input budget. This is deliberate selection, not evidence that omitted records did not occur.
Heating progression remains SHADOW. Quooker actuator evidence is versioned: use quookerEvents[].actuator.mode as the authority. For SHADOW evidence, desiredOn/wouldWrite is not a physical command. For LIVE evidence, physicalWritePerformed=true is direct proof that the Homey actuator executed a device write, while actualOnBefore/actualOnAfter describe the observed state transition. physicalWritePerformed=false may be an idempotent no-op when desired and actual state already matched. Detector HEATING is independent electrical evidence and must not by itself be described as a physical control write.
Never backfill missing pre-commissioning flex or Quooker history by inference.
For an in-progress day, PARTIAL_TODAY means the calendar day is not finished; never call data incomplete from full-day coverage alone. Use quality.coveragePctElapsed, quality.elapsedCoverageStatus and quality.dayProgressPct.
Treat EV deadline metadata as an active constraint only when deadlineSemantics.effective is true. Old deadlineAt/remainingKWh values may remain visible for audit but are not active constraints when semantics say INACTIVE, EXPIRED_OR_STALE or INVALID_OR_STALE.
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

def _ev_intent_reason_context(raw_json):
    context = {
        "intentReason": None,
        "intentSource": None,
        "realtimeApplied": None,
        "realtimePhaseReason": None,
        "realtimeCurrentReason": None,
        "realtimeAvailableTotalW": None,
        "realtimeAvailableTotalAvg2mW": None,
        "realtimeRollingReady": None,
        "realtimeRollingCoverageMs": None,
        "easeeRequestedA": None,
        "easeeOfferedA": None,
        "easeeTargetCircuitA": None,
        "easeeMeasureW": None,
        "easeePhaseCurrentsA": None,
        "equalizerAvailable": None,
        "equalizerMeasureW": None,
        "equalizerPhaseCurrentsA": None,
        "equalizerTelemetryAgeSec": None,
        "p1PhaseCurrentsA": None,
        "offeredBelowRequestedA": None,
    }
    if not raw_json:
        return context
    try:
        payload = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except (json.JSONDecodeError, TypeError):
        return context
    if not isinstance(payload, dict):
        return context

    intent = payload.get("intent")
    if not isinstance(intent, dict):
        return context
    projection = intent.get("policyProjection")
    if not isinstance(projection, dict):
        projection = {}
    realtime = projection.get("realtime")
    if not isinstance(realtime, dict):
        realtime = {}
    phase = realtime.get("phaseShadow")
    if not isinstance(phase, dict):
        phase = {}
    targets = intent.get("targets")
    ev = targets.get("ev") if isinstance(targets, dict) else {}
    if not isinstance(ev, dict):
        ev = {}

    context["intentReason"] = projection.get("reason")
    context["intentSource"] = ev.get("source")
    context["realtimeApplied"] = realtime.get("applied")
    context["realtimePhaseReason"] = phase.get("phaseReason") or phase.get("reason")
    context["realtimeCurrentReason"] = phase.get("currentReason")
    context["realtimeAvailableTotalW"] = phase.get("availableTotalW")
    context["realtimeAvailableTotalAvg2mW"] = phase.get("availableTotalAvg2mW")
    context["realtimeRollingReady"] = phase.get("rollingReady")
    context["realtimeRollingCoverageMs"] = phase.get("rollingCoverageMs")

    health = payload.get("deviceHealth")
    if not isinstance(health, dict):
        health = {}
    easee = health.get("easee")
    if not isinstance(easee, dict):
        easee = {}
    equalizer = health.get("equalizer")
    if not isinstance(equalizer, dict):
        equalizer = {}
    p1 = health.get("p1")
    if not isinstance(p1, dict):
        p1 = {}

    context["easeeRequestedA"] = easee.get("requestedA")
    context["easeeOfferedA"] = easee.get("offeredA")
    context["easeeTargetCircuitA"] = easee.get("targetCircuitA")
    context["easeeMeasureW"] = easee.get("measureW")
    context["easeePhaseCurrentsA"] = easee.get("phaseCurrentsA")
    context["equalizerAvailable"] = equalizer.get("deviceAvailable")
    context["equalizerMeasureW"] = equalizer.get("measureW")
    context["equalizerPhaseCurrentsA"] = equalizer.get("phaseCurrentsA")
    context["equalizerTelemetryAgeSec"] = equalizer.get("telemetryAgeSec")
    context["p1PhaseCurrentsA"] = {
        "l1": p1.get("l1A"),
        "l2": p1.get("l2A"),
        "l3": p1.get("l3A"),
    } if any(p1.get(key) is not None for key in ("l1A", "l2A", "l3A")) else None

    try:
        requested = float(context["easeeRequestedA"])
        offered = float(context["easeeOfferedA"])
        context["offeredBelowRequestedA"] = offered + 0.25 < requested
    except (TypeError, ValueError):
        context["offeredBelowRequestedA"] = None

    return context


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
                physical_write_performed, raw_json
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
            health_status, health_reason, physical_write, raw_json,
        ) = row
        try:
            gate_errors = json.loads(gate_errors_json or "[]")
        except json.JSONDecodeError:
            gate_errors = []
        local = datetime.fromisoformat(
            ts_text.replace("Z", "+00:00")
        ).astimezone(LOCAL_TZ)
        intent_context = _ev_intent_reason_context(raw_json)
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
            **intent_context,
        })
    return out


_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)")


def _parse_ts(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt



def _deadline_semantics(payload, reference_time):
    if not isinstance(payload, dict):
        return {
            "effective": False,
            "state": "MISSING",
            "reason": "DEADLINE_EVIDENCE_MISSING",
        }

    active = (
        payload.get("active")
        if "active" in payload
        else payload.get("deadlineActive")
    )
    status = payload.get("status")
    remaining = payload.get("remainingKWh")
    deadline_at_raw = payload.get("deadlineAt")

    try:
        remaining_value = None if remaining is None else float(remaining)
    except (TypeError, ValueError):
        remaining_value = None

    deadline_at = _parse_ts(deadline_at_raw)
    reference = _parse_ts(reference_time)
    if reference is None and isinstance(reference_time, datetime):
        reference = reference_time

    if active is not True:
        return {
            "effective": False,
            "state": "INACTIVE",
            "reason": "DEADLINE_ACTIVE_FALSE",
            "sourceStatus": status,
        }

    if remaining_value is None or remaining_value <= 1e-9:
        return {
            "effective": False,
            "state": "COMPLETE_OR_STALE",
            "reason": "NO_POSITIVE_REMAINING_ENERGY",
            "sourceStatus": status,
        }

    if deadline_at is None:
        return {
            "effective": False,
            "state": "INVALID_OR_STALE",
            "reason": "DEADLINE_TIMESTAMP_MISSING_OR_INVALID",
            "sourceStatus": status,
        }

    if reference is not None:
        reference_utc = reference.astimezone(timezone.utc)
        if deadline_at.astimezone(timezone.utc) <= reference_utc:
            return {
                "effective": False,
                "state": "EXPIRED_OR_STALE",
                "reason": "DEADLINE_NOT_FUTURE_AT_REFERENCE_TIME",
                "sourceStatus": status,
            }

    if status in {"INACTIVE", "GOAL_COMPLETE", "EXPIRED"}:
        return {
            "effective": False,
            "state": "EXPIRED_OR_STALE" if status == "EXPIRED" else "INACTIVE",
            "reason": "SOURCE_STATUS_NOT_ACTIVE",
            "sourceStatus": status,
        }

    return {
        "effective": True,
        "state": "ACTIVE",
        "reason": "ACTIVE_WITH_FUTURE_DEADLINE_AND_POSITIVE_REMAINING_ENERGY",
        "sourceStatus": status,
    }


def _annotate_deadline_semantics(ev_telemetry, planner_window, flex_context):
    for point in ev_telemetry:
        point["deadlineSemantics"] = _deadline_semantics(
            point,
            point.get("atLocal"),
        )

    for point in planner_window:
        deadline = point.get("deadline")
        if isinstance(deadline, dict):
            deadline["deadlineSemantics"] = _deadline_semantics(
                deadline,
                point.get("snapshotGeneratedAtLocal"),
            )

    for point in flex_context:
        priority = point.get("priority")
        if not isinstance(priority, dict):
            continue
        ev = priority.get("ev")
        if not isinstance(ev, dict):
            continue
        ev["deadlineSemantics"] = _deadline_semantics(
            ev,
            point.get("snapshotCapturedAtLocal") or point.get("capturedAt"),
        )


def _normalize_anchors(anchors):
    result = []
    seen = set()
    for anchor in anchors:
        local = anchor.astimezone(LOCAL_TZ).replace(second=0, microsecond=0)
        key = local.isoformat()
        if key in seen:
            continue
        seen.add(key)
        result.append(local)
        if len(result) >= 6:
            break
    return result


def _explicit_question_anchors(question, day):
    anchors = []
    for match in _TIME_RE.finditer(question or ""):
        anchors.append(datetime.combine(
            day,
            time(int(match.group(1)), int(match.group(2))),
            LOCAL_TZ,
        ))
    return _normalize_anchors(anchors)


_CONTEXT_REF_RE = re.compile(
    r"\b(dit|deze|die|daar|dan|hier|zelfde|vorige|tijdslot|slot)\b"
    r"|\bde\s+deadline\b",
    re.IGNORECASE,
)


def _validate_conversation_context(value):
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise ValueError("CONTEXT_INVALID")

    out = []
    for item in value[-MAX_CONTEXT_MESSAGES:]:
        if not isinstance(item, dict):
            raise ValueError("CONTEXT_INVALID")
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            raise ValueError("CONTEXT_INVALID")
        text = content.strip()
        if not text:
            continue
        if len(text) > MAX_CONTEXT_MESSAGE_CHARS:
            raise ValueError("CONTEXT_INVALID")
        out.append({"role": role, "content": text})
    return out


def _is_contextual_followup(question):
    return _CONTEXT_REF_RE.search(question or "") is not None


def _detect_topics(text):
    value = (text or "").lower()
    topics = set()

    if re.search(r"\b(tesla|ev|easee|laden|laadt|laad[a-z-]*)\b", value):
        topics.add("EV")
    if re.search(r"\b(warm\s*water|warmwater|boiler|ww|quatt|heating|verwarm[a-z-]*|preheat[a-z-]*|serre)\b", value):
        topics.add("HEATING_WW")
    if "deadline" in value and "HEATING_WW" not in topics:
        topics.add("EV")
    if re.search(r"\b(quooker)\b", value):
        topics.add("QUOOKER")
    if re.search(r"\b(pv|flex|planner|forecast|export|teruglever[a-z-]*|overschot|zelfgebruik|tijdslot)\b", value):
        topics.add("PV_FLEX")

    return topics


def _question_topics(question, conversation_context=None):
    topics = _detect_topics(question)
    if _is_contextual_followup(question):
        for item in (conversation_context or [])[-2:]:
            topics.update(_detect_topics(item.get("content")))
    return sorted(topics)


def _context_followup_anchors(question, day, conversation_context=None):
    if not _is_contextual_followup(question):
        return []
    for item in reversed(conversation_context or []):
        anchors = _explicit_question_anchors(item.get("content"), day)
        if anchors:
            return anchors[:3]
    return []


def _question_anchors(question, day, performance, ev_control):
    anchors = _explicit_question_anchors(question, day)

    if not anchors:
        for window in (performance.get("surplusWindowsForReplay") or [])[:3]:
            dt = _parse_ts(window.get("start"))
            if dt is not None:
                anchors.append(dt.astimezone(LOCAL_TZ))
        for event in (ev_control or [])[-3:]:
            dt = _parse_ts(event.get("atLocal"))
            if dt is not None:
                anchors.append(dt.astimezone(LOCAL_TZ))

    return _normalize_anchors(anchors)


def _point_path(point, path):
    value = point
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _evenly_pick_indices(indices, count):
    ordered = sorted(set(indices))
    if count <= 0:
        return []
    if len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[-1]]

    positions = {
        round(i * (len(ordered) - 1) / (count - 1))
        for i in range(count)
    }
    return [ordered[pos] for pos in sorted(positions)]


def _bounded_points(points, max_points, change_paths=(), important=None):
    values = list(points)
    if len(values) <= max_points:
        return values

    important_indices = {0, len(values) - 1}
    for index, point in enumerate(values):
        if important is not None and important(point):
            important_indices.add(index)
        if index == 0:
            continue
        previous = values[index - 1]
        if any(
            _point_path(previous, path) != _point_path(point, path)
            for path in change_paths
        ):
            important_indices.add(index - 1)
            important_indices.add(index)

    if len(important_indices) >= max_points:
        chosen = _evenly_pick_indices(important_indices, max_points)
        return [values[index] for index in chosen]

    chosen = set(important_indices)
    for index in _evenly_pick_indices(range(len(values)), max_points):
        chosen.add(index)
        if len(chosen) >= max_points:
            break

    if len(chosen) < max_points:
        for index in range(len(values)):
            chosen.add(index)
            if len(chosen) >= max_points:
                break

    return [values[index] for index in sorted(chosen)]


def _model_context_block(conversation_context=None):
    context_lines = [
        f"{item['role']}: {item['content']}"
        for item in (conversation_context or [])
    ]
    if not context_lines:
        return ""
    return (
        "Recente conversatiecontext (alleen voor referenties; "
        "geen EMS-bewijs):\n"
        + "\n".join(context_lines)
        + "\n\n"
    )


def _model_input_text(question, evidence, conversation_context=None):
    return (
        _model_context_block(conversation_context)
        + "Vraag:\n"
        + question
        + "\n\nEMS evidence JSON:\n"
        + json.dumps(evidence, ensure_ascii=False)
    )


def _estimate_model_input_tokens(question, evidence, conversation_context=None):
    # No runtime tokenizer dependency: use an intentionally conservative
    # byte-based estimator calibrated against observed EMS model calls.
    model_text = (
        SYSTEM_INSTRUCTIONS
        + "\n"
        + _model_input_text(question, evidence, conversation_context)
    )
    input_bytes = len(model_text.encode("utf-8"))
    estimated_tokens = (
        int(input_bytes / MODEL_INPUT_ESTIMATE_BYTES_PER_TOKEN) + 1
    )
    return estimated_tokens, input_bytes


def _budget_compact_field(
    evidence,
    field,
    max_points,
    change_paths=(),
    important=None,
):
    points = evidence.get(field)
    if not isinstance(points, list) or len(points) <= max_points:
        return False
    evidence[field] = _bounded_points(
        points,
        max_points,
        change_paths=change_paths,
        important=important,
    )
    return len(evidence[field]) < len(points)


def _budget_compact_evidence(evidence, limits):
    changed = []

    if _budget_compact_field(
        evidence,
        "timeline5m",
        limits["timeline5m"],
        change_paths=(("washerActive",), ("dryerActive",)),
    ):
        changed.append("timeline5m")

    if _budget_compact_field(
        evidence,
        "evTelemetry5m",
        limits["evTelemetry5m"],
        change_paths=(
            ("connected",),
            ("charging",),
            ("observedPhaseMode",),
            ("chargeState",),
            ("deadlineActive",),
            ("managerDecision",),
            ("managerReason",),
        ),
    ):
        changed.append("evTelemetry5m")

    if _budget_compact_field(
        evidence,
        "evControlEvents",
        limits["evControlEvents"],
        change_paths=(
            ("gateStatus",),
            ("actuatorStatus",),
            ("actuatorReason",),
            ("transitionStage",),
            ("transitionFailure",),
            ("chargeState",),
            ("deviceHealthStatus",),
            ("phaseMode",),
            ("intentReason",),
            ("realtimePhaseReason",),
            ("realtimeCurrentReason",),
            ("easeeRequestedA",),
            ("easeeOfferedA",),
            ("easeeMeasureW",),
            ("equalizerPhaseCurrentsA", "l1"),
            ("equalizerPhaseCurrentsA", "l2"),
            ("equalizerPhaseCurrentsA", "l3"),
        ),
        important=lambda point: bool(
            point.get("physicalWritePerformed")
            or point.get("transitionFailure")
            or point.get("gateErrors")
        ),
    ):
        changed.append("evControlEvents")

    if _budget_compact_field(
        evidence,
        "quookerEvents",
        limits["quookerEvents"],
        change_paths=(
            ("control", "targetOn"),
            ("actuator", "mode"),
            ("actuator", "actualOn"),
            ("detector", "active"),
            ("detector", "status"),
            ("physicalWritePerformed",),
        ),
        important=lambda point: bool(
            point.get("physicalWritePerformed")
            or (point.get("actuator") or {}).get("writeError")
        ),
    ):
        changed.append("quookerEvents")

    if _budget_compact_field(
        evidence,
        "semanticEvents",
        limits["semanticEvents"],
        change_paths=(
            ("eventType",),
            ("domain",),
            ("subject",),
        ),
        important=lambda point: (
            point.get("provenanceClass") == "USER_INTENT_COMMAND"
        ),
    ):
        changed.append("semanticEvents")

    if _budget_compact_field(
        evidence,
        "flexContextWindow",
        limits["flexContextWindow"],
        change_paths=(
            ("priority", "ev", "deadlineActive"),
            ("priority", "ev", "urgency"),
            ("priority", "decision", "priorityOwner"),
        ),
    ):
        changed.append("flexContextWindow")

    if _budget_compact_field(
        evidence,
        "plannerDecisionWindow",
        limits["plannerDecisionWindow"],
        change_paths=(
            ("deadline", "active"),
            ("deadline", "deadlineAt"),
            ("action", "tesla"),
            ("action", "warmWater"),
        ),
    ):
        changed.append("plannerDecisionWindow")

    forecast = evidence.get("forecastVsActual15m")
    if isinstance(forecast, dict):
        slots = forecast.get("slots")
        if (
            isinstance(slots, list)
            and len(slots) > limits["forecastSlots"]
        ):
            forecast["slots"] = _bounded_points(
                slots, limits["forecastSlots"]
            )
            changed.append("forecastVsActual15m.slots")

    return changed


def _refresh_budget_selected_counts(evidence):
    selection = evidence.get("evidenceSelection") or {}
    counts = selection.get("selectedCounts")
    if not isinstance(counts, dict):
        return
    for field in (
        "timeline5m",
        "evTelemetry5m",
        "evControlEvents",
        "quookerEvents",
        "semanticEvents",
        "flexContextWindow",
    ):
        value = evidence.get(field)
        if isinstance(value, list):
            counts[field] = len(value)


def _apply_model_input_budget(
    evidence,
    question,
    conversation_context=None,
):
    selection = evidence.get("evidenceSelection")
    if not isinstance(selection, dict):
        selection = {}
        evidence["evidenceSelection"] = selection

    budget = {
        "targetTokens": MODEL_INPUT_TARGET_TOKENS,
        "hardLimitTokens": MODEL_INPUT_HARD_LIMIT_TOKENS,
        "estimatedTokens": None,
        "estimatedInputBytes": None,
        "preBudgetEstimatedTokens": None,
        "status": "PENDING",
        "estimator": "UTF8_BYTES_DIV_2_5_CONSERVATIVE",
        "exactTokenizer": False,
        "compactionStepsApplied": 0,
        "budgetCompactedFields": [],
    }
    selection["inputBudget"] = budget

    estimated, input_bytes = _estimate_model_input_tokens(
        question, evidence, conversation_context
    )
    budget["preBudgetEstimatedTokens"] = estimated

    compacted = []
    steps_applied = 0

    if estimated > MODEL_INPUT_TARGET_TOKENS:
        for step_number, limits in enumerate(
            MODEL_INPUT_BUDGET_STEPS, start=1
        ):
            changed = _budget_compact_evidence(evidence, limits)
            steps_applied = step_number
            compacted.extend(changed)
            _refresh_budget_selected_counts(evidence)

            estimated, input_bytes = _estimate_model_input_tokens(
                question, evidence, conversation_context
            )
            if estimated <= MODEL_INPUT_TARGET_TOKENS:
                break

    compacted_unique = sorted(set(compacted))
    selection["compactedFields"] = sorted(set(
        (selection.get("compactedFields") or []) + compacted_unique
    ))
    budget["compactionStepsApplied"] = steps_applied
    budget["budgetCompactedFields"] = compacted_unique

    estimated, input_bytes = _estimate_model_input_tokens(
        question, evidence, conversation_context
    )
    budget["estimatedTokens"] = estimated
    budget["estimatedInputBytes"] = input_bytes

    if estimated > MODEL_INPUT_HARD_LIMIT_TOKENS:
        budget["status"] = "HARD_LIMIT_EXCEEDED"
        raise RuntimeError("MODEL_INPUT_BUDGET_EXCEEDED")
    if compacted_unique and estimated <= MODEL_INPUT_TARGET_TOKENS:
        budget["status"] = "COMPACTED_TO_BUDGET"
    elif estimated <= MODEL_INPUT_TARGET_TOKENS:
        budget["status"] = "WITHIN_BUDGET"
    else:
        budget["status"] = "WITHIN_HARD_LIMIT"

    # Re-estimate once with the final status/diagnostics included.
    estimated, input_bytes = _estimate_model_input_tokens(
        question, evidence, conversation_context
    )
    budget["estimatedTokens"] = estimated
    budget["estimatedInputBytes"] = input_bytes
    if estimated > MODEL_INPUT_HARD_LIMIT_TOKENS:
        budget["status"] = "HARD_LIMIT_EXCEEDED"
        raise RuntimeError("MODEL_INPUT_BUDGET_EXCEEDED")

    return evidence


def _select_points_near_anchors(
    points,
    anchors,
    window_minutes=EXPLICIT_TIME_WINDOW_MINUTES,
):
    if not anchors:
        return list(points)

    window_seconds = max(0, int(window_minutes)) * 60
    selected = []
    for point in points:
        if not isinstance(point, dict):
            continue
        point_time = _parse_ts(point.get("atLocal"))
        if point_time is None:
            continue
        point_utc = point_time.astimezone(timezone.utc)
        if any(
            abs(
                (
                    point_utc
                    - anchor.astimezone(timezone.utc)
                ).total_seconds()
            ) <= window_seconds
            for anchor in anchors
        ):
            selected.append(point)
    return selected


def _timeline(day):
    start, end = _bounds(day)
    mandatory_power = (
        "grid_p1", "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000", "tesla",
    )
    optional_power = ("boiler", "quatt_cic")
    state_devices = ("washer", "dryer")
    wanted = mandatory_power + optional_power + state_devices

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(
            f"""
            SELECT m.ts_utc,d.device_key,x.metric_key,m.value_real
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            JOIN metrics x ON x.id=m.metric_id
            WHERE m.ts_utc>=? AND m.ts_utc<?
              AND d.device_key IN ({','.join('?' for _ in wanted)})
              AND x.metric_key IN ('electrical_power_w','active')
            ORDER BY m.ts_utc
            """,
            (_iso_z(start), _iso_z(end), *wanted),
        ).fetchall()

    buckets = defaultdict(lambda: defaultdict(list))
    for ts_text, device_key, metric_key, value in rows:
        if value is None:
            continue
        ts = datetime.fromisoformat(ts_text.replace("Z", "+00:00"))
        local = ts.astimezone(LOCAL_TZ)
        minute = (local.minute // 5) * 5
        key = local.replace(minute=minute, second=0, microsecond=0)
        buckets[key][(device_key, metric_key)].append(float(value))

    out = []
    for stamp in sorted(buckets):
        b = buckets[stamp]
        if any((key, "electrical_power_w") not in b for key in mandatory_power):
            continue

        def avg_power(key):
            values = b.get((key, "electrical_power_w"))
            return None if not values else sum(values) / len(values)

        def active_state(key):
            values = b.get((key, "active"))
            return None if not values else max(values) >= 0.5

        grid = avg_power("grid_p1")
        pv = max(
            0.0,
            sum(avg_power(key) or 0.0 for key in (
                "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000",
            )),
        )
        tesla = max(0.0, avg_power("tesla") or 0.0)
        boiler_raw = avg_power("boiler")
        quatt_raw = avg_power("quatt_cic")
        boiler = None if boiler_raw is None else max(0.0, boiler_raw)
        quatt = None if quatt_raw is None else max(0.0, quatt_raw)
        washer = active_state("washer")
        dryer = active_state("dryer")
        export = max(0.0, -grid)
        house = max(0.0, pv + grid)
        tracked = tesla + (boiler or 0.0) + (quatt or 0.0)
        other_house = max(0.0, house - tracked)

        if (
            export < 150
            and tesla < 200
            and (boiler or 0.0) < 200
            and (quatt or 0.0) < 200
            and washer is not True
            and dryer is not True
        ):
            continue

        out.append({
            "atLocal": stamp.isoformat(),
            "gridW": round(grid),
            "pvW": round(pv),
            "houseW": round(house),
            "teslaW": round(tesla),
            "boilerW": None if boiler is None else round(boiler),
            "quattW": None if quatt is None else round(quatt),
            "washerActive": washer,
            "dryerActive": dryer,
            "otherHouseWDerived": round(other_house),
            "exportW": round(export),
        })
    return out[-180:]


def _project_action(action):
    if not isinstance(action, dict):
        return None

    # Canonical planner-history stores dynamic-shadow-plan.json, whose
    # executable planning decisions live in plan["slots"]. Do not use the
    # separate website publish projection (plan.plan.actions) as historical
    # decision authority.
    start = action.get("slot_start_utc") or action.get("start")
    return {
        "start": start,
        "localDate": action.get("localDate"),
        "pvForecastW": action.get("pvForecastW"),
        "baseLoadForecastW": action.get("baseLoadForecastW"),
        "quattForecastW": action.get("quattForecastW"),
        "forecastExportBeforeFlexW": action.get("forecastExportBeforeFlexW"),
        "correctedExportBeforeFlexW": action.get("correctedExportBeforeFlexW"),
        "confidence": action.get("confidence"),
        "wwPlanW": action.get("wwPlanW"),
        "wwAllocationReason": action.get("wwAllocationReason"),
        "wwCandidatePvCoverage": action.get("wwCandidatePvCoverage"),
        "wwCandidateGridImportW": action.get("wwCandidateGridImportW"),
        "wwCandidateSourceEligible": action.get("wwCandidateSourceEligible"),
        "evPlanW": action.get("evPlanW"),
        "evPlanA": action.get("evPlanA"),
        "evPlanPhaseMode": action.get("evPlanPhaseMode"),
        "evAllocationReason": action.get("evAllocationReason"),
        "evOpportunityWindowId": action.get("evOpportunityWindowId"),
        "evOpportunityWindowClass": action.get("evOpportunityWindowClass"),
        "evOpportunityWindowSelectionReason": action.get(
            "evOpportunityWindowSelectionReason"
        ),
        "evOpportunityWindowPvCoverage": action.get(
            "evOpportunityWindowPvCoverage"
        ),
        "evDeadlineRequired": action.get("evDeadlineRequired"),
        "quookerMode": action.get("quookerMode"),
        "quookerPlanW": action.get("quookerPlanW"),
        "quookerOpportunityAllowed": action.get("quookerOpportunityAllowed"),
        "gridImportAfterFlexW": action.get("gridImportAfterFlexW"),
        "gridExportAfterFlexW": action.get("gridExportAfterFlexW"),
    }


def _planner_decision_window(day, anchors):
    if not os.path.exists(PLANNER_DB) or not anchors:
        return []

    start, end = _bounds(day)
    query_start = start - timedelta(hours=2)
    with sqlite3.connect(f"file:{PLANNER_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(
            """
            SELECT generated_at_utc,snapshot_zlib
            FROM planner_snapshots
            WHERE generated_at_utc>=? AND generated_at_utc<?
            ORDER BY generated_at_utc
            """,
            (_iso_z(query_start), _iso_z(end)),
        ).fetchall()

    snapshots = []
    for generated_text, blob in rows:
        generated = _parse_ts(generated_text)
        if generated is None:
            continue
        try:
            payload = json.loads(zlib.decompress(blob).decode("utf-8"))
        except (TypeError, ValueError, zlib.error, json.JSONDecodeError):
            continue
        snapshots.append((generated.astimezone(timezone.utc), payload))

    out = []
    seen = set()
    for anchor in anchors:
        anchor_utc = anchor.astimezone(timezone.utc)
        eligible = [item for item in snapshots if item[0] <= anchor_utc]
        if not eligible:
            continue
        generated, snapshot = eligible[-1]
        age_min = (anchor_utc - generated).total_seconds() / 60.0
        if age_min > 90:
            continue

        plan = snapshot.get("plan") or {}
        context = snapshot.get("context") or {}
        slots = plan.get("slots") or []
        selected = None
        for action in slots:
            action_start = _parse_ts(
                action.get("slot_start_utc") or action.get("start")
            )
            if action_start is None:
                continue
            action_start_utc = action_start.astimezone(timezone.utc)
            action_end_utc = action_start_utc + timedelta(minutes=15)
            if action_start_utc <= anchor_utc < action_end_utc:
                selected = action
                break

        dedupe_key = (generated.isoformat(), (selected or {}).get("start"))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        realtime = context.get("realtime") or plan.get("realtime") or {}
        tesla_context = context.get("tesla") or {}
        deadline = tesla_context.get("deadline") or plan.get("deadlinePlan") or {}
        guardrails = plan.get("guardrails") or {}
        warm_water = context.get("warmWater") or {}
        out.append({
            "anchorLocal": anchor.isoformat(),
            "snapshotGeneratedAtLocal": generated.astimezone(LOCAL_TZ).isoformat(),
            "snapshotAgeMinutes": round(age_min, 1),
            "contextSource": context.get("contextSource"),
            "objective": snapshot.get("objective") or plan.get("objective"),
            "realtime": {
                "actualP1ExportW": realtime.get("actualP1ExportW"),
                "recentLocalAccuracy": realtime.get("recentLocalAccuracy"),
                "p1CorrectionPolicy": realtime.get("p1CorrectionPolicy"),
            },
            "deadline": {
                key: deadline.get(key)
                for key in (
                    "active", "connected", "remainingKWh", "deadlineAt",
                    "reserveNeedKWh", "reserveAddedKWh", "feasibleWithinVisibleHorizon",
                )
                if key in deadline
            },
            "guardrails": {
                key: guardrails.get(key)
                for key in (
                    "wwSourceMode", "wwElectricalFlexEligible", "wwSourceBlockReason",
                    "wwDeadlineLocal", "wwMinRunMinutes",
                    "quookerPolicy", "quookerModeledPowerW",
                    "quookerEnergyBudgetKWh", "quookerExpectedHeatMinutes",
                    "quookerOpportunityStartExportW",
                    "quookerOpportunityStopImportW",
                    "quookerWeekdayForcedLocal", "quookerWeekendForcedLocal",
                    "teslaRole", "evDeadlineHardConstraint",
                    "contractPolicyEnforced", "inputFreshnessFailClosed",
                )
                if key in guardrails
            },
            "warmWaterContext": {
                key: warm_water.get(key)
                for key in (
                    "date", "goalReached", "remainingFallbackMin",
                    "expectedDailyEnergyKWh", "plannedDemandMin",
                    "remainingPlannedDemandMin", "electricalRemainingDemandMin",
                    "heatingMinToday", "sourceMode", "electricalFlexEligible",
                    "sourceBlockReason", "requiredSlots", "allocatedSlots",
                    "comfortFeasible", "deadlineLocal", "allocationPolicy",
                )
                if key in warm_water
            },
            "action": _project_action(selected),
        })
    return out[-12:]



def _bool_db(value):
    if value is True:
        return 1
    if value is False:
        return 0
    return None


def _quooker_events(day):
    start, end = _bounds(day)
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='quooker_control_events'"
        ).fetchone()
        if not exists:
            return []

        available = {
            row[1] for row in db.execute(
                "PRAGMA table_info(quooker_control_events)"
            )
        }

        def column(name):
            return name if name in available else f"NULL AS {name}"

        selected = [
            "ts_utc",
            "control_mode",
            "control_target_on",
            "control_reason",
            "modeled_power_w",
            "avg_grid_w",
            "p1_fresh",
            "start_export_w",
            "stop_import_w",
            column("actuator_schema"),
            column("actuator_mode"),
            "actuator_control_valid",
            "actuator_control_fresh",
            "actuator_desired_on",
            "actuator_actual_on",
            column("actuator_actual_on_before"),
            column("actuator_actual_on_after"),
            "actuator_would_write",
            column("actuator_write_error"),
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
            column("raw_json"),
        ]
        rows = db.execute(
            f"""
            SELECT {",".join(selected)}
            FROM quooker_control_events
            WHERE ts_utc>=? AND ts_utc<?
            ORDER BY ts_utc
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()

    out = []
    for row in rows[-240:]:
        (
            ts_text, mode, target_on, control_reason,
            modeled_w, avg_grid_w, p1_fresh, start_export_w, stop_import_w,
            actuator_schema, actuator_mode, actuator_valid, actuator_fresh,
            desired_on, actual_on, actual_on_before, actual_on_after,
            would_write, actuator_write_error, actuator_reason,
            detector_valid, switch_on, active, detector_status,
            detector_power_w, detector_reason, last_heating_at,
            last_heating_power_w, physical_write, raw_json,
        ) = row

        raw_actuator = {}
        if raw_json:
            try:
                raw_payload = json.loads(raw_json)
                candidate = raw_payload.get("actuator")
                if isinstance(candidate, dict):
                    raw_actuator = candidate
            except (json.JSONDecodeError, TypeError):
                pass

        raw_safety = (
            raw_actuator.get("safety")
            if isinstance(raw_actuator.get("safety"), dict)
            else {}
        )
        actuator_schema = actuator_schema or raw_actuator.get("schema")
        actuator_mode = actuator_mode or raw_actuator.get("mode")
        if actual_on_before is None:
            actual_on_before = _bool_db(raw_actuator.get("actualOnBefore"))
        if actual_on_after is None:
            actual_on_after = _bool_db(raw_actuator.get("actualOnAfter"))
        if actual_on is None:
            actual_on = _bool_db(raw_actuator.get("actualOn"))
        if actuator_write_error is None:
            actuator_write_error = raw_actuator.get("writeError")
        if physical_write != 1 and (
            raw_actuator.get("physicalWritePerformed") is True
            or raw_safety.get("physicalWritePerformed") is True
        ):
            physical_write = 1

        if actuator_mode is None and would_write is not None:
            actuator_mode = "SHADOW"

        effective_actual = (
            actual_on_after
            if actual_on_after is not None
            else actual_on
            if actual_on is not None
            else actual_on_before
        )

        local = datetime.fromisoformat(
            ts_text.replace("Z", "+00:00")
        ).astimezone(LOCAL_TZ)
        out.append({
            "atLocal": local.isoformat(),
            "control": {
                "mode": mode,
                "targetOn": None if target_on is None else target_on == 1,
                "reason": control_reason,
                "modeledPowerW": modeled_w,
                "avgGridW": avg_grid_w,
                "p1Fresh": None if p1_fresh is None else p1_fresh == 1,
                "startExportW": start_export_w,
                "stopImportW": stop_import_w,
            },
            "actuator": {
                "schema": actuator_schema,
                "mode": actuator_mode or "UNKNOWN",
                "controlValid": None if actuator_valid is None else actuator_valid == 1,
                "controlFresh": None if actuator_fresh is None else actuator_fresh == 1,
                "desiredOn": None if desired_on is None else desired_on == 1,
                "actualOn": None if effective_actual is None else effective_actual == 1,
                "actualOnBefore": (
                    None if actual_on_before is None else actual_on_before == 1
                ),
                "actualOnAfter": (
                    None if actual_on_after is None else actual_on_after == 1
                ),
                "wouldWrite": None if would_write is None else would_write == 1,
                "physicalWritePerformed": physical_write == 1,
                "writeError": actuator_write_error,
                "reason": actuator_reason,
            },
            "detector": {
                "valid": None if detector_valid is None else detector_valid == 1,
                "switchOn": None if switch_on is None else switch_on == 1,
                "active": None if active is None else active == 1,
                "status": detector_status,
                "powerW": detector_power_w,
                "reason": detector_reason,
                "lastHeatingAt": last_heating_at,
                "lastHeatingPowerW": last_heating_power_w,
            },
            "physicalWritePerformed": physical_write == 1,
        })
    return out




def _semantic_events(day):
    start, end = _bounds(day)
    coverage = {
        "available": False,
        "schema": None,
        "commissionedAt": None,
        "historicalBackfill": False,
        "eventCount": 0,
        "oldestEventAt": None,
        "newestEventAt": None,
    }

    if not os.path.exists(HISTORY_DB):
        return [], coverage

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "semantic_events" not in tables:
            return [], coverage

        coverage["available"] = True
        if "semantic_event_meta" in tables:
            meta = dict(db.execute(
                "SELECT key,value_text FROM semantic_event_meta"
            ).fetchall())
            coverage["schema"] = meta.get("schema")
            commissioned = _parse_ts(meta.get("commissioned_at_utc"))
            coverage["commissionedAt"] = (
                commissioned.astimezone(LOCAL_TZ).isoformat()
                if commissioned is not None
                else meta.get("commissioned_at_utc")
            )

        stats = db.execute(
            """
            SELECT COUNT(*),MIN(ts_utc),MAX(ts_utc)
            FROM semantic_events
            """
        ).fetchone()
        coverage["eventCount"] = int(stats[0] or 0)
        coverage["oldestEventAt"] = stats[1]
        coverage["newestEventAt"] = stats[2]

        rows = db.execute(
            """
            SELECT
                ts_utc,event_type,domain,subject,state_key,
                provenance_class,source_name,source_at_utc,
                before_json,after_json,details_json
            FROM semantic_events
            WHERE ts_utc>=? AND ts_utc<?
            ORDER BY ts_utc,id
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()

    out = []
    for (
        ts_text,event_type,domain,subject,state_key,
        provenance,source_name,source_at,
        before_json,after_json,details_json,
    ) in rows:
        ts = _parse_ts(ts_text)
        if ts is None:
            continue

        def decode(value, fallback):
            if value is None:
                return fallback
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return fallback

        out.append({
            "atLocal": ts.astimezone(LOCAL_TZ).isoformat(),
            "eventType": event_type,
            "domain": domain,
            "subject": subject,
            "stateKey": state_key,
            "provenanceClass": provenance,
            "sourceName": source_name,
            "sourceAt": source_at,
            "before": decode(before_json, None),
            "after": decode(after_json, None),
            "details": decode(details_json, {}),
        })

    return out, coverage


def _flex_context_window(day, anchors):
    if not os.path.exists(PLANNER_DB) or not anchors:
        return []

    start, end = _bounds(day)
    query_start = start - timedelta(hours=2)
    with sqlite3.connect(f"file:{PLANNER_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='flex_context_snapshots'"
        ).fetchone()
        if not exists:
            return []
        rows = db.execute(
            """
            SELECT captured_at_utc,snapshot_zlib
            FROM flex_context_snapshots
            WHERE captured_at_utc>=? AND captured_at_utc<?
            ORDER BY captured_at_utc
            """,
            (_iso_z(query_start), _iso_z(end)),
        ).fetchall()

    snapshots = []
    for captured_text, blob in rows:
        captured = _parse_ts(captured_text)
        if captured is None:
            continue
        try:
            payload = json.loads(zlib.decompress(blob).decode("utf-8"))
        except (TypeError, ValueError, zlib.error, json.JSONDecodeError):
            continue
        if payload.get("schema") != "EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1":
            continue
        snapshots.append((captured.astimezone(timezone.utc), payload))

    out = []
    seen = set()
    for anchor in anchors:
        anchor_utc = anchor.astimezone(timezone.utc)
        eligible = [item for item in snapshots if item[0] <= anchor_utc]
        if not eligible:
            continue
        captured, payload = eligible[-1]
        age_min = (anchor_utc - captured).total_seconds() / 60.0
        if age_min > 30:
            continue

        dedupe = captured.isoformat()
        if dedupe in seen:
            continue
        seen.add(dedupe)
        item = dict(payload)
        item["anchorLocal"] = anchor.isoformat()
        item["snapshotCapturedAtLocal"] = captured.astimezone(LOCAL_TZ).isoformat()
        item["snapshotAgeMinutes"] = round(age_min, 1)
        out.append(item)

    return out[-12:]


def _forecast_vs_actual_15m(day, anchors):
    start, end = _bounds(day)
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "measurements_15m" not in tables or "pv_forecast_v2_archive" not in tables:
            return {
                "available": False,
                "reason": "CANONICAL_15M_OR_FORECAST_ARCHIVE_MISSING",
                "summary": {},
                "slots": [],
            }

        actual_rows = db.execute(
            """
            SELECT m.slot_start_utc,d.device_key,m.value_avg,m.energy_wh,m.quality
            FROM measurements_15m m
            JOIN devices d ON d.id=m.device_id
            JOIN metrics x ON x.id=m.metric_id
            WHERE m.slot_start_utc>=? AND m.slot_start_utc<?
              AND x.metric_key='electrical_power_w'
              AND d.device_key IN (
                'grid_p1','pv_solaredge','pv_goodwe4200','pv_goodwe2000',
                'tesla','boiler'
              )
              AND m.quality IN ('complete','partial')
            ORDER BY m.slot_start_utc
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()

        forecast_rows = db.execute(
            """
            SELECT f.slot_start_utc,f.forecast_w,f.confidence,f.model_basis,f.generated_at
            FROM pv_forecast_v2_archive f
            WHERE f.slot_start_utc>=? AND f.slot_start_utc<?
              AND f.generated_at = (
                SELECT MAX(f2.generated_at)
                FROM pv_forecast_v2_archive f2
                WHERE f2.slot_start_utc=f.slot_start_utc
                  AND julianday(f2.generated_at) <=
                      julianday(f.slot_start_utc) - (12.0/24.0)
              )
            ORDER BY f.slot_start_utc
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()

    slots = {}
    for slot_text, device_key, value_avg, energy_wh, quality in actual_rows:
        item = slots.setdefault(slot_text, {
            "pvEnergyWh": 0.0,
            "pvSeen": set(),
            "exportKWh": None,
            "evPowerW": None,
            "boilerPowerW": None,
            "qualities": set(),
        })
        item["qualities"].add(str(quality))
        if device_key.startswith("pv_") and energy_wh is not None:
            item["pvEnergyWh"] += max(0.0, float(energy_wh))
            item["pvSeen"].add(device_key)
        elif device_key == "grid_p1" and energy_wh is not None:
            item["exportKWh"] = round(max(0.0, -float(energy_wh) / 1000.0), 6)
        elif device_key == "tesla" and value_avg is not None:
            item["evPowerW"] = round(float(value_avg), 1)
        elif device_key == "boiler" and value_avg is not None:
            item["boilerPowerW"] = round(float(value_avg), 1)

    forecasts = {}
    for slot_text, forecast_w, confidence, model_basis, generated_at in forecast_rows:
        slot_dt = _parse_ts(slot_text)
        generated_dt = _parse_ts(generated_at)
        forecasts[slot_text] = {
            "forecastW": float(forecast_w),
            "confidence": confidence,
            "modelBasis": model_basis,
            "generatedAt": generated_at,
            "leadMinutes": (
                None if slot_dt is None or generated_dt is None
                else round((slot_dt - generated_dt).total_seconds() / 60.0, 1)
            ),
        }

    comparable = []
    details_by_key = {}
    required_pv = {"pv_solaredge", "pv_goodwe4200", "pv_goodwe2000"}
    for slot_text in sorted(set(slots) | set(forecasts)):
        actual = slots.get(slot_text) or {}
        forecast = forecasts.get(slot_text)
        pv_seen = actual.get("pvSeen") or set()
        pv_actual_kwh = (
            round(actual.get("pvEnergyWh", 0.0) / 1000.0, 6)
            if required_pv.issubset(pv_seen)
            else None
        )
        forecast_kwh = (
            None if forecast is None
            else round(forecast["forecastW"] * 0.25 / 1000.0, 6)
        )
        error_kwh = (
            None if pv_actual_kwh is None or forecast_kwh is None
            else round(pv_actual_kwh - forecast_kwh, 6)
        )
        actual_avg_w = (
            None if pv_actual_kwh is None
            else round(pv_actual_kwh * 4000.0, 1)
        )
        error_w = (
            None if actual_avg_w is None or forecast is None
            else round(actual_avg_w - forecast["forecastW"], 1)
        )
        detail = {
            "startLocal": (
                _parse_ts(slot_text).astimezone(LOCAL_TZ).isoformat()
                if _parse_ts(slot_text) is not None else slot_text
            ),
            "pvForecastW": None if forecast is None else round(forecast["forecastW"], 1),
            "pvActualAvgW": actual_avg_w,
            "pvForecastKWh": forecast_kwh,
            "pvActualKWh": pv_actual_kwh,
            "pvErrorKWhActualMinusForecast": error_kwh,
            "pvErrorWActualMinusForecast": error_w,
            "exportKWh": actual.get("exportKWh"),
            "evPowerW": actual.get("evPowerW"),
            "boilerPowerW": actual.get("boilerPowerW"),
            "forecastConfidence": None if forecast is None else forecast.get("confidence"),
            "forecastModelBasis": None if forecast is None else forecast.get("modelBasis"),
            "forecastGeneratedAt": None if forecast is None else forecast.get("generatedAt"),
            "forecastLeadMinutes": None if forecast is None else forecast.get("leadMinutes"),
            "actualQuality": sorted(actual.get("qualities") or []),
        }
        details_by_key[slot_text] = detail
        if error_w is not None:
            comparable.append((slot_text, detail))

    summary = {
        "selection": "FIXED_LEAD_12H_NO_HINDSIGHT",
        "slotCount": len(comparable),
        "forecastKWh": round(sum(x[1]["pvForecastKWh"] for x in comparable), 3)
            if comparable else 0.0,
        "actualKWh": round(sum(x[1]["pvActualKWh"] for x in comparable), 3)
            if comparable else 0.0,
        "biasKWhActualMinusForecast": round(
            sum(x[1]["pvErrorKWhActualMinusForecast"] for x in comparable), 3
        ) if comparable else 0.0,
        "meanAbsoluteErrorW": round(
            sum(abs(x[1]["pvErrorWActualMinusForecast"]) for x in comparable)
            / len(comparable), 1
        ) if comparable else None,
    }

    priority = []
    for anchor in anchors:
        anchor_utc = anchor.astimezone(timezone.utc)
        for slot_text in details_by_key:
            slot_dt = _parse_ts(slot_text)
            if slot_dt is not None and abs(
                (slot_dt.astimezone(timezone.utc) - anchor_utc).total_seconds()
            ) <= 30 * 60:
                priority.append(slot_text)

    priority.extend(
        key for key, detail in sorted(
            comparable,
            key=lambda item: abs(item[1]["pvErrorWActualMinusForecast"]),
            reverse=True,
        )[:8]
    )
    priority.extend(
        key for key, detail in sorted(
            details_by_key.items(),
            key=lambda item: item[1].get("exportKWh") or 0.0,
            reverse=True,
        )[:8]
    )

    selected = []
    seen = set()
    for key in priority:
        if key in seen:
            continue
        seen.add(key)
        selected.append(key)
        if len(selected) >= 24:
            break

    return {
        "available": bool(forecasts),
        "summary": summary,
        "slots": [details_by_key[key] for key in sorted(selected)],
    }


def build_evidence(day, question="", conversation_context=None):
    conversation_context = conversation_context or []
    performance = _load_performance(day)
    ev_control_all = _ev_control_events(day)

    explicit_anchors = _explicit_question_anchors(question, day)
    context_anchors = (
        []
        if explicit_anchors
        else _context_followup_anchors(
            question, day, conversation_context
        )
    )
    selected_time_anchors = explicit_anchors or context_anchors
    topics = _question_topics(question, conversation_context)

    if selected_time_anchors:
        anchors = selected_time_anchors
    else:
        anchors = _question_anchors(
            question, day, performance, ev_control_all
        )

    ev_telemetry_all = _ev_telemetry(day)
    quooker_events_all = _quooker_events(day)
    semantic_events_all, semantic_event_coverage = _semantic_events(day)
    timeline_all = _timeline(day)

    original_counts = {
        "timeline5m": len(timeline_all),
        "evTelemetry5m": len(ev_telemetry_all),
        "evControlEvents": len(ev_control_all),
        "quookerEvents": len(quooker_events_all),
        "semanticEvents": len(semantic_events_all),
    }

    timeline = list(timeline_all)
    ev_telemetry = list(ev_telemetry_all)
    ev_control = list(ev_control_all)
    quooker_events = list(quooker_events_all)
    semantic_events = list(semantic_events_all)
    compacted_fields = []
    omitted_fields = []

    if selected_time_anchors:
        timeline = _select_points_near_anchors(
            timeline_all, selected_time_anchors
        )
        ev_telemetry = _select_points_near_anchors(
            ev_telemetry_all, selected_time_anchors
        )
        ev_control = _select_points_near_anchors(
            ev_control_all, selected_time_anchors
        )
        quooker_events = _select_points_near_anchors(
            quooker_events_all, selected_time_anchors
        )
        semantic_events = _select_points_near_anchors(
            semantic_events_all, selected_time_anchors
        )
        mode = (
            "EXPLICIT_TIME_WINDOW"
            if explicit_anchors
            else "CONTEXT_TIME_WINDOW"
        )
    else:
        timeline = _bounded_points(
            timeline_all,
            DAY_SCOPE_LIMITS["timeline5m"],
            change_paths=(
                ("washerActive",),
                ("dryerActive",),
            ),
        )
        ev_telemetry = _bounded_points(
            ev_telemetry_all,
            DAY_SCOPE_LIMITS["evTelemetry5m"],
            change_paths=(
                ("connected",),
                ("charging",),
                ("observedPhaseMode",),
                ("chargeState",),
                ("deadlineActive",),
                ("managerDecision",),
                ("managerReason",),
            ),
        )
        ev_control = _bounded_points(
            ev_control_all,
            DAY_SCOPE_LIMITS["evControlEvents"],
            change_paths=(
                ("gateStatus",),
                ("actuatorStatus",),
                ("actuatorReason",),
                ("transitionStage",),
                ("transitionFailure",),
                ("chargeState",),
                ("deviceHealthStatus",),
                ("phaseMode",),
                ("intentReason",),
                ("realtimePhaseReason",),
                ("realtimeCurrentReason",),
            ("easeeRequestedA",),
            ("easeeOfferedA",),
            ("easeeMeasureW",),
            ("equalizerPhaseCurrentsA", "l1"),
            ("equalizerPhaseCurrentsA", "l2"),
            ("equalizerPhaseCurrentsA", "l3"),
            ),
            important=lambda point: bool(
                point.get("physicalWritePerformed")
                or point.get("transitionFailure")
                or point.get("gateErrors")
            ),
        )
        quooker_events = _bounded_points(
            quooker_events_all,
            DAY_SCOPE_LIMITS["quookerEvents"],
            change_paths=(
                ("control", "targetOn"),
                ("actuator", "mode"),
                ("actuator", "actualOn"),
                ("detector", "active"),
                ("detector", "status"),
                ("physicalWritePerformed",),
            ),
            important=lambda point: bool(
                point.get("physicalWritePerformed")
                or (point.get("actuator") or {}).get("writeError")
            ),
        )

        semantic_events = _bounded_points(
            semantic_events_all,
            DAY_SCOPE_LIMITS["semanticEvents"],
            change_paths=(
                ("eventType",),
                ("domain",),
                ("subject",),
            ),
            important=lambda point: (
                point.get("provenanceClass") == "USER_INTENT_COMMAND"
            ),
        )

        for field, before, after in (
            ("timeline5m", timeline_all, timeline),
            ("evTelemetry5m", ev_telemetry_all, ev_telemetry),
            ("evControlEvents", ev_control_all, ev_control),
            ("quookerEvents", quooker_events_all, quooker_events),
            ("semanticEvents", semantic_events_all, semantic_events),
        ):
            if len(after) < len(before):
                compacted_fields.append(field)

        mode = "TOPIC_DAY_SCOPE" if topics else "DAY_SCOPE_COMPACT"

    # Time scoping answers *when* to look; topic routing answers *which*
    # subsystem evidence is relevant. Apply topic routing after either
    # selection path so CONTEXT_TIME_WINDOW/EXPLICIT_TIME_WINDOW do not
    # accidentally carry unrelated EV or Quooker streams.
    if topics:
        if "EV" not in topics:
            if ev_telemetry:
                omitted_fields.append("evTelemetry5m")
            if ev_control:
                omitted_fields.append("evControlEvents")
            ev_telemetry = []
            ev_control = []
        if "QUOOKER" not in topics:
            if quooker_events:
                omitted_fields.append("quookerEvents")
            quooker_events = []

        if "PV_FLEX" not in topics:
            allowed_semantic_domains = set()
            if "EV" in topics:
                allowed_semantic_domains.update(("EV", "FLEX"))
            if "HEATING_WW" in topics:
                allowed_semantic_domains.update(
                    ("HEATING", "WARM_WATER", "FLEX")
                )
            filtered_semantic = [
                event for event in semantic_events
                if event.get("domain") in allowed_semantic_domains
            ]
            if len(filtered_semantic) < len(semantic_events):
                omitted_fields.append("semanticEvents")
            semantic_events = filtered_semantic

    health = _load_health()
    planner_window = _planner_decision_window(day, anchors)
    flex_context_all = _flex_context_window(day, anchors)

    if selected_time_anchors:
        flex_context = flex_context_all
    else:
        flex_context = _bounded_points(
            flex_context_all,
            DAY_SCOPE_LIMITS["flexContextWindow"],
        )
        if len(flex_context) < len(flex_context_all):
            compacted_fields.append("flexContextWindow")

    _annotate_deadline_semantics(
        ev_telemetry, planner_window, flex_context
    )
    forecast_actual = _forecast_vs_actual_15m(day, anchors)

    selected_counts = {
        "timeline5m": len(timeline),
        "evTelemetry5m": len(ev_telemetry),
        "evControlEvents": len(ev_control),
        "quookerEvents": len(quooker_events),
        "semanticEvents": len(semantic_events),
        "flexContextWindow": len(flex_context),
    }
    original_counts["flexContextWindow"] = len(flex_context_all)

    selection = {
        "mode": mode,
        "topics": topics,
        "conversationContextMessages": len(conversation_context),
        "explicitTimeAnchorsLocal": [
            anchor.isoformat() for anchor in explicit_anchors
        ],
        "contextTimeAnchorsLocal": [
            anchor.isoformat() for anchor in context_anchors
        ],
        "windowMinutesBefore": (
            EXPLICIT_TIME_WINDOW_MINUTES
            if selected_time_anchors
            else None
        ),
        "windowMinutesAfter": (
            EXPLICIT_TIME_WINDOW_MINUTES
            if selected_time_anchors
            else None
        ),
        "scopedFields": (
            [
                "timeline5m",
                "evTelemetry5m",
                "evControlEvents",
                "quookerEvents",
                "semanticEvents",
            ]
            if selected_time_anchors
            else []
        ),
        "compactedFields": sorted(set(compacted_fields)),
        "omittedFields": sorted(set(omitted_fields)),
        "originalCounts": original_counts,
        "selectedCounts": selected_counts,
    }

    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "generatedAt": _iso_z(datetime.now(timezone.utc)),
        "dateLocal": day.isoformat(),
        "sourceAuthority": {
            "measurements": "ems-history.sqlite",
            "evTelemetry": "Homey canonical state push -> ems-history.sqlite",
            "evControlEvents": "Homey observability LAN push -> ems-history.sqlite",
            "quookerEvents": "Homey Quooker observability LAN push -> ems-history.sqlite",
            "semanticEvents": "Pi-local semantic observer -> ems-history.sqlite semantic_events",
            "planner": "planner-history.sqlite frozen decision snapshots",
            "flexContext": "Pi-local Heating/WW shadow archive -> planner-history.sqlite",
            "forecastComparison": "pv_forecast_v2_archive fixed 12h lead + canonical measurements_15m",
            "performance": "EMS_PI_DAY_PERFORMANCE_V0.1",
            "currentHealth": "EMS_PI_HEALTH_V0.1 via ems-health",
        },
        "analysisAnchorsLocal": [anchor.isoformat() for anchor in anchors],
        "evidenceSelection": selection,
        "performance": performance,
        "timeline5m": timeline,
        "evTelemetry5m": ev_telemetry,
        "evControlEvents": ev_control,
        "quookerEvents": quooker_events,
        "semanticEvents": semantic_events,
        "semanticEventCoverage": semantic_event_coverage,
        "plannerDecisionWindow": planner_window,
        "flexContextWindow": flex_context,
        "forecastVsActual15m": forecast_actual,
        "piHealthCurrent": health,
        "limitations": [
            "For today, full-calendar-day coverage is not evidence completeness. Use coveragePctElapsed and elapsedCoverageStatus to judge elapsed-time measurement coverage.",
            "Recent conversation context is referential context only and is not EMS evidence. Factual claims still require support from the current evidence package.",
            "When evidenceSelection.mode is EXPLICIT_TIME_WINDOW or CONTEXT_TIME_WINDOW, timeline5m, evTelemetry5m, evControlEvents and quookerEvents are intentionally scoped to the documented local window; absence outside that window is not evidence of no activity.",
            "When evidenceSelection.mode is TOPIC_DAY_SCOPE or DAY_SCOPE_COMPACT, compactedFields are bounded samples across the day and omittedFields were intentionally excluded as unrelated to the question; absence or omission is not evidence of no activity.",
            "evidenceSelection.inputBudget uses a conservative UTF-8 byte-based token estimate rather than the model tokenizer. If budget compaction is applied, budgetCompactedFields records the additional deterministic reductions; HARD_LIMIT_EXCEEDED prevents the model call.",
            "EV deadline values may retain historical deadlineAt/remainingKWh metadata after the constraint becomes inactive; deadlineSemantics.effective is the authority for whether those values constrain the referenced decision time.",
            "EV telemetry and control-event history only exist from their V0.2 commissioning onward; earlier gaps must not be backfilled by inference.",
            "Heating/WW flex-context history only exists from V0.4 flex-context archive commissioning onward; earlier gaps must not be backfilled from current JSON.",
            "Quooker adapter/actuator/detector history only exists from V0.4 Quooker evidence-push commissioning onward; earlier gaps must not be backfilled from current Homey Logic.",
            "Semantic event history begins at semanticEventCoverage.commissionedAt. Initial state is baseline-only and creates no synthetic event; absence before commissioning or at baseline is not proof that no change occurred.",
            "Semantic event provenance is explicit: USER_INTENT_COMMAND records intent but not physical execution; OBSERVED_STATE does not identify the actor; DERIVED_STATE is Pi-derived; SHADOW_DECISION is not a physical write.",
            "Heating progression remains SHADOW. Quooker actuator mode is evidence-driven: SHADOW desiredOn/wouldWrite does not prove a physical command; LIVE physicalWritePerformed=true does.",
            "For Quooker LIVE evidence, physicalWritePerformed=false can be an idempotent no-op when the requested state already matched; use actualOnBefore/actualOnAfter plus detector evidence for context.",
            "If a historical Quooker event has actuator.mode=UNKNOWN, do not infer a physical write from detector HEATING alone.",
            "Planner decision windows use the latest frozen snapshot at or before each analysis anchor; missing snapshots remain missing.",
            "PV forecast comparison uses a fixed 12-hour no-hindsight archive selection and must not substitute a later forecast.",
            "Observed phase mode is derived from measured phase currents; use explicit actuator/gate phase fields when control-event evidence exists.",
            "Current Pi health does not prove health at an earlier historical decision timestamp.",
            "Recent incident evidence is best-effort journal coverage until durable incident history is implemented.",
            "Export windows are observations and require constraint context before classifying them as missed opportunities.",
        ],
    }
    return _apply_model_input_budget(
        evidence,
        question,
        conversation_context,
    )

def _job_now():
    return datetime.now(timezone.utc)


def _ensure_job_schema(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_jobs (
            request_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            day_local TEXT NOT NULL,
            status TEXT NOT NULL,
            response_json TEXT,
            error_reason TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_jobs_updated
        ON analysis_jobs(updated_at_utc)
        """
    )


def _validate_request_id(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("REQUEST_ID_INVALID")
    value = value.strip()
    if (
        not value
        or len(value) > MAX_REQUEST_ID_CHARS
        or _REQUEST_ID_RE.fullmatch(value) is None
    ):
        raise ValueError("REQUEST_ID_INVALID")
    return value


def _job_cleanup(db, now):
    cutoff = _iso_z(now - timedelta(hours=JOB_RETENTION_HOURS))
    db.execute(
        "DELETE FROM analysis_jobs WHERE updated_at_utc < ?",
        (cutoff,),
    )


def _job_is_active(request_id):
    with _ACTIVE_JOB_LOCK:
        return request_id in _ACTIVE_JOB_IDS


def _job_release(request_id):
    with _ACTIVE_JOB_LOCK:
        _ACTIVE_JOB_IDS.discard(request_id)


def _job_claim(request_id, question, day):
    now = _job_now()
    now_text = _iso_z(now)
    day_text = day.isoformat()

    with _ACTIVE_JOB_LOCK:
        return _job_claim_locked(request_id, question, day_text, now, now_text)


def _job_claim_locked(request_id, question, day_text, now, now_text):
    with sqlite3.connect(JOBS_DB, timeout=3.0) as db:
        db.execute("PRAGMA busy_timeout=3000")
        _ensure_job_schema(db)
        _job_cleanup(db, now)
        cur = db.execute(
            """
            INSERT OR IGNORE INTO analysis_jobs (
                request_id,question,day_local,status,
                response_json,error_reason,created_at_utc,updated_at_utc
            )
            VALUES (?, ?, ?, 'PENDING', NULL, NULL, ?, ?)
            """,
            (request_id, question, day_text, now_text, now_text),
        )
        if cur.rowcount == 1:
            _ACTIVE_JOB_IDS.add(request_id)
            db.commit()
            return {"claimed": True, "status": "PENDING"}

        row = db.execute(
            """
            SELECT question,day_local,status,response_json,error_reason,updated_at_utc
            FROM analysis_jobs
            WHERE request_id=?
            """,
            (request_id,),
        ).fetchone()

        if row is None:
            raise RuntimeError("ANALYSIS_JOB_LOOKUP_FAILED")

        old_question, old_day, status, response_json, error_reason, updated_text = row
        if old_question != question or old_day != day_text:
            raise ValueError("REQUEST_ID_CONFLICT")

        if status == "PENDING":
            active_here = request_id in _ACTIVE_JOB_IDS
            updated = _parse_ts(updated_text)
            stale = (
                not active_here
                and (
                    updated is None
                    or (now - updated.astimezone(timezone.utc)).total_seconds()
                    > JOB_PENDING_STALE_SECONDS
                )
            )
            if stale:
                db.execute(
                    """
                    UPDATE analysis_jobs
                    SET response_json=NULL,error_reason=NULL,updated_at_utc=?
                    WHERE request_id=?
                    """,
                    (now_text, request_id),
                )
                _ACTIVE_JOB_IDS.add(request_id)
                db.commit()
                return {"claimed": True, "status": "PENDING", "reclaimed": True}

        db.commit()
        return {
            "claimed": False,
            "status": status,
            "response": (
                json.loads(response_json)
                if status == "OK" and response_json
                else None
            ),
            "reason": error_reason,
        }


def _job_complete(request_id, response):
    now_text = _iso_z(_job_now())
    encoded = json.dumps(
        response, separators=(",", ":"), ensure_ascii=False
    )
    try:
        with sqlite3.connect(JOBS_DB, timeout=3.0) as db:
            db.execute("PRAGMA busy_timeout=3000")
            _ensure_job_schema(db)
            db.execute(
                """
                UPDATE analysis_jobs
                SET status='OK',response_json=?,error_reason=NULL,updated_at_utc=?
                WHERE request_id=?
                """,
                (encoded, now_text, request_id),
            )
            db.commit()
    finally:
        _job_release(request_id)


def _job_fail(request_id, reason):
    now_text = _iso_z(_job_now())
    try:
        with sqlite3.connect(JOBS_DB, timeout=3.0) as db:
            db.execute("PRAGMA busy_timeout=3000")
            _ensure_job_schema(db)
            db.execute(
                """
                UPDATE analysis_jobs
                SET status='ERROR',response_json=NULL,error_reason=?,updated_at_utc=?
                WHERE request_id=?
                """,
                (str(reason)[:500], now_text, request_id),
            )
            db.commit()
    finally:
        _job_release(request_id)


def _job_get(request_id):
    with sqlite3.connect(JOBS_DB, timeout=3.0) as db:
        db.execute("PRAGMA busy_timeout=3000")
        _ensure_job_schema(db)
        row = db.execute(
            """
            SELECT status,response_json,error_reason,updated_at_utc
            FROM analysis_jobs
            WHERE request_id=?
            """,
            (request_id,),
        ).fetchone()

    if row is None:
        return None

    status, response_json, error_reason, updated_at = row
    public_status = status
    if status == "PENDING" and not _job_is_active(request_id):
        updated = _parse_ts(updated_at)
        if (
            updated is None
            or (_job_now() - updated.astimezone(timezone.utc)).total_seconds()
            > JOB_PENDING_STALE_SECONDS
        ):
            public_status = "STALE"

    return {
        "status": public_status,
        "response": (
            json.loads(response_json)
            if status == "OK" and response_json
            else None
        ),
        "reason": error_reason,
        "updatedAt": updated_at,
    }


def _evidence_summary(evidence):
    return {
        "performanceSchema": evidence["performance"].get("schema"),
        "timelinePoints": len(evidence["timeline5m"]),
        "evTelemetryPoints": len(evidence["evTelemetry5m"]),
        "evControlEvents": len(evidence["evControlEvents"]),
        "quookerEvents": len(evidence["quookerEvents"]),
        "plannerDecisionPoints": len(evidence["plannerDecisionWindow"]),
        "flexContextPoints": len(evidence["flexContextWindow"]),
        "forecastComparisonSlots": len(
            evidence["forecastVsActual15m"].get("slots") or []
        ),
        "piHealthStatus": evidence["piHealthCurrent"].get("status"),
        "evidenceSelectionMode": (
            evidence.get("evidenceSelection") or {}
        ).get("mode"),
        "evidenceSelectionTopics": (
            evidence.get("evidenceSelection") or {}
        ).get("topics") or [],
        "conversationContextMessages": (
            evidence.get("evidenceSelection") or {}
        ).get("conversationContextMessages") or 0,
        "inputBudget": (
            evidence.get("evidenceSelection") or {}
        ).get("inputBudget"),
        "limitations": evidence["limitations"],
    }


def _analysis_response(day, answer, response_id, evidence, request_id=None):
    result = {
        "schema": SCHEMA,
        "status": "OK",
        "readOnly": True,
        "controlWrites": False,
        "dateLocal": day.isoformat(),
        "model": MODEL,
        "modelResponseId": response_id,
        "answer": answer,
        "evidenceSummary": _evidence_summary(evidence),
    }
    if request_id is not None:
        result["requestId"] = request_id
    return result


def _extract_output_text(payload):
    texts = []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return "\n".join(texts).strip()


def _model_refusal_present(payload):
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                return True
    return False


def _model_failure_reason(payload):
    status = str(payload.get("status") or "").strip().lower()
    incomplete = payload.get("incomplete_details") or {}
    incomplete_reason = str(incomplete.get("reason") or "").strip().lower()

    if status == "incomplete":
        if incomplete_reason == "max_output_tokens":
            return "MODEL_INCOMPLETE_MAX_OUTPUT_TOKENS"
        if incomplete_reason == "content_filter":
            return "MODEL_INCOMPLETE_CONTENT_FILTER"
        return "MODEL_INCOMPLETE"

    if _model_refusal_present(payload):
        return "MODEL_REFUSED"

    error = payload.get("error") or {}
    if isinstance(error, dict) and error:
        error_code = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            str(error.get("code") or "").strip(),
        )[:80]
        if error_code:
            return "MODEL_RESPONSE_ERROR:" + error_code
        return "MODEL_RESPONSE_ERROR"

    if status == "completed":
        return "MODEL_EMPTY_RESPONSE_COMPLETED"
    return "MODEL_EMPTY_RESPONSE"


def _model_token_usage(payload):
    usage = payload.get("usage") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "inputTokens": usage.get("input_tokens"),
        "outputTokens": usage.get("output_tokens"),
        "reasoningTokens": output_details.get("reasoning_tokens"),
        "totalTokens": usage.get("total_tokens"),
    }


def _model_response_diagnostics(payload, reason, duration_ms=None):
    incomplete = payload.get("incomplete_details") or {}
    error = payload.get("error") or {}
    result = {
        "event": "EMS_AI_MODEL_RESPONSE_FAILURE",
        "reason": reason,
        "responseId": payload.get("id"),
        "status": payload.get("status"),
        "durationMs": duration_ms,
        "incompleteReason": incomplete.get("reason"),
        "errorCode": error.get("code") if isinstance(error, dict) else None,
        "refusalPresent": _model_refusal_present(payload),
    }
    result.update(_model_token_usage(payload))
    return result


def _model_success_diagnostics(payload, duration_ms):
    result = {
        "event": "EMS_AI_MODEL_RESPONSE_SUCCESS",
        "responseId": payload.get("id"),
        "status": payload.get("status"),
        "durationMs": duration_ms,
    }
    result.update(_model_token_usage(payload))
    return result


def _raise_model_response_failure(payload, duration_ms=None):
    reason = _model_failure_reason(payload)
    print(
        json.dumps(
            _model_response_diagnostics(payload, reason, duration_ms),
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        flush=True,
    )
    raise RuntimeError(reason)


def ask_model(question, evidence, conversation_context=None):
    if not OPENAI_API_KEY:
        raise RuntimeError("MODEL_NOT_CONFIGURED")

    estimated, _ = _estimate_model_input_tokens(
        question, evidence, conversation_context
    )
    if estimated > MODEL_INPUT_HARD_LIMIT_TOKENS:
        raise RuntimeError("MODEL_INPUT_BUDGET_EXCEEDED")

    body = json.dumps({
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": _model_input_text(
            question, evidence, conversation_context
        ),
        "reasoning": {
            "effort": REASONING_EFFORT,
            "mode": "standard",
        },
        "max_output_tokens": MAX_OUTPUT_TOKENS,
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
    model_started = monotonic()
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

    duration_ms = round((monotonic() - model_started) * 1000)
    answer = _extract_output_text(payload)
    if not answer:
        _raise_model_response_failure(payload, duration_ms)
    print(
        json.dumps(
            _model_success_diagnostics(payload, duration_ms),
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        flush=True,
    )
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
        try:
            handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The browser may navigate away while a model request finishes.
            # The result is already persisted when requestId was supplied.
            return

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

        if path.path == "/agent/result":
            query = parse_qs(path.query, keep_blank_values=False)
            values = query.get("requestId") or []
            try:
                request_id = _validate_request_id(values[0] if len(values) == 1 else None)
            except ValueError as exc:
                send_json(self, 400, {
                    "schema": SCHEMA,
                    "status": "ERROR",
                    "reason": str(exc),
                })
                return
            if request_id is None:
                send_json(self, 400, {
                    "schema": SCHEMA,
                    "status": "ERROR",
                    "reason": "REQUEST_ID_REQUIRED",
                })
                return

            try:
                job = _job_get(request_id)
            except sqlite3.Error:
                send_json(self, 500, {
                    "schema": SCHEMA,
                    "status": "UNAVAILABLE",
                    "reason": "ANALYSIS_JOB_STORE_FAILED",
                })
                return

            if job is None:
                send_json(self, 404, {
                    "schema": SCHEMA,
                    "status": "NOT_FOUND",
                    "requestId": request_id,
                })
                return
            if job["status"] == "PENDING":
                send_json(self, 202, {
                    "schema": SCHEMA,
                    "status": "PENDING",
                    "requestId": request_id,
                    "updatedAt": job.get("updatedAt"),
                })
                return
            if job["status"] == "STALE":
                send_json(self, 409, {
                    "schema": SCHEMA,
                    "status": "STALE",
                    "requestId": request_id,
                    "updatedAt": job.get("updatedAt"),
                })
                return
            if job["status"] == "OK" and isinstance(job.get("response"), dict):
                send_json(self, 200, job["response"])
                return

            send_json(self, 200, {
                "schema": SCHEMA,
                "status": "ERROR",
                "requestId": request_id,
                "reason": job.get("reason") or "ANALYSIS_FAILED",
            })
            return

        send_json(self, 404, {
            "schema": SCHEMA,
            "status": "ERROR",
            "reason": "NOT_FOUND",
        })

    def do_POST(self):
        path = urlsplit(self.path)
        if path.path != "/agent/ask" or path.query:
            send_json(self, 404, {
                "schema": SCHEMA,
                "status": "ERROR",
                "reason": "NOT_FOUND",
            })
            return

        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            send_json(self, 413, {
                "schema": SCHEMA,
                "status": "ERROR",
                "reason": "REQUEST_TOO_LARGE",
            })
            return

        request_id = None
        claimed_job = False
        try:
            request_payload = json.loads(self.rfile.read(length).decode("utf-8"))
            question = request_payload.get("question")
            if (
                not isinstance(question, str)
                or not question.strip()
                or len(question) > MAX_QUESTION_CHARS
            ):
                raise ValueError("QUESTION_INVALID")
            question = question.strip()
            day = _resolve_day(request_payload.get("day"))
            request_id = _validate_request_id(request_payload.get("requestId"))
            conversation_context = _validate_conversation_context(
                request_payload.get("conversationContext")
            )

            if request_id is not None:
                job = _job_claim(request_id, question, day)
                if not job["claimed"]:
                    if job["status"] == "OK" and isinstance(job.get("response"), dict):
                        send_json(self, 200, job["response"])
                        return
                    if job["status"] == "PENDING":
                        send_json(self, 202, {
                            "schema": SCHEMA,
                            "status": "PENDING",
                            "requestId": request_id,
                        })
                        return
                    send_json(self, 503, {
                        "schema": SCHEMA,
                        "status": "UNAVAILABLE",
                        "requestId": request_id,
                        "reason": job.get("reason") or "ANALYSIS_FAILED",
                    })
                    return
                claimed_job = True

            evidence = build_evidence(
                day, question, conversation_context
            )
            answer, response_id = ask_model(
                question, evidence, conversation_context
            )
            result = _analysis_response(
                day, answer, response_id, evidence, request_id=request_id
            )

            # Persist before writing the HTTP response. If the user navigates
            # away, the model result remains retrievable by requestId.
            if request_id is not None:
                _job_complete(request_id, result)

            send_json(self, 200, result)

        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json(self, 400, {
                "schema": SCHEMA,
                "status": "ERROR",
                "reason": "JSON_INVALID",
            })
        except ValueError as exc:
            if request_id is not None and claimed_job:
                try:
                    _job_fail(request_id, str(exc))
                except sqlite3.Error:
                    pass
            send_json(self, 400, {
                "schema": SCHEMA,
                "status": "ERROR",
                "reason": str(exc),
            })
        except (OSError, sqlite3.Error, subprocess.SubprocessError, RuntimeError) as exc:
            reason = str(exc)
            if request_id is not None and claimed_job:
                try:
                    _job_fail(request_id, reason)
                except sqlite3.Error:
                    pass
            status = 503 if reason.startswith("MODEL_") or reason in {
                "TIMELINE_SOURCE_INCOMPLETE",
            } or reason.startswith("EMS_PERFORMANCE_FAILED") else 500
            send_json(self, status, {
                "schema": SCHEMA,
                "status": "UNAVAILABLE",
                "requestId": request_id,
                "reason": reason,
            })
        finally:
            if request_id is not None and claimed_job:
                _job_release(request_id)

    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

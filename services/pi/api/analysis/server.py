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
import zlib
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
JOB_RETENTION_HOURS = 24
JOB_PENDING_STALE_SECONDS = 180
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")

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
Use plannerDecisionWindow as historical intent evidence and never judge an earlier planner decision using a forecast generated later.
Use forecastVsActual15m to distinguish forecast error from planner/control execution error when the evidence supports that distinction.
Use flexContextWindow for historical Heating/WW eligibility and priority, and quookerEvents for Quooker adapter/actuator/detector evidence.
Heating progression and the Quooker actuator are SHADOW unless evidence explicitly proves otherwise: a shadow grant, desired target or wouldWrite is not a physical command.
Never backfill missing pre-commissioning flex or Quooker history by inference.
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


def _question_anchors(question, day, performance, ev_control):
    anchors = []
    for match in _TIME_RE.finditer(question or ""):
        anchors.append(datetime.combine(
            day,
            time(int(match.group(1)), int(match.group(2))),
            LOCAL_TZ,
        ))

    if not anchors:
        for window in (performance.get("surplusWindowsForReplay") or [])[:3]:
            dt = _parse_ts(window.get("start"))
            if dt is not None:
                anchors.append(dt.astimezone(LOCAL_TZ))
        for event in (ev_control or [])[-3:]:
            dt = _parse_ts(event.get("atLocal"))
            if dt is not None:
                anchors.append(dt.astimezone(LOCAL_TZ))

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
        rows = db.execute(
            """
            SELECT
                ts_utc,control_mode,control_target_on,control_reason,
                modeled_power_w,avg_grid_w,p1_fresh,start_export_w,stop_import_w,
                actuator_control_valid,actuator_control_fresh,
                actuator_desired_on,actuator_actual_on,actuator_would_write,
                actuator_reason,detector_valid,detector_switch_on,
                detector_active,detector_status,detector_power_w,
                detector_reason,detector_last_heating_at,
                detector_last_heating_power_w,physical_write_performed
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
            actuator_valid, actuator_fresh, desired_on, actual_on, would_write,
            actuator_reason, detector_valid, switch_on, active, detector_status,
            detector_power_w, detector_reason, last_heating_at,
            last_heating_power_w, physical_write,
        ) = row
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
            "actuatorShadow": {
                "controlValid": None if actuator_valid is None else actuator_valid == 1,
                "controlFresh": None if actuator_fresh is None else actuator_fresh == 1,
                "desiredOn": None if desired_on is None else desired_on == 1,
                "actualOn": None if actual_on is None else actual_on == 1,
                "wouldWrite": None if would_write is None else would_write == 1,
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


def build_evidence(day, question=""):
    performance = _load_performance(day)
    ev_telemetry = _ev_telemetry(day)
    ev_control = _ev_control_events(day)
    anchors = _question_anchors(question, day, performance, ev_control)
    health = _load_health()
    planner_window = _planner_decision_window(day, anchors)
    flex_context = _flex_context_window(day, anchors)
    quooker_events = _quooker_events(day)
    forecast_actual = _forecast_vs_actual_15m(day, anchors)
    return {
        "schema": EVIDENCE_SCHEMA,
        "generatedAt": _iso_z(datetime.now(timezone.utc)),
        "dateLocal": day.isoformat(),
        "sourceAuthority": {
            "measurements": "ems-history.sqlite",
            "evTelemetry": "Homey canonical state push -> ems-history.sqlite",
            "evControlEvents": "Homey observability LAN push -> ems-history.sqlite",
            "quookerEvents": "Homey Quooker observability LAN push -> ems-history.sqlite",
            "planner": "planner-history.sqlite frozen decision snapshots",
            "flexContext": "Pi-local Heating/WW shadow archive -> planner-history.sqlite",
            "forecastComparison": "pv_forecast_v2_archive fixed 12h lead + canonical measurements_15m",
            "performance": "EMS_PI_DAY_PERFORMANCE_V0.1",
            "currentHealth": "EMS_PI_HEALTH_V0.1 via ems-health",
        },
        "analysisAnchorsLocal": [anchor.isoformat() for anchor in anchors],
        "performance": performance,
        "timeline5m": _timeline(day),
        "evTelemetry5m": ev_telemetry,
        "evControlEvents": ev_control,
        "quookerEvents": quooker_events,
        "plannerDecisionWindow": planner_window,
        "flexContextWindow": flex_context,
        "forecastVsActual15m": forecast_actual,
        "piHealthCurrent": health,
        "limitations": [
            "EV telemetry and control-event history only exist from their V0.2 commissioning onward; earlier gaps must not be backfilled by inference.",
            "Heating/WW flex-context history only exists from V0.4 flex-context archive commissioning onward; earlier gaps must not be backfilled from current JSON.",
            "Quooker adapter/actuator/detector history only exists from V0.4 Quooker evidence-push commissioning onward; earlier gaps must not be backfilled from current Homey Logic.",
            "Heating progression and Quooker actuator evidence are SHADOW: grant, desiredOn and wouldWrite do not prove a physical command or device change.",
            "Planner decision windows use the latest frozen snapshot at or before each analysis anchor; missing snapshots remain missing.",
            "PV forecast comparison uses a fixed 12-hour no-hindsight archive selection and must not substitute a later forecast.",
            "Observed phase mode is derived from measured phase currents; use explicit actuator/gate phase fields when control-event evidence exists.",
            "Current Pi health does not prove health at an earlier historical decision timestamp.",
            "Recent incident evidence is best-effort journal coverage until durable incident history is implemented.",
            "Export windows are observations and require constraint context before classifying them as missed opportunities.",
        ],
    }


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


def _job_claim(request_id, question, day):
    now = _job_now()
    now_text = _iso_z(now)
    day_text = day.isoformat()

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
            updated = _parse_ts(updated_text)
            stale = (
                updated is None
                or (now - updated.astimezone(timezone.utc)).total_seconds()
                > JOB_PENDING_STALE_SECONDS
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


def _job_fail(request_id, reason):
    now_text = _iso_z(_job_now())
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
    return {
        "status": status,
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

def ask_model(question, evidence):
    if not OPENAI_API_KEY:
        raise RuntimeError("MODEL_NOT_CONFIGURED")
    body = json.dumps({
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": "Vraag:\n" + question + "\n\nEMS evidence JSON:\n" + json.dumps(evidence, ensure_ascii=False),
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

            evidence = build_evidence(day, question)
            answer, response_id = ask_model(question, evidence)
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
            status = 503 if reason in {
                "MODEL_NOT_CONFIGURED", "MODEL_UNAVAILABLE",
                "TIMELINE_SOURCE_INCOMPLETE", "MODEL_EMPTY_RESPONSE"
            } or reason.startswith("MODEL_HTTP_") or reason.startswith(
                "EMS_PERFORMANCE_FAILED"
            ) else 500
            send_json(self, status, {
                "schema": SCHEMA,
                "status": "UNAVAILABLE",
                "requestId": request_id,
                "reason": reason,
            })

    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

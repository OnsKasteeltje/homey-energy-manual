#!/usr/bin/env python3
"""Deterministic read-only constrained replay for EMS export analysis.

V0.1 is deliberately EV-only. It classifies observed grid export intervals as:

- UNAVOIDABLE_EXPORT
- CONSTRAINT_DRIVEN_EXPORT
- REAL_MISSED_OPPORTUNITY
- INSUFFICIENT_EVIDENCE

The replay never asks an LLM to decide feasibility. Classification is derived
from canonical measurement history plus durable EV control evidence. The
result is analysis-only and is never consumed by planner, Gate or actuator.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
DATA = Path("/home/jeroen/ems/data")
HISTORY_DB = DATA / "ems-history.sqlite"

SCHEMA = "EMS_PI_CONSTRAINED_REPLAY_V0.1.1"
SCOPE = "EV_EXPORT_ONLY"

MIN_EXPORT_W = 250.0
MAX_MEASUREMENT_INTERVAL_S = 600.0
PREFERRED_ATTRIBUTION_INTERVAL_S = 120.0
HIGH_CONFIDENCE_CONTROL_EVENT_AGE_S = 90.0

MIN_A = 6
MAX_A = 16
W_PER_A_1P = 230.0
W_PER_A_3P = 690.0
IMPORT_TARGET_W = 300.0
PHASE_MARGIN_W = 250.0
DEFAULT_START_1P_W = 1500.0
DEFAULT_ENTER_3P_W = 4400.0
DEFAULT_OFF_REENTRY_DWELL_MS = 120000.0
DEFAULT_1P_TO_3P_DWELL_MS = 180000.0

CONNECTED_STATES = {
    "plugged_in",
    "plugged_in_paused",
    "plugged_in_charging",
}

CLASS_UNAVOIDABLE = "UNAVOIDABLE_EXPORT"
CLASS_CONSTRAINT = "CONSTRAINT_DRIVEN_EXPORT"
CLASS_MISSED = "REAL_MISSED_OPPORTUNITY"
CLASS_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


@dataclass
class Measurement:
    at: datetime
    grid_w: float
    ev_w: float
    pv_w: float | None


@dataclass
class ControlEvent:
    at: datetime
    requested_a: float | None
    phase_mode: str | None
    gate_status: str | None
    actuator_status: str | None
    actuator_reason: str | None
    actuator_target_a: float | None
    transition_stage: str | None
    transition_failure: str | None
    charge_state: str | None
    raw: dict


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, TZ)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def resolve_day(value: str) -> date:
    now = datetime.now(TZ)
    if value == "today":
        return now.date()
    if value == "yesterday":
        return now.date() - timedelta(days=1)
    return date.fromisoformat(value)


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def load_measurements(
    day: date,
    db_path: Path = HISTORY_DB,
) -> list[Measurement]:
    start, end = _bounds(day)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        device_rows = con.execute(
            """
            SELECT device_key,id
            FROM devices
            WHERE device_key IN (
                'grid_p1','tesla',
                'pv_solaredge','pv_goodwe4200','pv_goodwe2000'
            )
            """
        ).fetchall()
        ids = dict(device_rows)
        for required in ("grid_p1", "tesla"):
            if required not in ids:
                raise RuntimeError(f"missing device: {required}")

        metric = con.execute(
            "SELECT id FROM metrics WHERE metric_key='electrical_power_w'"
        ).fetchone()
        if not metric:
            raise RuntimeError("metric electrical_power_w missing")

        placeholders = ",".join("?" * len(ids))
        rows = con.execute(
            f"""
            SELECT m.ts_utc,d.device_key,m.value_real
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            WHERE m.metric_id=?
              AND m.ts_utc>=?
              AND m.ts_utc<?
              AND m.device_id IN ({placeholders})
            ORDER BY m.ts_utc
            """,
            (
                metric[0],
                _iso_z(start),
                _iso_z(end),
                *ids.values(),
            ),
        ).fetchall()
    finally:
        con.close()

    by_ts: dict[str, dict[str, float]] = {}
    for ts, key, value in rows:
        if value is None:
            continue
        by_ts.setdefault(ts, {})[str(key)] = float(value)

    out: list[Measurement] = []
    pv_keys = ("pv_solaredge", "pv_goodwe4200", "pv_goodwe2000")
    for ts, values in by_ts.items():
        if "grid_p1" not in values or "tesla" not in values:
            continue
        pv_w = None
        if all(k in values for k in pv_keys):
            pv_w = sum(max(0.0, values[k]) for k in pv_keys)
        out.append(
            Measurement(
                at=datetime.fromisoformat(ts.replace("Z", "+00:00")),
                grid_w=values["grid_p1"],
                ev_w=max(0.0, values["tesla"]),
                pv_w=pv_w,
            )
        )
    out.sort(key=lambda row: row.at)
    return out


def load_control_events(
    day: date,
    db_path: Path = HISTORY_DB,
) -> list[ControlEvent]:
    start, end = _bounds(day)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        if not _table_exists(con, "ev_control_events"):
            return []
        baseline = con.execute(
            """
            SELECT
                ts_utc,requested_a,phase_mode,gate_status,
                actuator_status,actuator_reason,actuator_target_a,
                transition_stage,transition_failure,charge_state,raw_json
            FROM ev_control_events
            WHERE ts_utc<?
            ORDER BY ts_utc DESC
            LIMIT 1
            """,
            (_iso_z(start),),
        ).fetchall()
        in_day = con.execute(
            """
            SELECT
                ts_utc,requested_a,phase_mode,gate_status,
                actuator_status,actuator_reason,actuator_target_a,
                transition_stage,transition_failure,charge_state,raw_json
            FROM ev_control_events
            WHERE ts_utc>=? AND ts_utc<?
            ORDER BY ts_utc
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()
        rows = baseline + in_day
    finally:
        con.close()

    out: list[ControlEvent] = []
    for row in rows:
        (
            ts_text,
            requested_a,
            phase_mode,
            gate_status,
            actuator_status,
            actuator_reason,
            actuator_target_a,
            transition_stage,
            transition_failure,
            charge_state,
            raw_json,
        ) = row
        try:
            raw = json.loads(raw_json or "{}")
        except json.JSONDecodeError:
            raw = {}
        out.append(
            ControlEvent(
                at=datetime.fromisoformat(ts_text.replace("Z", "+00:00")),
                requested_a=_num(requested_a),
                phase_mode=str(phase_mode) if phase_mode else None,
                gate_status=str(gate_status) if gate_status else None,
                actuator_status=str(actuator_status) if actuator_status else None,
                actuator_reason=str(actuator_reason) if actuator_reason else None,
                actuator_target_a=_num(actuator_target_a),
                transition_stage=str(transition_stage) if transition_stage else None,
                transition_failure=str(transition_failure) if transition_failure else None,
                charge_state=str(charge_state) if charge_state else None,
                raw=raw if isinstance(raw, dict) else {},
            )
        )
    return out


def load_semantic_events(
    day: date,
    db_path: Path = HISTORY_DB,
) -> list[dict]:
    start, end = _bounds(day)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        if not _table_exists(con, "semantic_events"):
            return []
        rows = con.execute(
            """
            SELECT ts_utc,event_type,domain,subject,provenance_class
            FROM semantic_events
            WHERE ts_utc>=? AND ts_utc<?
            ORDER BY ts_utc
            """,
            (_iso_z(start), _iso_z(end)),
        ).fetchall()
    finally:
        con.close()

    return [
        {
            "at": ts,
            "eventType": event_type,
            "domain": domain,
            "subject": subject,
            "provenanceClass": provenance,
        }
        for ts, event_type, domain, subject, provenance in rows
    ]


def _control_context(event: ControlEvent) -> dict:
    payload = event.raw
    intent = _as_dict(payload.get("intent"))
    projection = _as_dict(intent.get("policyProjection"))
    realtime = _as_dict(projection.get("realtime"))
    phase = _as_dict(realtime.get("phaseShadow"))
    phase_policy = _as_dict(realtime.get("phasePolicy"))

    health = _as_dict(payload.get("deviceHealth"))
    easee = _as_dict(health.get("easee"))

    mode = str(
        event.phase_mode
        or phase.get("mode")
        or event.raw.get("phaseMode")
        or "UNKNOWN"
    ).upper()

    requested_a = event.requested_a
    if requested_a is None:
        requested_a = _num(phase.get("requestedA"))
    if requested_a is None:
        requested_a = event.actuator_target_a

    offered_a = _num(easee.get("offeredA"))
    if offered_a is None:
        downstream = _as_dict(payload.get("downstream"))
        offered_a = _num(_as_dict(downstream.get("easee")).get("offeredA"))

    deadline_guard_applied = projection.get("deadlineGuardApplied") is True
    deadline_max_a = _num(projection.get("deadlineMaxA"))

    max_a = _num(realtime.get("maxA"))
    if deadline_guard_applied and deadline_max_a is not None:
        max_a = deadline_max_a
    if max_a is None:
        max_a = MAX_A
    max_a = max(MIN_A, min(MAX_A, int(math.floor(max_a))))

    return {
        "mode": mode,
        "requestedA": requested_a,
        "offeredA": offered_a,
        "maxA": max_a,
        "eligible": realtime.get("eligible"),
        "applied": realtime.get("applied"),
        "envelopeAllowed": realtime.get("envelopeAllowed"),
        "currentReason": phase.get("currentReason"),
        "phaseReason": phase.get("phaseReason") or phase.get("reason"),
        "availableTotalW": _num(phase.get("availableTotalW")),
        "rollingAvgW": _num(phase.get("availableTotalAvg2mW")),
        "rollingReady": phase.get("rollingReady"),
        "rollingCoverageMs": _num(phase.get("rollingCoverageMs")),
        "physicalTargetSettled": phase.get("physicalTargetSettled"),
        "actualProductionA": _num(phase.get("actualProductionA")),
        "modeSinceAt": phase.get("modeSinceAt"),
        "offReentryDwellMs": _num(phase.get("offReentryDwellMs"))
        or DEFAULT_OFF_REENTRY_DWELL_MS,
        "onePTo3pDwellMs": _num(phase.get("onePTo3pDwellMs"))
        or DEFAULT_1P_TO_3P_DWELL_MS,
        "start1pW": _num(phase_policy.get("start1p_W"))
        or DEFAULT_START_1P_W,
        "enter3pW": _num(phase_policy.get("enter3p_W"))
        or DEFAULT_ENTER_3P_W,
        "deadlineGuardApplied": deadline_guard_applied,
        "deadlineMaxA": deadline_max_a,
        "intentReason": projection.get("reason"),
        "policyRevision": intent.get("policyRevision"),
    }


def _mode_dwell_ok(ctx: dict, at: datetime, required_ms: float) -> bool | None:
    mode_since = _parse_ts(ctx.get("modeSinceAt"))
    if mode_since is None:
        return None
    return (at - mode_since).total_seconds() * 1000.0 >= required_ms


def _desired_a(available_w: float | None, w_per_a: float, max_a: int) -> int | None:
    if available_w is None or w_per_a <= 0:
        return None
    return max(
        MIN_A,
        min(
            max_a,
            int(math.floor((available_w + IMPORT_TARGET_W) / w_per_a)),
        ),
    )


def _result(
    classification: str,
    reason: str,
    additional_w: float = 0.0,
    *,
    confidence: str = "HIGH",
) -> dict:
    return {
        "classification": classification,
        "reason": reason,
        "additionalFeasibleW": max(0.0, additional_w),
        "confidence": confidence,
    }


def classify_export_interval(
    *,
    at: datetime,
    export_w: float,
    ev_w: float,
    event: ControlEvent | None,
) -> dict:
    """Classify one observed export interval conservatively.

    REAL_MISSED_OPPORTUNITY is only emitted when durable control evidence says
    the EV was connected/eligible and no recorded controller constraint explains
    why a higher safe target was not used.
    """

    if event is None:
        return _result(CLASS_INSUFFICIENT, "NO_EV_CONTROL_EVIDENCE", confidence="LOW")

    event_age_s = (at - event.at).total_seconds()
    if event_age_s < -5:
        return _result(
            CLASS_INSUFFICIENT,
            "EV_CONTROL_EVIDENCE_NOT_TIME_ALIGNED",
            confidence="LOW",
        )

    ctx = _control_context(event)
    charge_state = str(event.charge_state or "").lower()
    connected = charge_state in CONNECTED_STATES
    if not charge_state:
        return _result(CLASS_INSUFFICIENT, "EV_CONNECTION_STATE_MISSING", confidence="LOW")
    if not connected:
        return _result(CLASS_UNAVOIDABLE, "EV_NOT_CONNECTED")

    gate_status = str(event.gate_status or "").upper()
    if gate_status and gate_status != "PASS":
        return _result(CLASS_CONSTRAINT, "EV_GATE_BLOCKED")

    actuator_status = str(event.actuator_status or "").upper()
    if event.transition_failure or actuator_status in {"FAILED", "ERROR"}:
        mode = ctx["mode"]
        wpa = W_PER_A_3P if mode == "3P" else W_PER_A_1P if mode == "1P" else 0.0
        requested_a = _num(ctx["requestedA"]) or 0.0
        requested_w = requested_a * wpa
        potential = min(export_w, max(0.0, requested_w - ev_w))
        if potential > 0:
            return _result(
                CLASS_MISSED,
                "ACTUATOR_OR_PHASE_TRANSITION_FAILED",
                potential,
                confidence="MEDIUM",
            )
        return _result(
            CLASS_CONSTRAINT,
            "ACTUATOR_FAILURE_NO_PROVEN_CAPTURE",
            confidence="MEDIUM",
        )

    if ctx["deadlineGuardApplied"]:
        requested_a = _num(ctx["requestedA"]) or 0.0
        offered_a = _num(ctx["offeredA"])
        max_a = int(ctx["maxA"])
        if offered_a is not None and offered_a + 0.25 < requested_a:
            return _result(CLASS_CONSTRAINT, "DOWNSTREAM_OFFER_BELOW_DEADLINE_TARGET")
        if requested_a >= max_a - 0.01:
            if max_a < MAX_A:
                return _result(CLASS_CONSTRAINT, "DEADLINE_CURRENT_CAP")
            return _result(CLASS_UNAVOIDABLE, "EV_AT_MAX_3P_CURRENT")
        return _result(CLASS_CONSTRAINT, "DEADLINE_EXECUTION_RESPONSE")

    if ctx["eligible"] is False or ctx["envelopeAllowed"] is False:
        return _result(CLASS_CONSTRAINT, "EV_OPPORTUNITY_ENVELOPE_NOT_ALLOWED")
    if ctx["applied"] is False:
        return _result(CLASS_CONSTRAINT, "REALTIME_EV_OPPORTUNITY_NOT_APPLIED")

    mode = ctx["mode"]
    requested_a = _num(ctx["requestedA"]) or 0.0
    offered_a = _num(ctx["offeredA"])
    max_a = int(ctx["maxA"])
    current_reason = str(ctx["currentReason"] or "")
    phase_reason = str(ctx["phaseReason"] or "")
    available_w = _num(ctx["availableTotalW"])
    rolling_w = _num(ctx["rollingAvgW"])
    rolling_ready = ctx["rollingReady"] is True

    if offered_a is not None and requested_a >= MIN_A and offered_a + 0.25 < requested_a:
        return _result(CLASS_CONSTRAINT, "DOWNSTREAM_OFFER_BELOW_REQUEST")

    transition_reasons = {
        "OFF_TO_1P_ROLLING_HIGH",
        "OFF_TO_3P_ROLLING_HIGH",
        "1P_TO_3P_ROLLING_HIGH",
    }
    bounded_reasons = {
        "PREDICTIVE_UP_BOUNDED",
        "PREDICTIVE_UP_ADAPTIVE_EXPORT",
        "PREDICTIVE_UP_WAIT_PHYSICAL",
        "MODE_ENTRY_INITIAL_A",
        "INITIAL_A",
    }

    if mode == "OFF":
        if not rolling_ready:
            return _result(CLASS_CONSTRAINT, "ROLLING_POWER_NOT_READY")

        dwell_ok = _mode_dwell_ok(
            ctx,
            at,
            float(ctx["offReentryDwellMs"]),
        )
        if dwell_ok is not True:
            return _result(CLASS_CONSTRAINT, "OFF_REENTRY_DWELL_ACTIVE")

        can_3p = (
            rolling_w is not None
            and rolling_w >= float(ctx["enter3pW"])
            and available_w is not None
            and available_w + PHASE_MARGIN_W >= MIN_A * W_PER_A_3P
        )
        can_1p = (
            rolling_w is not None
            and rolling_w >= float(ctx["start1pW"])
            and available_w is not None
            and available_w + PHASE_MARGIN_W >= MIN_A * W_PER_A_1P
        )
        if phase_reason in transition_reasons:
            return _result(CLASS_CONSTRAINT, "PHASE_TRANSITION_IN_PROGRESS")
        if can_3p:
            target_a = _desired_a(available_w, W_PER_A_3P, max_a) or MIN_A
            potential = min(export_w, max(0.0, target_a * W_PER_A_3P - ev_w))
            return _result(CLASS_MISSED, "OFF_TO_3P_FEASIBLE_NOT_TAKEN", potential)
        if can_1p:
            target_a = _desired_a(available_w, W_PER_A_1P, max_a) or MIN_A
            potential = min(export_w, max(0.0, target_a * W_PER_A_1P - ev_w))
            return _result(CLASS_MISSED, "OFF_TO_1P_FEASIBLE_NOT_TAKEN", potential)
        return _result(CLASS_CONSTRAINT, "ROLLING_OR_MIN_POWER_BLOCKS_START")

    if mode == "1P":
        if phase_reason in transition_reasons:
            return _result(CLASS_CONSTRAINT, "PHASE_TRANSITION_IN_PROGRESS")

        three_phase_dwell_ok = _mode_dwell_ok(
            ctx,
            at,
            float(ctx["onePTo3pDwellMs"]),
        )
        three_phase_feasible = (
            rolling_ready
            and three_phase_dwell_ok is True
            and rolling_w is not None
            and rolling_w >= float(ctx["enter3pW"])
            and available_w is not None
            and available_w + PHASE_MARGIN_W >= MIN_A * W_PER_A_3P
        )

        if three_phase_feasible:
            target_a = _desired_a(available_w, W_PER_A_3P, max_a) or MIN_A
            potential = min(export_w, max(0.0, target_a * W_PER_A_3P - ev_w))
            if ctx["physicalTargetSettled"] is False:
                return _result(CLASS_CONSTRAINT, "PHYSICAL_TARGET_NOT_SETTLED")
            return _result(
                CLASS_MISSED,
                "3P_PROMOTION_FEASIBLE_NOT_TAKEN",
                potential,
            )

        ideal_a = _desired_a(available_w, W_PER_A_1P, max_a)
        if ideal_a is not None and ideal_a > requested_a + 0.01:
            potential = min(export_w, (ideal_a - requested_a) * W_PER_A_1P)
            if current_reason in bounded_reasons or ctx["physicalTargetSettled"] is False:
                return _result(CLASS_CONSTRAINT, "CURRENT_RAMP_OR_SETTLING_LIMIT")
            if current_reason == "HOLD_A":
                return _result(CLASS_MISSED, "1P_CURRENT_HEADROOM_UNUSED", potential)
            return _result(CLASS_INSUFFICIENT, "UNEXPLAINED_1P_CURRENT_HEADROOM", confidence="MEDIUM")

        if requested_a >= max_a - 0.01:
            if max_a < MAX_A:
                return _result(CLASS_CONSTRAINT, "EV_CURRENT_ENVELOPE_CAP")
            return _result(CLASS_CONSTRAINT, "1P_CAP_WHILE_3P_CONSTRAINT_ACTIVE")

        if not rolling_ready or three_phase_dwell_ok is not True:
            return _result(CLASS_CONSTRAINT, "3P_PROMOTION_CONSTRAINT_ACTIVE")
        return _result(CLASS_UNAVOIDABLE, "CURRENT_GRANULARITY_OR_IMPORT_GUARD")

    if mode == "3P":
        ideal_a = _desired_a(available_w, W_PER_A_3P, max_a)

        if ideal_a is not None and ideal_a > requested_a + 0.01:
            potential = min(export_w, (ideal_a - requested_a) * W_PER_A_3P)
            if current_reason in bounded_reasons or ctx["physicalTargetSettled"] is False:
                return _result(CLASS_CONSTRAINT, "CURRENT_RAMP_OR_SETTLING_LIMIT")
            if current_reason == "HOLD_A":
                return _result(CLASS_MISSED, "3P_CURRENT_HEADROOM_UNUSED", potential)
            return _result(CLASS_INSUFFICIENT, "UNEXPLAINED_3P_CURRENT_HEADROOM", confidence="MEDIUM")

        if requested_a >= max_a - 0.01:
            if max_a < MAX_A:
                return _result(CLASS_CONSTRAINT, "EV_CURRENT_ENVELOPE_CAP")
            return _result(CLASS_UNAVOIDABLE, "EV_AT_MAX_3P_CURRENT")

        return _result(CLASS_UNAVOIDABLE, "CURRENT_GRANULARITY_OR_IMPORT_GUARD")

    return _result(CLASS_INSUFFICIENT, "EV_PHASE_MODE_UNKNOWN", confidence="LOW")


def _semantic_for_window(
    events: list[dict],
    start: datetime,
    end: datetime,
) -> list[dict]:
    margin = timedelta(minutes=5)
    low = start - margin
    high = end + margin
    out = []
    for event in events:
        at = _parse_ts(event.get("at"))
        if at is None or at < low or at > high:
            continue
        out.append(event)
    return out[:12]


def _group_samples(samples: list[dict], semantic_events: list[dict]) -> list[dict]:
    windows: list[dict] = []
    current = None

    for sample in samples:
        key = sample["classification"]
        start = _parse_ts(sample["start"])
        end = _parse_ts(sample["end"])
        if start is None or end is None:
            continue

        if (
            current is None
            or current["classification"] != key
            or start > current["_lastEnd"] + timedelta(seconds=MAX_MEASUREMENT_INTERVAL_S + 5)
        ):
            if current is not None:
                windows.append(current)
            current = {
                "start": sample["start"],
                "end": sample["end"],
                "classification": key,
                "exportKWh": 0.0,
                "additionalFeasibleCaptureKWh": 0.0,
                "peakExportW": 0.0,
                "sampleCount": 0,
                "reasons": Counter(),
                "phaseModes": Counter(),
                "controlReasons": Counter(),
                "confidence": Counter(),
                "_startDt": start,
                "_lastEnd": end,
            }

        current["end"] = sample["end"]
        current["_lastEnd"] = end
        current["exportKWh"] += sample["exportKWh"]
        current["additionalFeasibleCaptureKWh"] += sample["additionalFeasibleCaptureKWh"]
        current["peakExportW"] = max(current["peakExportW"], sample["exportW"])
        current["sampleCount"] += 1
        current["reasons"][sample["reason"]] += 1
        if sample.get("phaseMode"):
            current["phaseModes"][sample["phaseMode"]] += 1
        if sample.get("currentReason"):
            current["controlReasons"][sample["currentReason"]] += 1
        current["confidence"][sample["confidence"]] += 1

    if current is not None:
        windows.append(current)

    out = []
    for window in windows:
        reasons = [name for name, _ in window["reasons"].most_common()]
        controls = [name for name, _ in window["controlReasons"].most_common()]
        phases = [name for name, _ in window["phaseModes"].most_common()]
        confidence = window["confidence"].most_common(1)[0][0] if window["confidence"] else "LOW"
        start_dt = window["_startDt"]
        end_dt = window["_lastEnd"]
        out.append({
            "start": window["start"],
            "end": window["end"],
            "minutes": round((end_dt - start_dt).total_seconds() / 60.0, 1),
            "classification": window["classification"],
            "primaryReason": reasons[0] if reasons else None,
            "reasons": reasons,
            "phaseModes": phases,
            "controlReasons": controls,
            "exportKWh": round(window["exportKWh"], 4),
            "additionalFeasibleCaptureKWh": round(
                window["additionalFeasibleCaptureKWh"],
                4,
            ),
            "peakExportW": round(window["peakExportW"]),
            "sampleCount": window["sampleCount"],
            "confidence": confidence,
            "semanticEvents": _semantic_for_window(
                semantic_events,
                start_dt,
                end_dt,
            ),
        })
    return out


def build_replay(
    day: date,
    *,
    db_path: Path = HISTORY_DB,
) -> dict:
    start, end = _bounds(day)
    measurements = load_measurements(day, db_path)
    controls = load_control_events(day, db_path)
    semantic_events = load_semantic_events(day, db_path)

    control_i = 0
    latest_control: ControlEvent | None = None
    samples = []
    below_threshold_kwh = 0.0
    total_export_kwh = 0.0
    integrated_s = 0.0
    measurement_intervals_s = []
    intervals_over_preferred = 0
    control_segmented_intervals = 0
    carried_forward_segments = 0

    for i in range(len(measurements) - 1):
        row = measurements[i]
        next_row = measurements[i + 1]
        dt_s = (next_row.at - row.at).total_seconds()
        if dt_s <= 0 or dt_s > MAX_MEASUREMENT_INTERVAL_S:
            continue

        measurement_intervals_s.append(dt_s)
        if dt_s > PREFERRED_ATTRIBUTION_INTERVAL_S:
            intervals_over_preferred += 1

        while control_i < len(controls) and controls[control_i].at <= row.at:
            latest_control = controls[control_i]
            control_i += 1

        export_w = max(0.0, -row.grid_w)
        export_kwh = export_w * dt_s / 3_600_000.0
        total_export_kwh += export_kwh
        integrated_s += dt_s

        if export_w < MIN_EXPORT_W:
            below_threshold_kwh += export_kwh
            continue

        segment_start = row.at
        segment_control = latest_control
        segmented = False

        while segment_start < next_row.at:
            next_control_at = None
            if control_i < len(controls):
                candidate_at = controls[control_i].at
                if segment_start < candidate_at < next_row.at:
                    next_control_at = candidate_at

            boundaries = [next_row.at]
            if next_control_at is not None:
                boundaries.append(next_control_at)
            segment_end = min(boundaries)
            segment_dt_s = (segment_end - segment_start).total_seconds()

            if segment_dt_s > 0:
                result = classify_export_interval(
                    at=segment_start,
                    export_w=export_w,
                    ev_w=row.ev_w,
                    event=segment_control,
                )

                ctx = _control_context(segment_control) if segment_control else {}
                additional_w = min(export_w, result["additionalFeasibleW"])
                confidence = result["confidence"]
                resolution_limited = dt_s > PREFERRED_ATTRIBUTION_INTERVAL_S
                control_evidence_age_s = (
                    max(0.0, (segment_start - segment_control.at).total_seconds())
                    if segment_control is not None
                    else None
                )
                state_carried_forward = (
                    control_evidence_age_s is not None
                    and control_evidence_age_s
                    > HIGH_CONFIDENCE_CONTROL_EVENT_AGE_S
                )
                if (
                    (resolution_limited or state_carried_forward)
                    and confidence == "HIGH"
                ):
                    confidence = "MEDIUM"

                samples.append({
                    "start": _iso_z(segment_start),
                    "end": _iso_z(segment_end),
                    "exportW": export_w,
                    "exportKWh": export_w * segment_dt_s / 3_600_000.0,
                    "evW": row.ev_w,
                    "pvW": row.pv_w,
                    "classification": result["classification"],
                    "reason": result["reason"],
                    "confidence": confidence,
                    "measurementIntervalSec": dt_s,
                    "resolutionLimited": resolution_limited,
                    "controlEvidenceAgeSec": (
                        round(control_evidence_age_s, 3)
                        if control_evidence_age_s is not None
                        else None
                    ),
                    "controlStateCarriedForward": state_carried_forward,
                    "additionalFeasibleCaptureKWh": additional_w * segment_dt_s / 3_600_000.0,
                    "phaseMode": ctx.get("mode"),
                    "currentReason": ctx.get("currentReason"),
                    "phaseReason": ctx.get("phaseReason"),
                    "requestedA": ctx.get("requestedA"),
                    "offeredA": ctx.get("offeredA"),
                    "maxA": ctx.get("maxA"),
                    "availableTotalW": ctx.get("availableTotalW"),
                    "rollingAvgW": ctx.get("rollingAvgW"),
                    "rollingReady": ctx.get("rollingReady"),
                    "controlEvidenceAt": _iso_z(segment_control.at) if segment_control else None,
                })
                if state_carried_forward:
                    carried_forward_segments += 1

            if segment_end >= next_row.at:
                break

            segmented = True
            if next_control_at is not None and segment_end == next_control_at:
                while (
                    control_i < len(controls)
                    and controls[control_i].at == next_control_at
                ):
                    latest_control = controls[control_i]
                    control_i += 1
                segment_control = latest_control

            segment_start = segment_end

        if segmented:
            control_segmented_intervals += 1

    windows = _group_samples(samples, semantic_events)

    class_energy = defaultdict(float)
    class_potential = defaultdict(float)
    reason_energy = defaultdict(float)
    for sample in samples:
        class_energy[sample["classification"]] += sample["exportKWh"]
        class_potential[sample["classification"]] += sample["additionalFeasibleCaptureKWh"]
        reason_energy[sample["reason"]] += sample["exportKWh"]

    classified_export = sum(class_energy.values())
    sufficient_export = (
        classified_export - class_energy.get(CLASS_INSUFFICIENT, 0.0)
    )

    return {
        "schema": SCHEMA,
        "generatedAt": _iso_z(datetime.now(timezone.utc)),
        "dayLocal": day.isoformat(),
        "scope": SCOPE,
        "readOnly": True,
        "controlWrites": False,
        "sourceAuthority": {
            "measurements": "ems-history.sqlite/measurements",
            "evControlEvents": "ems-history.sqlite/ev_control_events",
            "semanticEvents": "ems-history.sqlite/semantic_events",
        },
        "policy": {
            "minimumExportForClassificationW": MIN_EXPORT_W,
            "maxMeasurementIntervalSec": MAX_MEASUREMENT_INTERVAL_S,
            "preferredAttributionIntervalSec": PREFERRED_ATTRIBUTION_INTERVAL_S,
            "controlEventSegmentation": True,
            "controlStateSemantics": "SEMANTIC_CHANGE_LEDGER",
            "highConfidenceControlEvidenceAgeSec": HIGH_CONFIDENCE_CONTROL_EVENT_AGE_S,
            "evCurrentRangeA": [MIN_A, MAX_A],
            "wattsPerAmp": {"1P": W_PER_A_1P, "3P": W_PER_A_3P},
            "predictiveImportTargetW": IMPORT_TARGET_W,
            "phaseViabilityMarginW": PHASE_MARGIN_W,
            "defaultOffReentryDwellSec": DEFAULT_OFF_REENTRY_DWELL_MS / 1000.0,
            "default1pTo3pDwellSec": DEFAULT_1P_TO_3P_DWELL_MS / 1000.0,
        },
        "coverage": {
            "measurementPoints": len(measurements),
            "controlEvents": len(controls),
            "controlEventsInDay": sum(1 for event in controls if start <= event.at < end),
            "controlBaselineBeforeDay": any(event.at < start for event in controls),
            "semanticEvents": len(semantic_events),
            "integratedHours": round(integrated_s / 3600.0, 3),
            "measurementIntervalSecP50": (
                round(sorted(measurement_intervals_s)[len(measurement_intervals_s) // 2], 1)
                if measurement_intervals_s
                else None
            ),
            "measurementIntervalsOverPreferredAttributionSec": intervals_over_preferred,
            "controlSegmentedMeasurementIntervals": control_segmented_intervals,
            "controlStateCarriedForwardSegments": carried_forward_segments,
            "classifiedExportKWh": round(classified_export, 4),
            "sufficientEvidenceExportKWh": round(max(0.0, sufficient_export), 4),
            "insufficientEvidenceExportKWh": round(
                class_energy.get(CLASS_INSUFFICIENT, 0.0),
                4,
            ),
            "belowClassificationThresholdExportKWh": round(
                below_threshold_kwh,
                4,
            ),
        },
        "totals": {
            "observedGridExportKWh": round(total_export_kwh, 4),
            "byClassificationKWh": {
                classification: round(class_energy.get(classification, 0.0), 4)
                for classification in (
                    CLASS_UNAVOIDABLE,
                    CLASS_CONSTRAINT,
                    CLASS_MISSED,
                    CLASS_INSUFFICIENT,
                )
            },
            "additionalFeasibleCaptureKWh": round(
                sum(class_potential.values()),
                4,
            ),
            "realMissedOpportunityCaptureKWh": round(
                class_potential.get(CLASS_MISSED, 0.0),
                4,
            ),
        },
        "reasonEnergyKWh": {
            reason: round(value, 4)
            for reason, value in sorted(
                reason_energy.items(),
                key=lambda item: (-item[1], item[0]),
            )
        },
        "windows": windows,
        "limitations": [
            "V0.1 classifies export only relative to EV feasibility; WW, Heating, appliances and battery are not counterfactual consumers in this replay.",
            "UNAVOIDABLE_EXPORT means unavoidable by the modeled EV path, not globally unavoidable by every possible household flexibility option.",
            "REAL_MISSED_OPPORTUNITY is emitted only when time-aligned durable control evidence supports EV connection/eligibility and no recorded controller constraint explains unused current or phase headroom.",
            "CONSTRAINT_DRIVEN_EXPORT includes rolling-power readiness, dwell, envelope/current caps, physical target settling, downstream offered-current limits and safe phase-transition execution.",
            "ev_control_events is a semantically deduplicated state-change ledger, not a heartbeat log. The latest known normalized control state remains valid until the next durable control change; age above 90 seconds reduces confidence rather than erasing the state. Missing baseline/control state is still INSUFFICIENT_EVIDENCE.",
            "Canonical measurements may be coarser than 120 seconds. V0.1.1 integrates valid intervals up to 600 seconds, segments them at durable EV-control state-change boundaries, and downgrades otherwise HIGH attribution confidence to MEDIUM when the measurement interval exceeds 120 seconds or the last semantic control change is older than 90 seconds.",
            "The replay does not invent pre-commissioning semantic events or backfill unavailable control history.",
        ],
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Deterministic EV constrained replay for EMS export analysis"
    )
    parser.add_argument(
        "day",
        nargs="?",
        default="yesterday",
        help="today, yesterday or YYYY-MM-DD",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=HISTORY_DB,
        help="canonical EMS history SQLite path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="derived JSON output path",
    )
    parser.add_argument(
        "--no-write-output",
        action="store_true",
        help="print only; do not write derived output",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    day = resolve_day(args.day)
    report = build_replay(day, db_path=args.db)

    if not args.no_write_output:
        output = args.output or DATA / f"constrained-replay-v0.1-{day.isoformat()}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(output.suffix + ".tmp")
        tmp.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(output)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

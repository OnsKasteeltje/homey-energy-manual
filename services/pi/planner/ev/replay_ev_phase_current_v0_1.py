#!/usr/bin/env python3
"""Read-only replay of current vs candidate EV phase/current control.

Source of truth:
  /home/jeroen/ems/data/ems-history.sqlite

The script performs no Homey calls and no device/control writes.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

DB_DEFAULT = "/home/jeroen/ems/data/ems-history.sqlite"

START_1P_W = 1500
STOP_1P_W = 1100
ENTER_3P_W = 4400
LEAVE_3P_W = 3600

CURRENT_DWELL_S = 120
CANDIDATE_DWELL_S = 300
ROLLING_WINDOW_S = 120
ROLLING_MIN_SPAN_S = 90
UPSCALE_CONFIRM_S = 45
IMPORT_DEADBAND_W = 250
MIN_A = 6
MAX_A = 16
MAX_INTEGRATION_GAP_S = 300


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Sample:
    ts: datetime
    p1_w: float
    ev_actual_w: float

    @property
    def available_w(self) -> float:
        return max(0.0, -self.p1_w + max(0.0, self.ev_actual_w))


@dataclass
class Step:
    ts: datetime
    mode: str
    requested_a: int
    target_w: int
    available_w: float
    rolling_w: float | None
    rolling_ready: bool
    synthetic_p1_w: float
    mode_reason: str
    current_reason: str


@dataclass
class State:
    mode: str = "OFF"
    mode_since: datetime | None = None
    requested_a: int = 0
    upscale_since: datetime | None = None


class Rolling:
    def __init__(self, window_s: int = ROLLING_WINDOW_S):
        self.window = timedelta(seconds=window_s)
        self.samples: deque[tuple[datetime, float]] = deque()

    def add(self, ts: datetime, value: float) -> tuple[float, bool, float]:
        while self.samples and self.samples[0][0] < ts - self.window:
            self.samples.popleft()
        self.samples.append((ts, value))
        avg = sum(v for _, v in self.samples) / len(self.samples)
        span_s = 0.0
        if len(self.samples) >= 2:
            span_s = (self.samples[-1][0] - self.samples[0][0]).total_seconds()
        ready = len(self.samples) >= 2 and span_s >= ROLLING_MIN_SPAN_S
        return avg, ready, span_s


def watts_per_amp(mode: str) -> int:
    if mode == "1P":
        return 230
    if mode == "3P":
        return 690
    return 0


def clamp_active_a(mode: str, available_w: float) -> int:
    wpa = watts_per_amp(mode)
    if not wpa:
        return 0
    feasible = math.floor(available_w / wpa)
    return max(MIN_A, min(MAX_A, feasible))


def dwell_ok(state: State, ts: datetime, dwell_s: int) -> bool:
    return state.mode_since is None or (ts - state.mode_since).total_seconds() >= dwell_s


def change_mode(state: State, ts: datetime, new_mode: str) -> None:
    if new_mode != state.mode:
        state.mode = new_mode
        state.mode_since = ts
        state.upscale_since = None
        if new_mode == "OFF":
            state.requested_a = 0


def current_policy_step(state: State, sample: Sample, rolling_w: float) -> Step:
    """Approximate the authoritative production phase-control path.

    Production currently uses instantaneous available power for OFF/1P/3P entry
    and 1P<->3P transitions, while 1P->OFF uses the 120 s rolling signal.
    """
    ts = sample.ts
    available = sample.available_w
    mode_reason = "HOLD"

    if state.mode == "3P":
        if available < LEAVE_3P_W and dwell_ok(state, ts, CURRENT_DWELL_S):
            if available >= START_1P_W:
                change_mode(state, ts, "1P")
                mode_reason = "3P_TO_1P_INSTANT"
            else:
                change_mode(state, ts, "OFF")
                mode_reason = "3P_TO_OFF_INSTANT"
    elif state.mode == "1P":
        if available >= ENTER_3P_W and dwell_ok(state, ts, CURRENT_DWELL_S):
            change_mode(state, ts, "3P")
            mode_reason = "1P_TO_3P_INSTANT"
        elif rolling_w < STOP_1P_W and dwell_ok(state, ts, CURRENT_DWELL_S):
            change_mode(state, ts, "OFF")
            mode_reason = "1P_TO_OFF_ROLLING"
    else:
        if available >= ENTER_3P_W:
            change_mode(state, ts, "3P")
            mode_reason = "OFF_TO_3P_INSTANT"
        elif available >= START_1P_W:
            change_mode(state, ts, "1P")
            mode_reason = "OFF_TO_1P_INSTANT"

    if state.mode == "OFF":
        state.requested_a = 0
    else:
        state.requested_a = clamp_active_a(state.mode, available)

    target_w = state.requested_a * watts_per_amp(state.mode)
    synthetic_p1 = target_w - available

    return Step(
        ts=ts,
        mode=state.mode,
        requested_a=state.requested_a,
        target_w=target_w,
        available_w=available,
        rolling_w=rolling_w,
        rolling_ready=True,
        synthetic_p1_w=synthetic_p1,
        mode_reason=mode_reason,
        current_reason="DIRECT_AVAILABLE_QUANTIZATION",
    )


def candidate_policy_step(
    state: State,
    sample: Sample,
    rolling_w: float,
    rolling_ready: bool,
) -> Step:
    """Candidate separated phase selector + phase-aware current regulator."""
    ts = sample.ts
    available = sample.available_w
    mode_reason = "HOLD"

    can_switch = dwell_ok(state, ts, CANDIDATE_DWELL_S) and rolling_ready

    if state.mode == "3P" and can_switch:
        if rolling_w < STOP_1P_W:
            change_mode(state, ts, "OFF")
            mode_reason = "3P_TO_OFF_ROLLING"
        elif rolling_w < LEAVE_3P_W:
            change_mode(state, ts, "1P")
            mode_reason = "3P_TO_1P_ROLLING"
    elif state.mode == "1P" and can_switch:
        if rolling_w >= ENTER_3P_W:
            change_mode(state, ts, "3P")
            mode_reason = "1P_TO_3P_ROLLING"
        elif rolling_w < STOP_1P_W:
            change_mode(state, ts, "OFF")
            mode_reason = "1P_TO_OFF_ROLLING"
    elif state.mode == "OFF" and can_switch:
        if rolling_w >= ENTER_3P_W:
            change_mode(state, ts, "3P")
            mode_reason = "OFF_TO_3P_ROLLING"
        elif rolling_w >= START_1P_W:
            change_mode(state, ts, "1P")
            mode_reason = "OFF_TO_1P_ROLLING"

    current_reason = "OFF"
    if state.mode == "OFF":
        state.requested_a = 0
        state.upscale_since = None
    else:
        wpa = watts_per_amp(state.mode)
        if state.requested_a < MIN_A:
            state.requested_a = clamp_active_a(state.mode, available)
            current_reason = "MODE_ENTRY_INITIAL_A"
            state.upscale_since = None
        else:
            target_w = state.requested_a * wpa
            synthetic_p1 = target_w - available

            if synthetic_p1 > IMPORT_DEADBAND_W:
                reduction = max(
                    1,
                    math.ceil((synthetic_p1 - IMPORT_DEADBAND_W) / wpa),
                )
                state.requested_a = max(MIN_A, state.requested_a - reduction)
                state.upscale_since = None
                current_reason = "FAST_IMPORT_DOWN"
            elif synthetic_p1 <= -wpa and state.requested_a < MAX_A:
                if state.upscale_since is None:
                    state.upscale_since = ts
                    current_reason = "UPSCALE_CONFIRM_STARTED"
                elif (ts - state.upscale_since).total_seconds() >= UPSCALE_CONFIRM_S:
                    state.requested_a += 1
                    state.upscale_since = ts
                    current_reason = "SLOW_PLUS_1A"
                else:
                    current_reason = "UPSCALE_CONFIRMING"
            else:
                state.upscale_since = None
                current_reason = "HOLD_A"

    target_w = state.requested_a * watts_per_amp(state.mode)
    synthetic_p1 = target_w - available

    return Step(
        ts=ts,
        mode=state.mode,
        requested_a=state.requested_a,
        target_w=target_w,
        available_w=available,
        rolling_w=rolling_w,
        rolling_ready=rolling_ready,
        synthetic_p1_w=synthetic_p1,
        mode_reason=mode_reason,
        current_reason=current_reason,
    )


def load_samples(db_path: str, start_utc: datetime, end_utc: datetime) -> list[Sample]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT
                x.ts_utc,
                MAX(CASE WHEN d.device_key='grid_p1' THEN x.value_real END) AS p1_w,
                MAX(CASE WHEN d.device_key='tesla' THEN x.value_real END) AS ev_w
            FROM measurements x
            JOIN devices d ON d.id=x.device_id
            JOIN metrics m ON m.id=x.metric_id
            WHERE m.metric_key='electrical_power_w'
              AND d.device_key IN ('grid_p1','tesla')
              AND x.ts_utc >= ?
              AND x.ts_utc < ?
            GROUP BY x.ts_utc
            HAVING p1_w IS NOT NULL AND ev_w IS NOT NULL
            ORDER BY x.ts_utc
            """,
            (iso_z(start_utc), iso_z(end_utc)),
        ).fetchall()
    finally:
        con.close()

    return [
        Sample(parse_utc(ts), float(p1), float(ev))
        for ts, p1, ev in rows
    ]


def summarize(steps: list[Step]) -> dict:
    if len(steps) < 2:
        return {}

    mode_changes = []
    a_changes = []
    mode_seconds = {"OFF": 0.0, "1P": 0.0, "3P": 0.0}
    energy_kwh = 0.0
    induced_import_kwh = 0.0
    residual_export_kwh = 0.0
    covered_s = 0.0

    prev = steps[0]
    for step in steps[1:]:
        dt_s = min(
            MAX_INTEGRATION_GAP_S,
            max(0.0, (step.ts - prev.ts).total_seconds()),
        )
        if dt_s > 0:
            covered_s += dt_s
            mode_seconds[prev.mode] += dt_s
            energy_kwh += prev.target_w * dt_s / 3_600_000
            induced_import_kwh += max(0.0, prev.synthetic_p1_w) * dt_s / 3_600_000
            residual_export_kwh += max(0.0, -prev.synthetic_p1_w) * dt_s / 3_600_000

        if step.mode != prev.mode:
            mode_changes.append({
                "at": iso_z(step.ts),
                "from": prev.mode,
                "to": step.mode,
                "reason": step.mode_reason,
                "rollingW": None if step.rolling_w is None else round(step.rolling_w),
                "availableW": round(step.available_w),
            })
        if step.requested_a != prev.requested_a:
            a_changes.append({
                "at": iso_z(step.ts),
                "mode": step.mode,
                "fromA": prev.requested_a,
                "toA": step.requested_a,
                "reason": step.current_reason,
            })
        prev = step

    return {
        "coveredHours": round(covered_s / 3600, 3),
        "modeHours": {k: round(v / 3600, 3) for k, v in mode_seconds.items()},
        "modeChangeCount": len(mode_changes),
        "currentChangeCount": len(a_changes),
        "targetEnergyKWh": round(energy_kwh, 3),
        "estimatedInducedImportKWh": round(induced_import_kwh, 3),
        "estimatedResidualExportKWh": round(residual_export_kwh, 3),
        "modeChanges": mode_changes,
        "currentChanges": a_changes,
    }


def run_model(samples: list[Sample], candidate: bool) -> tuple[list[Step], dict]:
    rolling = Rolling()
    state = State(mode="OFF", mode_since=samples[0].ts if samples else None)
    steps: list[Step] = []
    ready_count = 0
    spans = []

    for sample in samples:
        avg, ready, span_s = rolling.add(sample.ts, sample.available_w)
        spans.append(span_s)
        if ready:
            ready_count += 1

        if candidate:
            step = candidate_policy_step(state, sample, avg, ready)
        else:
            step = current_policy_step(state, sample, avg)
        steps.append(step)

    diag = {
        "rollingReadyPct": round(100 * ready_count / len(samples), 1) if samples else 0.0,
        "maxRollingSpanSec": round(max(spans), 1) if spans else 0.0,
    }
    return steps, diag


def cadence(samples: list[Sample]) -> dict:
    gaps = [
        (b.ts - a.ts).total_seconds()
        for a, b in zip(samples, samples[1:])
        if b.ts > a.ts
    ]
    if not gaps:
        return {"sampleCount": len(samples)}
    gaps_sorted = sorted(gaps)
    p95 = gaps_sorted[min(len(gaps_sorted) - 1, math.floor(0.95 * len(gaps_sorted)))]
    return {
        "sampleCount": len(samples),
        "medianGapSec": round(median(gaps), 1),
        "p95GapSec": round(p95, 1),
        "maxGapSec": round(max(gaps), 1),
    }


def focus_events(steps: list[Step], start: datetime, end: datetime) -> list[dict]:
    out = []
    prev = None
    for step in steps:
        if not (start <= step.ts < end):
            prev = step
            continue
        changed = (
            prev is None
            or step.mode != prev.mode
            or step.requested_a != prev.requested_a
        )
        if changed:
            out.append({
                "at": iso_z(step.ts),
                "mode": step.mode,
                "a": step.requested_a,
                "targetW": step.target_w,
                "availableW": round(step.available_w),
                "rollingW": None if step.rolling_w is None else round(step.rolling_w),
                "rollingReady": step.rolling_ready,
                "modeReason": step.mode_reason,
                "currentReason": step.current_reason,
            })
        prev = step
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--date", required=True, help="Local date YYYY-MM-DD")
    ap.add_argument("--timezone", default="Europe/Amsterdam")
    ap.add_argument("--focus-start", default="12:00")
    ap.add_argument("--focus-end", default="15:00")
    ap.add_argument("--allow-sparse", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"DB_NOT_FOUND: {db}")

    tz = ZoneInfo(args.timezone)
    day = datetime.fromisoformat(args.date)
    local_start = day.replace(tzinfo=tz)
    local_end = local_start + timedelta(days=1)

    def local_hhmm(value: str) -> datetime:
        hh, mm = [int(x) for x in value.split(":", 1)]
        return local_start.replace(hour=hh, minute=mm, second=0, microsecond=0)

    samples = load_samples(
        str(db),
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )

    if len(samples) < 2:
        raise SystemExit("INSUFFICIENT_HISTORY: fewer than two joined P1/Tesla samples")

    current_steps, current_diag = run_model(samples, candidate=False)
    candidate_steps, candidate_diag = run_model(samples, candidate=True)
    cad = cadence(samples)

    valid_rolling = candidate_diag["rollingReadyPct"] >= 50.0
    if not valid_rolling and not args.allow_sparse:
        payload = {
            "status": "INSUFFICIENT_HISTORY_RESOLUTION",
            "dateLocal": args.date,
            "cadence": cad,
            "candidateRolling": candidate_diag,
            "note": (
                "Raw history does not provide enough 120-second window coverage "
                "for a defensible replay. Re-run with --allow-sparse only for "
                "diagnostics; do not use that result for promotion."
            ),
        }
        print(json.dumps(payload, indent=2))
        return 2

    focus_start = local_hhmm(args.focus_start).astimezone(timezone.utc)
    focus_end = local_hhmm(args.focus_end).astimezone(timezone.utc)

    payload = {
        "status": "PASS" if valid_rolling else "SPARSE_DIAGNOSTIC_ONLY",
        "schema": "EMS_EV_PHASE_CURRENT_REPLAY_V0.1",
        "dateLocal": args.date,
        "timezone": args.timezone,
        "source": str(db),
        "cadence": cad,
        "policy": {
            "thresholdsW": {
                "start1p": START_1P_W,
                "stop1p": STOP_1P_W,
                "enter3p": ENTER_3P_W,
                "leave3p": LEAVE_3P_W,
            },
            "currentDwellSec": CURRENT_DWELL_S,
            "candidateDwellSec": CANDIDATE_DWELL_S,
            "rollingWindowSec": ROLLING_WINDOW_S,
            "rollingMinSpanSec": ROLLING_MIN_SPAN_S,
            "upscaleConfirmSec": UPSCALE_CONFIRM_S,
            "importDeadbandW": IMPORT_DEADBAND_W,
        },
        "current": {
            "diagnostic": current_diag,
            "summary": summarize(current_steps),
            "focusEvents": focus_events(current_steps, focus_start, focus_end),
        },
        "candidate": {
            "diagnostic": candidate_diag,
            "summary": summarize(candidate_steps),
            "focusEvents": focus_events(candidate_steps, focus_start, focus_end),
        },
        "readOnly": True,
        "deviceWrites": False,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

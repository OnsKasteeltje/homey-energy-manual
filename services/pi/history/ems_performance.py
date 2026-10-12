#!/usr/bin/env python3

"""Standardized read-only EMS day-performance report.

Usage:
  ems-performance yesterday
  ems-performance today
  ems-performance YYYY-MM-DD

The report combines measured operational history with planner-history coverage.
It deliberately separates realised PV capture from a simple energy upper bound.
A constrained theoretical optimum is never fabricated when replay context is
insufficient or the dedicated constrained replay optimiser is not available.
"""

import argparse
import json
import sqlite3
import sys
import zlib
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
DATA = Path("/home/jeroen/ems/data")
MEASUREMENTS_DB = DATA / "ems-history.sqlite"
PLANNER_DB = DATA / "planner-history.sqlite"
MAX_INTERVAL_S = 600
FULL_DAY_MINUTES = 24 * 60
DEVICES = (
    "grid_p1",
    "pv_solaredge",
    "pv_goodwe4200",
    "pv_goodwe2000",
    "tesla",
    "boiler",
    "quatt_cic",
)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Standard EMS day-performance report")
    p.add_argument("day", nargs="?", default="yesterday", help="yesterday, today or YYYY-MM-DD")
    return p.parse_args(argv)


def resolve_day(value):
    now = datetime.now(TZ)
    if value == "yesterday":
        return now.date() - timedelta(days=1)
    if value == "today":
        return now.date()
    return date.fromisoformat(value)


def bounds(day):
    start = datetime.combine(day, time.min, TZ)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_measurements(day, db_path=MEASUREMENTS_DB):
    start, end = bounds(day)
    if not db_path.exists():
        raise RuntimeError(f"measurement DB missing: {db_path}")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        ids = dict(con.execute(
            "SELECT device_key,id FROM devices WHERE device_key IN (%s)" % ",".join("?" * len(DEVICES)),
            DEVICES,
        ).fetchall())
        missing = [d for d in DEVICES if d not in ids]
        if missing:
            raise RuntimeError("missing devices: " + ", ".join(missing))
        metric = con.execute("SELECT id FROM metrics WHERE metric_key='electrical_power_w'").fetchone()
        if not metric:
            raise RuntimeError("metric electrical_power_w missing")
        q = f"""
            SELECT m.ts_utc,d.device_key,m.value_real,m.quality
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            WHERE m.metric_id=? AND m.ts_utc>=? AND m.ts_utc<?
              AND m.device_id IN ({','.join('?' * len(ids))})
            ORDER BY m.ts_utc
        """
        params = [
            metric[0],
            iso_z(start),
            iso_z(end),
            *ids.values(),
        ]
        rows = con.execute(q, params).fetchall()
    finally:
        con.close()

    by_ts = {}
    quality = Counter()
    for ts, key, value, qv in rows:
        by_ts.setdefault(ts, {})[key] = float(value)
        quality[str(qv or "unknown")] += 1

    out = []
    for ts, values in by_ts.items():
        if all(k in values for k in DEVICES):
            out.append((datetime.fromisoformat(ts.replace("Z", "+00:00")), values))
    out.sort(key=lambda x: x[0])
    return out, quality


def load_easee_meter_window(day, db_path=MEASUREMENTS_DB, now_utc=None):
    """Read the cumulative Easee delivered-energy counter without inventing coverage."""
    start, end = bounds(day)
    now_utc = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    effective_end = min(end, now_utc) if now_utc > start else start

    if not db_path.exists():
        return {"available": False, "coverageStatus": "UNAVAILABLE", "reason": "HISTORY_DB_MISSING"}

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        device = con.execute("SELECT id FROM devices WHERE device_key='tesla'").fetchone()
        metric = con.execute("SELECT id FROM metrics WHERE metric_key='energy_delivered_kwh'").fetchone()
        if not device or not metric:
            return {"available": False, "coverageStatus": "UNAVAILABLE", "reason": "EASEE_CUMULATIVE_METER_NOT_ARCHIVED"}
        baseline = con.execute(
            """SELECT ts_utc,value_real FROM measurements
               WHERE device_id=? AND metric_id=? AND value_real IS NOT NULL AND ts_utc<=?
               ORDER BY ts_utc DESC LIMIT 1""",
            (device[0], metric[0], iso_z(start)),
        ).fetchone()
        latest = con.execute(
            """SELECT ts_utc,value_real FROM measurements
               WHERE device_id=? AND metric_id=? AND value_real IS NOT NULL
                 AND ts_utc>=? AND ts_utc<?
               ORDER BY ts_utc DESC LIMIT 1""",
            (device[0], metric[0], iso_z(start), iso_z(effective_end)),
        ).fetchone()
    finally:
        con.close()

    if not baseline or not latest:
        return {"available": False, "coverageStatus": "UNAVAILABLE", "reason": "EASEE_CUMULATIVE_METER_BOUNDARY_MISSING"}

    baseline_at = datetime.fromisoformat(baseline[0].replace("Z", "+00:00"))
    latest_at = datetime.fromisoformat(latest[0].replace("Z", "+00:00"))
    baseline_age_s = max(0.0, (start - baseline_at).total_seconds())
    end_gap_s = max(0.0, (effective_end - latest_at).total_seconds())
    delta = float(latest[1]) - float(baseline[1])

    if delta < -0.01:
        return {
            "available": False,
            "coverageStatus": "INVALID_COUNTER_RESET",
            "reason": "EASEE_CUMULATIVE_METER_DECREASED",
            "baselineAt": iso_z(baseline_at),
            "latestAt": iso_z(latest_at),
        }

    full = baseline_age_s <= MAX_INTERVAL_S and end_gap_s <= MAX_INTERVAL_S
    return {
        "available": full,
        "coverageStatus": (
            "FULL_ELAPSED_DAY" if full and day == now_utc.astimezone(TZ).date()
            else "FULL_DAY" if full else "PARTIAL_BOUNDARY_COVERAGE"
        ),
        "reason": None if full else "EASEE_CUMULATIVE_METER_BOUNDARY_GAP",
        "chargedKWh": round(max(0.0, delta), 3) if full else None,
        "observedDeltaKWh": round(max(0.0, delta), 3),
        "baselineAt": iso_z(baseline_at),
        "latestAt": iso_z(latest_at),
        "baselineAgeSec": round(baseline_age_s, 1),
        "endGapSec": round(end_gap_s, 1),
        "source": "Easee meter_power cumulative delivered energy",
        "metric": "energy_delivered_kwh",
    }



def load_energy_interval_accounting(day, db_path=MEASUREMENTS_DB, now_utc=None):
    """Day KPI from archived energy intervals, never from sampled instantaneous power.

    P1 import/export stays the grid authority. Paired PV/P1 coverage is
    required for a trustworthy derived PV self-consumption day KPI.
    """
    start, end = bounds(day)
    now_utc = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    effective_end = min(end, now_utc)
    expected_s = max(0.0, (effective_end - start).total_seconds())
    unavailable = {
        "available": False,
        "status": "UNAVAILABLE",
        "source": "ems-history.sqlite/house_energy_intervals",
        "method": "ARCHIVED_CUMULATIVE_ENERGY_INTERVALS",
        "pvKWh": None, "importKWh": None, "exportKWh": None,
        "pvSelfConsumedKWh": None, "pvSelfConsumptionRate": None,
        "p1Coverage": 0.0, "pvCoverage": 0.0, "pairedCoverage": 0.0,
        "sourceQualityCounts": {"p1": {}, "pv": {}},
    }
    if not db_path.exists() or expected_s < 1800:
        return unavailable

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='house_energy_intervals'"
        ).fetchone()
        if not table:
            return unavailable
        rows = con.execute(
            """SELECT start_ts_utc,end_ts_utc,import_kwh,export_kwh,
                      pv_total_kwh,quality,p1_quality,pv_quality
               FROM house_energy_intervals
               WHERE end_ts_utc > ? AND start_ts_utc < ?
               ORDER BY start_ts_utc""",
            (iso_z(start), iso_z(effective_end)),
        ).fetchall()

    totals = {"pvKWh": 0.0, "importKWh": 0.0, "exportKWh": 0.0}
    seconds = {"p1": 0.0, "pv": 0.0, "paired": 0.0}
    source_quality = {"p1": Counter(), "pv": Counter()}
    for start_text, end_text, imp, exp, pv, quality, p1_quality, pv_quality in rows:
        row_start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        row_end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
        row_seconds = (row_end - row_start).total_seconds()
        overlap = max(
            0.0,
            (min(row_end, effective_end) - max(row_start, start)).total_seconds(),
        )
        if overlap <= 0 or row_seconds <= 0 or quality == "discontinuity":
            continue
        fraction = overlap / row_seconds
        p1_ok = p1_quality in {"observed", "held"} and imp is not None and exp is not None
        pv_ok = pv_quality in {"observed", "held", "estimated"} and pv is not None
        if p1_ok:
            totals["importKWh"] += float(imp) * fraction
            totals["exportKWh"] += float(exp) * fraction
            seconds["p1"] += overlap
            source_quality["p1"][p1_quality] += 1
        if pv_ok:
            totals["pvKWh"] += float(pv) * fraction
            seconds["pv"] += overlap
            source_quality["pv"][pv_quality] += 1
        if p1_ok and pv_ok:
            seconds["paired"] += overlap

    coverage = {
        "p1Coverage": round(min(1.0, seconds["p1"] / expected_s), 4),
        "pvCoverage": round(min(1.0, seconds["pv"] / expected_s), 4),
        "pairedCoverage": round(min(1.0, seconds["paired"] / expected_s), 4),
    }
    # Do not promote partial/inconsistent accounting into a day KPI.
    available = (
        seconds["paired"] / expected_s >= 0.95
        and totals["pvKWh"] > 0
        and totals["pvKWh"] + 1e-6 >= totals["exportKWh"]
    )
    status = (
        "GOOD" if available
        else "INVALID_ENERGY_BALANCE" if totals["pvKWh"] + 1e-6 < totals["exportKWh"]
        else "INSUFFICIENT_PAIRED_COVERAGE"
    )
    direct = max(0.0, totals["pvKWh"] - totals["exportKWh"]) if available else None
    return {
        **unavailable,
        **coverage,
        "available": available,
        "status": status,
        "sourceQualityCounts": {k: dict(v) for k, v in source_quality.items()},
        "pvKWh": round(totals["pvKWh"], 6) if seconds["pv"] else None,
        "importKWh": round(totals["importKWh"], 6) if seconds["p1"] else None,
        "exportKWh": round(totals["exportKWh"], 6) if seconds["p1"] else None,
        "pvSelfConsumedKWh": round(direct, 6) if direct is not None else None,
        "pvSelfConsumptionRate": (
            round(direct / totals["pvKWh"], 4) if available else None
        ),
    }


def integrate(rows):
    totals = {
        "pv_kwh": 0.0,
        "grid_import_kwh": 0.0,
        "grid_export_kwh": 0.0,
        "house_consumption_kwh": 0.0,
        "direct_pv_self_use_kwh": 0.0,
        "boiler_kwh": 0.0,
        "tesla_kwh": 0.0,
        "ev_pv_allocated_kwh": 0.0,
        "ev_grid_allocated_kwh": 0.0,
        "quatt_kwh": 0.0,
        "flex_load_kwh": 0.0,
        "flex_pv_capture_kwh": 0.0,
        "flex_grid_energy_kwh": 0.0,
        "pre_flex_surplus_kwh": 0.0,
        "pv_p1_impossible_export_kwh": 0.0,
        "pv_p1_impossible_export_intervals": 0,
    }
    integrated_s = 0.0
    surplus_windows = []
    current = None

    for i in range(len(rows) - 1):
        ts, v = rows[i]
        dt = (rows[i + 1][0] - ts).total_seconds()
        if dt <= 0 or dt > MAX_INTERVAL_S:
            if current:
                surplus_windows.append(current)
                current = None
            continue
        h = dt / 3600.0
        integrated_s += dt

        grid = v["grid_p1"]
        pv = max(0.0, v["pv_solaredge"] + v["pv_goodwe4200"] + v["pv_goodwe2000"])
        tesla = max(0.0, v["tesla"])
        boiler = max(0.0, v["boiler"])
        quatt = max(0.0, v["quatt_cic"])
        flex = tesla + boiler
        house = max(0.0, pv + grid)
        base = max(0.0, house - flex)
        export = max(0.0, -grid)
        imp = max(0.0, grid)
        if export > pv:
            totals["pv_p1_impossible_export_kwh"] += (export - pv) / 1000 * h
            totals["pv_p1_impossible_export_intervals"] += 1
        direct = min(pv, house)
        available_for_flex = max(0.0, pv - base)
        flex_pv = min(flex, available_for_flex)
        # Derived allocation only; this is not a directly metered PV->EV flow.
        ev_pv_allocated = min(tesla, available_for_flex)
        ev_grid_allocated = max(0.0, tesla - ev_pv_allocated)
        preflex = export + flex_pv

        totals["pv_kwh"] += pv / 1000 * h
        totals["grid_import_kwh"] += imp / 1000 * h
        totals["grid_export_kwh"] += export / 1000 * h
        totals["house_consumption_kwh"] += house / 1000 * h
        totals["direct_pv_self_use_kwh"] += direct / 1000 * h
        totals["boiler_kwh"] += boiler / 1000 * h
        totals["tesla_kwh"] += tesla / 1000 * h
        totals["ev_pv_allocated_kwh"] += ev_pv_allocated / 1000 * h
        totals["ev_grid_allocated_kwh"] += ev_grid_allocated / 1000 * h
        totals["quatt_kwh"] += quatt / 1000 * h
        totals["flex_load_kwh"] += flex / 1000 * h
        totals["flex_pv_capture_kwh"] += flex_pv / 1000 * h
        totals["flex_grid_energy_kwh"] += max(0.0, flex - flex_pv) / 1000 * h
        totals["pre_flex_surplus_kwh"] += preflex / 1000 * h

        # Observation only: exported-PV windows while no measured flexible load
        # was active. These are candidates for replay, not automatically EMS faults.
        candidate = export >= 500 and flex < 200
        if candidate:
            if current is None:
                current = {
                    "start": iso_z(ts),
                    "end": iso_z(ts + timedelta(seconds=dt)),
                    "export_kwh": 0.0,
                    "peak_export_w": 0.0,
                }
            current["end"] = iso_z(ts + timedelta(seconds=dt))
            current["export_kwh"] += export / 1000 * h
            current["peak_export_w"] = max(current["peak_export_w"], export)
        elif current:
            surplus_windows.append(current)
            current = None

    if current:
        surplus_windows.append(current)

    for w in surplus_windows:
        w["export_kwh"] = round(w["export_kwh"], 3)
        w["peak_export_w"] = round(w["peak_export_w"])
        start = datetime.fromisoformat(w["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(w["end"].replace("Z", "+00:00"))
        w["minutes"] = round((end - start).total_seconds() / 60)

    return totals, integrated_s, sorted(surplus_windows, key=lambda x: x["export_kwh"], reverse=True)[:8]


def load_planner_history(day, db_path=PLANNER_DB):
    start, end = bounds(day)
    if not db_path.exists():
        return {
            "available": False,
            "snapshotCount": 0,
            "contextSources": [],
            "firstSnapshot": None,
            "lastSnapshot": None,
            "maxGapMinutes": None,
            "contractIds": [],
            "plannerOwners": [],
        }
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        rows = con.execute(
            "SELECT generated_at_utc,snapshot_zlib FROM planner_snapshots "
            "WHERE generated_at_utc>=? AND generated_at_utc<? ORDER BY generated_at_utc",
            (iso_z(start), iso_z(end)),
        ).fetchall()
    finally:
        con.close()

    stamps = []
    context_sources = Counter()
    contract_ids = Counter()
    owners = Counter()
    schemas = Counter()
    for ts, blob in rows:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        stamps.append(dt)
        try:
            snap = json.loads(zlib.decompress(blob).decode("utf-8"))
            plan = snap.get("plan") or {}
            context = snap.get("context") or {}
            context_sources[str(context.get("contextSource") or "UNKNOWN")] += 1
            contract = plan.get("contract") or context.get("contract") or {}
            if contract.get("id"):
                contract_ids[str(contract["id"])] += 1
            if plan.get("plannerOwner"):
                owners[str(plan["plannerOwner"])] += 1
            if plan.get("schema"):
                schemas[str(plan["schema"])] += 1
        except Exception:
            schemas["UNREADABLE_SNAPSHOT"] += 1

    gaps = []
    for a, b in zip(stamps, stamps[1:]):
        gaps.append((b - a).total_seconds() / 60)

    return {
        "available": bool(rows),
        "snapshotCount": len(rows),
        "contextSources": sorted(context_sources),
        "firstSnapshot": iso_z(stamps[0]) if stamps else None,
        "lastSnapshot": iso_z(stamps[-1]) if stamps else None,
        "maxGapMinutes": None if not gaps else round(max(gaps), 1),
        "contractIds": sorted(contract_ids),
        "plannerOwners": sorted(owners),
        "plannerSchemas": sorted(schemas),
    }


def verdict(score, gap_kwh, quality):
    if quality not in ("GOOD", "PARTIAL_TODAY"):
        return "INSUFFICIENT_DATA"
    if score is None:
        return "NO_FLEX_BENCHMARK"
    if gap_kwh <= 0.25 or score >= 0.97:
        return "HIGH_PV_CAPTURE"
    if score >= 0.90:
        return "GOOD_PV_CAPTURE"
    if score >= 0.75:
        return "REVIEW_OPPORTUNITIES"
    return "REVIEW_REQUIRED"


def build_report(
    day,
    measurement_db=MEASUREMENTS_DB,
    planner_db=PLANNER_DB,
    now_utc=None,
):
    rows, quality_counts = load_measurements(day, measurement_db)
    if len(rows) < 2:
        raise RuntimeError(f"insufficient complete measurement samples for {day}")

    totals, integrated_s, windows = integrate(rows)
    minutes = integrated_s / 60

    start_utc, end_utc = bounds(day)
    now_utc = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    easee_meter = load_easee_meter_window(day, measurement_db, now_utc=now_utc)
    energy_accounting = load_energy_interval_accounting(day, measurement_db, now_utc=now_utc)
    now_local = now_utc.astimezone(TZ)
    today = now_local.date()

    day_duration_minutes = (end_utc - start_utc).total_seconds() / 60.0
    full_day_coverage_pct = min(
        100.0,
        minutes / day_duration_minutes * 100
        if day_duration_minutes > 0 else 0.0,
    )

    if day == today:
        elapsed_minutes = min(
            day_duration_minutes,
            max(0.0, (now_utc - start_utc).total_seconds() / 60.0),
        )
    elif day < today:
        elapsed_minutes = day_duration_minutes
    else:
        elapsed_minutes = 0.0

    day_progress_pct = min(
        100.0,
        elapsed_minutes / day_duration_minutes * 100
        if day_duration_minutes > 0 else 0.0,
    )
    elapsed_coverage_pct = min(
        100.0,
        minutes / elapsed_minutes * 100
        if elapsed_minutes > 0 else 0.0,
    )

    if elapsed_minutes < 30 or minutes < 30:
        elapsed_coverage_status = "INSUFFICIENT_SO_FAR"
    elif elapsed_coverage_pct >= 90:
        elapsed_coverage_status = "GOOD_SO_FAR"
    elif elapsed_coverage_pct >= 50:
        elapsed_coverage_status = "PARTIAL_SO_FAR"
    else:
        elapsed_coverage_status = "INSUFFICIENT_SO_FAR"

    if day == today:
        # PARTIAL_TODAY means the calendar day is still in progress. It does
        # not mean measurement coverage of elapsed time is poor.
        quality = "PARTIAL_TODAY" if minutes >= 30 else "INSUFFICIENT"
    else:
        quality = (
            "GOOD"
            if full_day_coverage_pct >= 90
            else ("PARTIAL" if full_day_coverage_pct >= 50 else "INSUFFICIENT")
        )

    pv = totals["pv_kwh"]
    direct = totals["direct_pv_self_use_kwh"]
    flex = totals["flex_load_kwh"]
    captured = totals["flex_pv_capture_kwh"]
    surplus = totals["pre_flex_surplus_kwh"]
    upper = min(flex, surplus)
    upper_gap = max(0.0, upper - captured)
    upper_score = captured / upper if upper > 0 else None
    planner = load_planner_history(day, planner_db)

    # Planner-history availability is reported separately. V0.1 does not pretend
    # to solve the full constrained replay optimisation yet.
    replay_context_usable = (
        planner["available"]
        and "PLAN_EMBEDDED_DECISION_OUTPUT" in planner["contextSources"]
        and planner["snapshotCount"] >= 8
    )

    power_sample_metrics = {k: round(v, 3) for k, v in totals.items()}
    power_sample_metrics["pv_self_consumption_rate"] = (
        None if pv <= 0 else round(direct / pv, 4)
    )
    metrics = dict(power_sample_metrics)
    # Grid boundary is P1. PV and self-consumption are promoted only with
    # sufficient paired cumulative-energy history; retain sampled integrals
    # separately for diagnosis and flex-allocation analysis.
    if energy_accounting["p1Coverage"] >= 0.95:
        metrics["grid_import_kwh"] = round(energy_accounting["importKWh"], 3)
        metrics["grid_export_kwh"] = round(energy_accounting["exportKWh"], 3)
    if energy_accounting["available"]:
        metrics["pv_kwh"] = round(energy_accounting["pvKWh"], 3)
        metrics["direct_pv_self_use_kwh"] = round(
            energy_accounting["pvSelfConsumedKWh"], 3
        )
        metrics["pv_self_consumption_rate"] = energy_accounting["pvSelfConsumptionRate"]
        metrics["house_consumption_kwh"] = round(
            metrics["pv_kwh"] + metrics["grid_import_kwh"]
            - metrics["grid_export_kwh"], 3
        )
    else:
        metrics["direct_pv_self_use_kwh"] = None
        metrics["pv_self_consumption_rate"] = None
    metrics["flex_pv_capture_rate_of_preflex_surplus"] = None if surplus <= 0 else round(captured / surplus, 4)

    ev_energy_accounting = {
        "authoritativeChargedEnergy": {
            "available": bool(easee_meter.get("available")),
            "chargedKWh": easee_meter.get("chargedKWh"),
            "coverageStatus": easee_meter.get("coverageStatus"),
            "reason": easee_meter.get("reason"),
            "source": easee_meter.get("source"),
            "metric": easee_meter.get("metric"),
            "baselineAt": easee_meter.get("baselineAt"),
            "latestAt": easee_meter.get("latestAt"),
            "observedDeltaKWh": easee_meter.get("observedDeltaKWh"),
        },
        "powerIntegratedEnergy": {
            "kWh": metrics["tesla_kwh"],
            "source": "ems-history.sqlite electrical_power_w samples",
            "semantics": "DERIVED_FROM_SAMPLED_POWER_INTEGRATION",
            "authoritativeChargedEnergy": False,
        },
        "derivedSourceAllocation": {
            "pvCoveredKWh": metrics["ev_pv_allocated_kwh"],
            "gridCoveredKWh": metrics["ev_grid_allocated_kwh"],
            "allocationBasisKWh": round(
                metrics["ev_pv_allocated_kwh"] + metrics["ev_grid_allocated_kwh"], 3
            ),
            "method": "SIMULTANEOUS_POWER_ALLOCATION_EV_FIRST_V0.1",
            "measuredDirectly": False,
            "authoritativeChargedEnergy": False,
            "interpretation": (
                "Derived allocation from sampled P1/PV/EV power; it is not a directly "
                "measured PV-to-EV or grid-to-EV energy flow."
            ),
        },
    }

    benchmark = {
        "mode": "SAME_FLEX_ENERGY_UNCONSTRAINED_UPPER_BOUND_V0.1",
        "actualFlexPvCaptureKWh": round(captured, 3),
        "upperBoundFlexPvCaptureKWh": round(upper, 3),
        "upperBoundGapKWh": round(upper_gap, 3),
        "upperBoundScore": None if upper_score is None else round(upper_score, 4),
        "constrainedOptimumAvailable": False,
        "constrainedOptimumStatus": (
            "REPLAY_CONTEXT_PRESENT_OPTIMIZER_NOT_IMPLEMENTED_V0.1"
            if replay_context_usable
            else "REPLAY_CONTEXT_INSUFFICIENT"
        ),
        "interpretation": (
            "Upper bound keeps the day's measured flexible-load energy constant but ignores detailed timing, "
            "availability, minimum-run, comfort and deadline constraints. A gap is a replay candidate, not proof of an EMS fault."
        ),
    }

    result = {
        "schema": "EMS_PI_DAY_PERFORMANCE_V0.1",
        "generatedAt": iso_z(datetime.now(timezone.utc)),
        "dateLocal": day.isoformat(),
        "timezone": "Europe/Amsterdam",
        "analysisContract": {
            "defaultQuestion": "Hoe heeft de EMS gepresteerd?",
            "defaultPeriod": "previous complete local day",
            "defaultCommand": "ems-performance yesterday",
            "objective": "MAXIMIZE_PV_SELF_CONSUMPTION_WITHOUT_MISCLASSIFYING_CONSTRAINT_DRIVEN_EXPORT",
        },
        "quality": {
            "status": quality,
            "integratedMinutes": round(minutes, 1),
            # Backwards-compatible field: coverage against the complete local
            # calendar day, not evidence completeness of elapsed time.
            "coveragePct": round(full_day_coverage_pct, 1),
            "coveragePctFullDay": round(full_day_coverage_pct, 1),
            "elapsedMinutes": round(elapsed_minutes, 1),
            "coveragePctElapsed": round(elapsed_coverage_pct, 1),
            "dayProgressPct": round(day_progress_pct, 1),
            "elapsedCoverageStatus": elapsed_coverage_status,
            "dayInProgress": day == today,
            "completeSampleCount": len(rows),
            "measurementQualityCounts": dict(quality_counts),
            "interpretation": (
                "For today, coveragePct/coveragePctFullDay is coverage against "
                "the full calendar day and must not be interpreted as missing "
                "measurement data. Use coveragePctElapsed and "
                "elapsedCoverageStatus to judge data completeness so far."
                if day == today
                else "For a completed day, full-day and elapsed-time coverage are equivalent."
            ),
        },
        "metrics": metrics,
        "energyAccounting": energy_accounting,
        "sampledPowerMetrics": power_sample_metrics,
        "powerSampleQuality": {
            "status": (
                "REVIEW_PV_P1_TIME_ALIGNMENT"
                if totals["pv_p1_impossible_export_intervals"] else "NO_IMPOSSIBLE_EXPORT_SAMPLES"
            ),
            "impossibleExportIntervals": int(totals["pv_p1_impossible_export_intervals"]),
            "impossibleExportEnergyKWh": round(totals["pv_p1_impossible_export_kwh"], 3),
            "interpretation": (
                "Samples where P1 export exceeds the sum of simultaneously archived "
                "inverter powers. This is a source-consistency diagnostic, not "
                "proof of an EMS missed opportunity or an instruction to change P1."
            ),
        },
        "evEnergyAccounting": ev_energy_accounting,
        "metricSemantics": {
            "pv_self_consumption_rate": {
                "provenanceClass": "DERIVED_FROM_ARCHIVED_ENERGY_INTERVALS",
                "source": "ems-history.sqlite/house_energy_intervals",
                "available": energy_accounting["available"],
                "interpretation": (
                    "Daily PV self-consumption is PV generated minus P1 export "
                    "from historical energy intervals with at least 95% paired "
                    "coverage. Sampled instantaneous inverter/P1 power never "
                    "supplies the authoritative day KPI."
                ),
            },
            "tesla_kwh": {
                "provenanceClass": "DERIVED_POWER_INTEGRAL",
                "source": "ems-history.sqlite/measurements tesla electrical_power_w",
                "authoritativeActualChargedEnergy": False,
                "interpretation": (
                    "Time-integrated sampled EV power. This is not the authoritative "
                    "charger energy meter and must not be presented as exact charged kWh."
                ),
            },
            "flex_pv_capture_kwh": {
                "provenanceClass": "DERIVED_ALLOCATION",
                "scope": "TESLA_PLUS_BOILER_FLEX",
                "directlyMeasured": False,
                "interpretation": (
                    "Derived contemporaneous PV allocation for the combined flexible load. "
                    "It is not directly measured PV energy delivered to the EV."
                ),
            },
            "flex_grid_energy_kwh": {
                "provenanceClass": "DERIVED_ALLOCATION",
                "scope": "TESLA_PLUS_BOILER_FLEX",
                "directlyMeasured": False,
                "interpretation": (
                    "Derived contemporaneous grid allocation for the combined flexible load. "
                    "It is not directly measured grid energy delivered to the EV."
                ),
            },
            "authoritativeEvChargedEnergy": {
                "provenanceClass": "MEASURED_CUMULATIVE_METER_DELTA",
                "preferredSource": "Easee meter_power cumulative kWh",
                "available": bool(easee_meter.get("available")),
                "reason": easee_meter.get("reason"),
                "interpretation": (
                    "Authoritative daily charged energy is exposed only when the archived "
                    "Easee cumulative meter has bounded day-boundary coverage."
                ),
            },
        },
        "benchmark": benchmark,
        "plannerHistory": planner,
        "surplusWindowsForReplay": windows,
        "verdict": verdict(upper_score, upper_gap, quality),
        "important": [
            "surplusWindowsForReplay are observations, not automatically missed EMS opportunities",
            "upperBoundScore is not the final constrained-theoretical-optimum score",
            "plannerHistory is used to explain decisions and will support a later constrained replay optimiser",
            "tesla_kwh is a sampled-power integral, not the authoritative Easee cumulative energy-meter delta",
            "flex_pv_capture_kwh and flex_grid_energy_kwh are derived combined-flex allocations, not directly measured EV source energy",
            "daily PV self-consumption KPI requires sufficient paired archived energy-interval coverage",
            "sampledPowerMetrics and powerSampleQuality expose instantaneous PV/P1 mismatch without changing P1 authority",
        ],
    }
    return result


def main(argv=None):
    try:
        args = parse_args(argv)
        day = resolve_day(args.day)
        report = build_report(day)
        print(json.dumps(report, indent=2, sort_keys=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema": "EMS_PI_DAY_PERFORMANCE_ERROR_V0.1",
            "status": "ERROR",
            "error": str(exc),
        }, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

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


def load_counter_delta(
    day,
    db_path,
    *,
    device_key,
    metric_key,
    cutoff_utc=None,
):
    start, end = bounds(day)
    cutoff = min(
        end,
        (cutoff_utc or datetime.now(timezone.utc)).astimezone(timezone.utc),
    )
    if cutoff <= start:
        return {
            "available": False,
            "reason": "COUNTER_PERIOD_NOT_STARTED",
            "deviceKey": device_key,
            "metricKey": metric_key,
        }
    if not db_path.exists():
        return {
            "available": False,
            "reason": "COUNTER_DB_MISSING",
            "deviceKey": device_key,
            "metricKey": metric_key,
        }

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        ids = con.execute(
            """
            SELECT d.id,m.id
            FROM devices d
            CROSS JOIN metrics m
            WHERE d.device_key=? AND m.metric_key=?
            """,
            (device_key, metric_key),
        ).fetchone()
        if not ids:
            return {
                "available": False,
                "reason": "COUNTER_NOT_COMMISSIONED",
                "deviceKey": device_key,
                "metricKey": metric_key,
            }

        device_id, metric_id = ids
        baseline = con.execute(
            """
            SELECT ts_utc,value_real,quality
            FROM measurements
            WHERE device_id=? AND metric_id=? AND ts_utc<=?
              AND value_real IS NOT NULL
            ORDER BY ts_utc DESC
            LIMIT 1
            """,
            (device_id, metric_id, iso_z(start)),
        ).fetchone()
        endpoint = con.execute(
            """
            SELECT ts_utc,value_real,quality
            FROM measurements
            WHERE device_id=? AND metric_id=? AND ts_utc<=?
              AND value_real IS NOT NULL
            ORDER BY ts_utc DESC
            LIMIT 1
            """,
            (device_id, metric_id, iso_z(cutoff)),
        ).fetchone()
    finally:
        con.close()

    if baseline is None:
        return {
            "available": False,
            "reason": "COUNTER_BASELINE_MISSING",
            "deviceKey": device_key,
            "metricKey": metric_key,
        }
    if endpoint is None:
        return {
            "available": False,
            "reason": "COUNTER_ENDPOINT_MISSING",
            "deviceKey": device_key,
            "metricKey": metric_key,
        }

    start_value = float(baseline[1])
    end_value = float(endpoint[1])
    delta = end_value - start_value
    if delta < -0.001:
        return {
            "available": False,
            "reason": "COUNTER_RESET_OR_DECREASE",
            "deviceKey": device_key,
            "metricKey": metric_key,
            "startValueKWh": round(start_value, 3),
            "endValueKWh": round(end_value, 3),
        }

    return {
        "available": True,
        "authority": "EASEE_CUMULATIVE_METER_DELTA",
        "deviceKey": device_key,
        "metricKey": metric_key,
        "startAt": baseline[0],
        "endAt": endpoint[0],
        "startValueKWh": round(start_value, 3),
        "endValueKWh": round(end_value, 3),
        "deliveredKWh": round(max(0.0, delta), 3),
        "startQuality": baseline[2],
        "endQuality": endpoint[2],
        "interpretation": (
            "Authoritative charged-energy delta from the cumulative Easee meter. "
            "This is measured delivered EV energy; it does not identify PV versus grid origin."
        ),
    }


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


def integrate(rows):
    totals = {
        "pv_kwh": 0.0,
        "grid_import_kwh": 0.0,
        "grid_export_kwh": 0.0,
        "house_consumption_kwh": 0.0,
        "direct_pv_self_use_kwh": 0.0,
        "boiler_kwh": 0.0,
        "tesla_kwh": 0.0,
        "tesla_pv_covered_derived_kwh": 0.0,
        "tesla_grid_covered_derived_kwh": 0.0,
        "quatt_kwh": 0.0,
        "flex_load_kwh": 0.0,
        "flex_pv_capture_kwh": 0.0,
        "flex_grid_energy_kwh": 0.0,
        "pre_flex_surplus_kwh": 0.0,
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
        direct = min(pv, house)
        available_for_flex = max(0.0, pv - base)
        tesla_pv = min(tesla, available_for_flex)
        tesla_grid = max(0.0, tesla - tesla_pv)
        boiler_pv = min(
            boiler,
            max(0.0, available_for_flex - tesla_pv),
        )
        flex_pv = tesla_pv + boiler_pv
        preflex = export + flex_pv

        totals["pv_kwh"] += pv / 1000 * h
        totals["grid_import_kwh"] += imp / 1000 * h
        totals["grid_export_kwh"] += export / 1000 * h
        totals["house_consumption_kwh"] += house / 1000 * h
        totals["direct_pv_self_use_kwh"] += direct / 1000 * h
        totals["boiler_kwh"] += boiler / 1000 * h
        totals["tesla_kwh"] += tesla / 1000 * h
        totals["tesla_pv_covered_derived_kwh"] += tesla_pv / 1000 * h
        totals["tesla_grid_covered_derived_kwh"] += tesla_grid / 1000 * h
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
    now_local = now_utc.astimezone(TZ)
    today = now_local.date()

    ev_meter_energy = load_counter_delta(
        day,
        measurement_db,
        device_key="tesla",
        metric_key="energy_delivered_kwh",
        cutoff_utc=now_utc,
    )

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

    metrics = {k: round(v, 3) for k, v in totals.items()}
    metrics["tesla_power_integral_kwh"] = metrics["tesla_kwh"]
    metrics["tesla_meter_delivered_kwh"] = (
        ev_meter_energy.get("deliveredKWh")
        if ev_meter_energy.get("available")
        else None
    )
    metrics["pv_self_consumption_rate"] = None if pv <= 0 else round(direct / pv, 4)
    metrics["flex_pv_capture_rate_of_preflex_surplus"] = None if surplus <= 0 else round(captured / surplus, 4)

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
        "evEnergySemantics": {
            "actualChargedEnergy": ev_meter_energy,
            "powerIntegral": {
                "metric": "tesla_power_integral_kwh",
                "authority": "DERIVED_FROM_SAMPLED_EV_POWER",
                "measuredDirectly": False,
                "interpretation": (
                    "Time integral of sampled Tesla/Easee power. Useful as a derived estimate, "
                    "but not authoritative charged energy when the Easee cumulative meter delta is available."
                ),
            },
            "pvGridAllocation": {
                "pvMetric": "tesla_pv_covered_derived_kwh",
                "gridMetric": "tesla_grid_covered_derived_kwh",
                "authority": "DERIVED_ALLOCATION_FROM_P1_PV_EV_TIMING",
                "measuredDirectly": False,
                "allocationOrder": "EV_BEFORE_WW_WITHIN_FLEX",
                "interpretation": (
                    "Derived attribution from simultaneous P1/PV/EV power. "
                    "It is not a directly measured physical split of charger energy into PV and grid origin."
                ),
            },
            "legacyTeslaKWh": {
                "metric": "tesla_kwh",
                "semantics": "ALIAS_OF_TESLA_POWER_INTEGRAL_KWH",
                "deprecatedForActualChargedEnergyClaims": True,
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
            "tesla_meter_delivered_kwh is authoritative only when evEnergySemantics.actualChargedEnergy.available=true",
            "tesla_pv_covered_derived_kwh and tesla_grid_covered_derived_kwh are derived allocations, not direct measurements",
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

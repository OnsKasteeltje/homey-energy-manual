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
    con = sqlite3.connect(db_path)
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
        flex_pv = min(flex, available_for_flex)
        preflex = export + flex_pv

        totals["pv_kwh"] += pv / 1000 * h
        totals["grid_import_kwh"] += imp / 1000 * h
        totals["grid_export_kwh"] += export / 1000 * h
        totals["house_consumption_kwh"] += house / 1000 * h
        totals["direct_pv_self_use_kwh"] += direct / 1000 * h
        totals["boiler_kwh"] += boiler / 1000 * h
        totals["tesla_kwh"] += tesla / 1000 * h
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
    con = sqlite3.connect(db_path)
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


def build_report(day, measurement_db=MEASUREMENTS_DB, planner_db=PLANNER_DB):
    rows, quality_counts = load_measurements(day, measurement_db)
    if len(rows) < 2:
        raise RuntimeError(f"insufficient complete measurement samples for {day}")

    totals, integrated_s, windows = integrate(rows)
    minutes = integrated_s / 60
    today = datetime.now(TZ).date()
    coverage_pct = min(100.0, minutes / FULL_DAY_MINUTES * 100)
    if day == today:
        quality = "PARTIAL_TODAY" if minutes >= 30 else "INSUFFICIENT"
    else:
        quality = "GOOD" if coverage_pct >= 90 else ("PARTIAL" if coverage_pct >= 50 else "INSUFFICIENT")

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
            "coveragePct": round(coverage_pct, 1),
            "completeSampleCount": len(rows),
            "measurementQualityCounts": dict(quality_counts),
        },
        "metrics": metrics,
        "benchmark": benchmark,
        "plannerHistory": planner,
        "surplusWindowsForReplay": windows,
        "verdict": verdict(upper_score, upper_gap, quality),
        "important": [
            "surplusWindowsForReplay are observations, not automatically missed EMS opportunities",
            "upperBoundScore is not the final constrained-theoretical-optimum score",
            "plannerHistory is used to explain decisions and will support a later constrained replay optimiser",
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

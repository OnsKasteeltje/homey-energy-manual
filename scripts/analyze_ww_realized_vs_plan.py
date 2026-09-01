#!/usr/bin/env python3
"""Offline WW realized-vs-plan analysis.

Consumes already-published JSON only. No Homey, device, or network access.

Inputs:
  --day docs/data/energy-day-v2.json (raw day payload or wrapper with .day)
  --planner-history optional compact planner-slot history JSON

Outputs:
  --csv quarter-level comparison
  --summary JSON with actual vs hindsight-optimal WW metrics
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BOILER_W_DEFAULT = 1900.0
SLOT_MIN = 15


def parse_iso(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def unwrap_day(obj):
    return obj.get("day", obj)


def quarter_floor(dt):
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


def mean(values):
    xs = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return sum(xs) / len(xs) if xs else None


def aggregate_day(day):
    buckets = defaultdict(list)
    for s in day.get("samples", []):
        ts = parse_iso(s.get("ts"))
        if ts is None or s.get("p1Valid") is not True:
            continue
        buckets[quarter_floor(ts)].append(s)

    rows = []
    for start in sorted(buckets):
        samples = buckets[start]
        p1 = mean([s.get("p1W") for s in samples])
        se = mean([s.get("solarEdgeW") for s in samples]) or 0.0
        gw42 = mean([s.get("goodWe4200W") for s in samples]) or 0.0
        gw20 = mean([s.get("goodWe2000W") for s in samples]) or 0.0
        pv = se + gw42 + gw20
        boiler = mean([s.get("boilerW") for s in samples]) or 0.0
        tesla = mean([s.get("teslaW") for s in samples]) or 0.0
        # p1W sign contract used by Planner: + import, - export; house = p1 + PV.
        house = None if p1 is None else p1 + pv
        base_without_ww = None if house is None else max(0.0, house - boiler - tesla)
        surplus_without_ww = None if base_without_ww is None else max(0.0, pv - base_without_ww - tesla)
        marginal_import_ww = None if surplus_without_ww is None else max(0.0, boiler - surplus_without_ww)
        ww_pv_covered = None if marginal_import_ww is None else max(0.0, boiler - marginal_import_ww)
        rows.append({
            "start": start,
            "samples": len(samples),
            "p1W": p1,
            "importW": None if p1 is None else max(0.0, p1),
            "exportW": None if p1 is None else max(0.0, -p1),
            "pvW": pv,
            "houseW": house,
            "baseWithoutWwW": base_without_ww,
            "boilerW": boiler,
            "teslaW": tesla,
            "surplusWithoutWwW": surplus_without_ww,
            "wwMarginalImportW": marginal_import_ww,
            "wwPvCoveredW": ww_pv_covered,
        })
    return rows


def attach_planner(rows, planner_history):
    by_start = {}
    if planner_history:
        records = planner_history.get("records", planner_history if isinstance(planner_history, list) else [])
        for r in records:
            dt = parse_iso(r.get("start"))
            if dt:
                by_start[quarter_floor(dt)] = r
    for row in rows:
        p = by_start.get(row["start"], {})
        row["plannerWarmWater"] = p.get("warmWater")
        row["plannerWwTargetW"] = p.get("WW_target_W", p.get("wwTargetW"))
        row["plannerPvForecastW"] = p.get("pvForecastW")
        row["plannerBaseForecastW"] = p.get("baseLoadForecastW")
        row["price_eur_kwh"] = p.get("price_eur_kwh")
    return rows


def optimize_hindsight(rows, required_energy_kwh, boiler_w, deadline_hour=19):
    slot_energy = boiler_w * SLOT_MIN / 60000.0
    required_slots = int(math.ceil(required_energy_kwh / slot_energy - 1e-12)) if required_energy_kwh > 0 else 0
    candidates = []
    for row in rows:
        # day JSON timestamps are UTC; deadline must be prefiltered by local-day publisher/analyzer integration.
        # For present use, accept only daylight/WW candidate slots whose UTC hour maps before local deadline through supplied dataset order.
        if row["surplusWithoutWwW"] is None:
            continue
        marginal = max(0.0, boiler_w - row["surplusWithoutWwW"])
        price = row.get("price_eur_kwh")
        candidates.append((marginal, float("inf") if price is None else float(price), row["start"], row))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    chosen = {x[3]["start"] for x in candidates[:required_slots]}
    for row in rows:
        row["optimalWw"] = row["start"] in chosen
        row["optimalWwTargetW"] = boiler_w if row["optimalWw"] else 0.0
        row["optimalMarginalImportW"] = max(0.0, boiler_w - row["surplusWithoutWwW"]) if row["optimalWw"] and row["surplusWithoutWwW"] is not None else 0.0
    return rows


def summarize(rows, boiler_w):
    h = SLOT_MIN / 60.0
    actual_energy = sum((r["boilerW"] or 0.0) * h / 1000.0 for r in rows)
    actual_grid = sum((r["wwMarginalImportW"] or 0.0) * h / 1000.0 for r in rows)
    actual_pv = max(0.0, actual_energy - actual_grid)
    optimal_energy = sum((r["optimalWwTargetW"] or 0.0) * h / 1000.0 for r in rows)
    optimal_grid = sum((r["optimalMarginalImportW"] or 0.0) * h / 1000.0 for r in rows)
    optimal_pv = max(0.0, optimal_energy - optimal_grid)

    def cost(prefix):
        total = 0.0
        known = True
        for r in rows:
            p = r.get("price_eur_kwh")
            w = r["wwMarginalImportW"] if prefix == "actual" else r["optimalMarginalImportW"]
            if w and p is None:
                known = False
            if p is not None:
                total += (w or 0.0) * h / 1000.0 * float(p)
        return total if known else None

    actual_cost = cost("actual")
    optimal_cost = cost("optimal")
    return {
        "schema": "EM2_WW_REALIZED_VS_PLAN_ANALYSIS_V0.1",
        "slotMinutes": SLOT_MIN,
        "modeledBoilerW": boiler_w,
        "actual": {
            "wwEnergyKWh": round(actual_energy, 3),
            "pvCoveredKWh": round(actual_pv, 3),
            "marginalGridImportKWh": round(actual_grid, 3),
            "importCostEur": None if actual_cost is None else round(actual_cost, 4),
        },
        "hindsightOptimal": {
            "wwEnergyKWh": round(optimal_energy, 3),
            "pvCoveredKWh": round(optimal_pv, 3),
            "marginalGridImportKWh": round(optimal_grid, 3),
            "importCostEur": None if optimal_cost is None else round(optimal_cost, 4),
        },
        "potential": {
            "extraPvSelfConsumptionKWh": round(optimal_pv - actual_pv, 3),
            "avoidedGridImportKWh": round(actual_grid - optimal_grid, 3),
            "costDifferenceEur": None if actual_cost is None or optimal_cost is None else round(actual_cost - optimal_cost, 4),
        },
        "note": "Hindsight optimum uses realized PV/base load and is an oracle upper bound, not a forecast-achievable Planner score.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--planner-history")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--boiler-w", type=float, default=BOILER_W_DEFAULT)
    args = ap.parse_args()

    day = unwrap_day(load_json(args.day))
    rows = aggregate_day(day)
    planner = load_json(args.planner_history) if args.planner_history else None
    attach_planner(rows, planner)

    actual_energy = sum((r["boilerW"] or 0.0) * SLOT_MIN / 60000.0 for r in rows)
    optimize_hindsight(rows, actual_energy, args.boiler_w)
    summary = summarize(rows, args.boiler_w)

    fields = [
        "start","samples","pvW","baseWithoutWwW","boilerW","importW","exportW",
        "wwPvCoveredW","wwMarginalImportW","plannerWarmWater","plannerWwTargetW",
        "plannerPvForecastW","plannerBaseForecastW","price_eur_kwh","optimalWw",
        "optimalWwTargetW","optimalMarginalImportW"
    ]
    with open(args.csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = {k: row.get(k) for k in fields}
            out["start"] = row["start"].isoformat().replace("+00:00", "Z")
            w.writerow(out)

    Path(args.summary).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

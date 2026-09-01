#!/usr/bin/env python3
"""Reconstruct WW realized-vs-plan from GitHub commit history only.

No Homey API/device access. Reads historical revisions of published JSON files
from this public GitHub repository and emits an approximate 15-minute replay.

This is intentionally an observational fallback: each 15-minute published
energy-state snapshot is treated as representative of that quarter. It is not
as accurate as the native 5-minute day-series collector.

Important: WW marginal import is derived from fresh P1 net power, not from the
asynchronous reconstructed PV/house balance. This avoids false surplus caused
by stale PV source timestamps.
"""
from __future__ import annotations

import argparse, csv, json, math, os, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "OnsKasteeltje/homey-energy-manual"
STATE_PATH = "docs/data/energy-state-v2.json"
PLANNER_PATH = "docs/data/energy-planner-shadow.json"
SLOT_MIN = 15
BOILER_MODEL_W = 1900.0


def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ems-ww-history-replay"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def commits_for(path, start, end):
    q = urllib.parse.urlencode({"path": path, "since": iso_z(start), "until": iso_z(end), "per_page": 100})
    return get_json(f"https://api.github.com/repos/{REPO}/commits?{q}")


def file_at(path, sha):
    return get_json(f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}")


def quarter_floor(dt):
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def first_action_for_quarter(snapshot, qstart):
    actions = (((snapshot or {}).get("plan") or {}).get("plan") or {}).get("actions") or []
    for a in actions:
        try:
            if quarter_floor(parse_ts(a.get("start"))) == qstart:
                return a
        except Exception:
            pass
    return None


def marginal_import_for_added_load(grid_w, load_w):
    """Extra grid import caused by adding load_w to current net P1 power.

    P1 sign contract: positive=import, negative=export.
    """
    before_import = max(0.0, float(grid_w))
    after_import = max(0.0, float(grid_w) + float(load_w))
    return max(0.0, after_import - before_import)


def marginal_import_of_existing_load(grid_w, load_w):
    """Grid import attributable to an already-running load."""
    before_import = max(0.0, float(grid_w) - float(load_w))
    actual_import = max(0.0, float(grid_w))
    return max(0.0, actual_import - before_import)


def replay(date_local, utc_offset_hours=2):
    local_start = datetime.fromisoformat(date_local).replace(tzinfo=timezone(timedelta(hours=utc_offset_hours)))
    start = local_start.astimezone(timezone.utc)
    end = (local_start + timedelta(days=1)).astimezone(timezone.utc) - timedelta(microseconds=1)

    state_commits = commits_for(STATE_PATH, start, end)
    planner_commits = commits_for(PLANNER_PATH, start, end)

    state_by_q = {}
    for c in reversed(state_commits):
        snap = file_at(STATE_PATH, c["sha"])
        generated = parse_ts((snap.get("meta") or {}).get("generated_at") or c["commit"]["committer"]["date"])
        state_by_q[quarter_floor(generated)] = snap

    planner_by_q = {}
    for c in reversed(planner_commits):
        snap = file_at(PLANNER_PATH, c["sha"])
        generated = parse_ts(snap.get("generatedAt") or snap.get("publishedAt") or c["commit"]["committer"]["date"])
        planner_by_q[quarter_floor(generated)] = snap

    rows = []
    for q in sorted(state_by_q):
        s = state_by_q[q]
        grid = (s.get("grid") or {}).get("power_w")
        pv = (s.get("pv") or {}).get("total_w")
        hot = s.get("hot_water") or {}
        boiler = float(hot.get("boiler_power_w") or 0)
        tesla = float((s.get("tesla") or {}).get("power_w") or 0)
        if not isinstance(grid, (int, float)):
            continue
        grid = float(grid)
        pv = float(pv) if isinstance(pv, (int, float)) else None
        balance = s.get("balance") or {}
        source_timing = balance.get("source_timing") or {}
        pv_reconstruction_trustworthy = bool(source_timing.get("synchronized") is True and (balance.get("control_gate") or {}).get("derived_house_balance_valid") is True)

        # P1-only counterfactual is robust against stale asynchronous PV values.
        actual_ww_import = marginal_import_of_existing_load(grid, boiler) if boiler > 100 else 0.0
        actual_ww_pv = max(0.0, boiler - actual_ww_import) if boiler > 100 else 0.0
        add_boiler_import = marginal_import_for_added_load(grid, BOILER_MODEL_W) if boiler <= 100 else None

        # Reconstructed base/PV are retained only for observability and flagged.
        house = None if pv is None else grid + pv
        base_without_ww = None if house is None else max(0.0, house - boiler - tesla)

        ps = planner_by_q.get(q)
        action = first_action_for_quarter(ps, q) if ps else None
        rows.append({
            "start": q,
            "gridW": grid,
            "importW": max(0.0, grid),
            "exportW": max(0.0, -grid),
            "pvW": pv,
            "pvReconstructionTrustworthy": pv_reconstruction_trustworthy,
            "baseWithoutWwW": base_without_ww,
            "boilerW": boiler,
            "teslaW": tesla,
            "actualWwMarginalImportW": actual_ww_import,
            "actualWwPvCoveredW": actual_ww_pv,
            "candidateAddedBoilerMarginalImportW": add_boiler_import,
            "plannerWarmWater": None if action is None else action.get("warmWater"),
            "plannerPvForecastW": None if action is None else action.get("pvForecastW"),
            "plannerBaseForecastW": None if action is None else action.get("baseLoadForecastW"),
            "price_eur_kwh": None if action is None else action.get("price_eur_kwh"),
        })

    h = SLOT_MIN / 60.0
    actual_energy = sum(r["boilerW"] * h / 1000.0 for r in rows if r["boilerW"] > 100)
    required_slots = math.ceil(actual_energy / (BOILER_MODEL_W * h / 1000.0) - 1e-12) if actual_energy > 0 else 0
    deadline_utc = local_start.replace(hour=19, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    candidates = []
    for r in rows:
        if r["start"] >= deadline_utc:
            continue
        # If WW already ran in this snapshot, remove it first to get the
        # counterfactual grid without WW, then add the modeled 1900 W target.
        counterfactual_grid_without_ww = r["gridW"] - r["boilerW"] if r["boilerW"] > 100 else r["gridW"]
        marginal = marginal_import_for_added_load(counterfactual_grid_without_ww, BOILER_MODEL_W)
        price = r["price_eur_kwh"]
        price_sort = float("inf") if not isinstance(price, (int, float)) else float(price)
        candidates.append((marginal, price_sort, r["start"], r, counterfactual_grid_without_ww))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    chosen = {x[3]["start"] for x in candidates[:required_slots]}

    for r in rows:
        r["optimalWw"] = r["start"] in chosen
        r["optimalWwTargetW"] = BOILER_MODEL_W if r["optimalWw"] else 0.0
        if r["optimalWw"]:
            no_ww_grid = r["gridW"] - r["boilerW"] if r["boilerW"] > 100 else r["gridW"]
            r["optimalMarginalImportW"] = marginal_import_for_added_load(no_ww_grid, BOILER_MODEL_W)
            r["optimalPvCoveredW"] = BOILER_MODEL_W - r["optimalMarginalImportW"]
        else:
            r["optimalMarginalImportW"] = 0.0
            r["optimalPvCoveredW"] = 0.0

    actual_grid = sum(r["actualWwMarginalImportW"] * h / 1000.0 for r in rows)
    actual_pv = sum(r["actualWwPvCoveredW"] * h / 1000.0 for r in rows)
    optimal_grid = sum(r["optimalMarginalImportW"] * h / 1000.0 for r in rows)
    optimal_pv = sum(r["optimalPvCoveredW"] * h / 1000.0 for r in rows)

    def priced_cost(which):
        total = 0.0
        complete = True
        for r in rows:
            w = r["actualWwMarginalImportW"] if which == "actual" else r["optimalMarginalImportW"]
            if w <= 0:
                continue
            p = r.get("price_eur_kwh")
            if not isinstance(p, (int, float)):
                complete = False
                continue
            total += w * h / 1000.0 * float(p)
        return total if complete else None

    ac = priced_cost("actual")
    oc = priced_cost("optimal")
    trusted_pv_rows = sum(1 for r in rows if r["pvReconstructionTrustworthy"])
    summary = {
        "schema": "EM2_WW_GITHUB_HISTORY_REPLAY_V0.2",
        "dateLocal": date_local,
        "method": "15_MIN_GITHUB_PUBLICATION_P1_COUNTERFACTUAL_APPROXIMATION",
        "homeyReads": 0,
        "physicalWrites": 0,
        "stateSnapshots": len(state_by_q),
        "plannerSnapshots": len(planner_by_q),
        "pvReconstructionTrustworthySnapshots": trusted_pv_rows,
        "observedWwEnergyKWhApprox": round(actual_energy, 3),
        "actualPvCoveredKWhApprox": round(actual_pv, 3),
        "actualMarginalGridImportKWhApprox": round(actual_grid, 3),
        "optimalPvCoveredKWhApprox": round(optimal_pv, 3),
        "optimalMarginalGridImportKWhApprox": round(optimal_grid, 3),
        "potentialExtraPvSelfConsumptionKWhApprox": round(optimal_pv - actual_pv, 3),
        "potentialAvoidedGridImportKWhApprox": round(actual_grid - optimal_grid, 3),
        "actualImportCostEurApprox": None if ac is None else round(ac, 4),
        "optimalImportCostEurApprox": None if oc is None else round(oc, 4),
        "potentialCostDifferenceEurApprox": None if ac is None or oc is None else round(ac - oc, 4),
        "caveat": "15-minute publications are instantaneous snapshots, not interval means. PV/base fields may be asynchronous; optimization therefore uses P1 net-power counterfactuals. Results are directional until 5-minute day-series publication is available.",
    }
    return rows, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="local date YYYY-MM-DD")
    ap.add_argument("--utc-offset-hours", type=int, default=2)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()
    rows, summary = replay(args.date, args.utc_offset_hours)
    fields = [
        "start","gridW","importW","exportW","pvW","pvReconstructionTrustworthy","baseWithoutWwW","boilerW","teslaW",
        "actualWwPvCoveredW","actualWwMarginalImportW","candidateAddedBoilerMarginalImportW","plannerWarmWater","plannerPvForecastW",
        "plannerBaseForecastW","price_eur_kwh","optimalWw","optimalWwTargetW","optimalPvCoveredW","optimalMarginalImportW"
    ]
    with open(args.csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            out = {k: r.get(k) for k in fields}
            out["start"] = iso_z(r["start"])
            w.writerow(out)
    Path(args.summary).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""WW Seasonal Source Advisor v0.4 PI SHADOW.

Read-only economic advisor. It never controls Homey or physical devices.
It values the last 14 complete local days from the Pi SQLite history and
compares a 1.9 kW electric-boiler counterfactual with CV hot-water heat.
"""

import argparse
import json
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

DB_DEFAULT = Path("/home/jeroen/ems/data/ems-history.sqlite")
HERE = Path(__file__).resolve().parent
CONTRACTS_DEFAULT = HERE / "seasonal_contracts.json"
STATE_DEFAULT = Path("/home/jeroen/ems/data/ww-seasonal-advisor-state.json")
OUTPUT_DEFAULT = Path("/home/jeroen/ems/data/ww-seasonal-advisor.json")
TZ = ZoneInfo("Europe/Amsterdam")

SCHEMA = "EMS_WW_SEASONAL_SOURCE_V0.4_PI"
WINDOW_DAYS = 14
MIN_VALID_DAYS = 7
CONFIRM_DAYS = 5
HYSTERESIS_EUR_USEFUL_KWH = 0.03
BOILER_W = 1900.0
BOILER_EFFICIENCY = 0.98
CV_EFFICIENCY = 0.90
GAS_USABLE_KWH_PER_M3 = 9.77
WINDOW_START = (9, 30)
WINDOW_END = (19, 0)
FRESHNESS_HOURS = 36


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {} if default is None else default


def contract_for(day, cfg):
    ds = day.isoformat()
    for p in cfg["periods"]:
        if p["from"] <= ds <= p["through"]:
            return p
    raise ValueError(f"No contract period for {ds}")


def offpeak(local_dt):
    # NL conventional dual-tariff window: weekends plus 23:00-07:00.
    return local_dt.weekday() >= 5 or local_dt.hour >= 23 or local_dt.hour < 7


def import_tariff(contract, local_dt):
    key = "electricity_import_offpeak_eur_kwh" if offpeak(local_dt) else "electricity_import_normal_eur_kwh"
    return float(contract[key])


def pv_opportunity_tariff(contract, local_dt):
    method = contract["pv_opportunity_method"]
    if method == "IMPORT_TARIFF":
        return import_tariff(contract, local_dt)
    if method == "NET_EXPORT_VALUE":
        return float(contract["net_export_value_eur_kwh"])
    raise ValueError(f"Unsupported pv_opportunity_method={method}")


def fetch_slots(con, day):
    start_local = datetime.combine(day, datetime.min.time(), TZ)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    end_utc = end_local.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    sql = """
    SELECT x.slot_start_utc, d.device_key, x.value_avg, x.energy_wh, x.quality
      FROM measurements_15m x
      JOIN devices d ON d.id=x.device_id
      JOIN metrics m ON m.id=x.metric_id
     WHERE m.metric_key='electrical_power_w'
       AND d.device_key IN ('grid_p1','boiler')
       AND x.slot_start_utc>=? AND x.slot_start_utc<?
     ORDER BY x.slot_start_utc
    """
    rows = con.execute(sql, (start_utc, end_utc)).fetchall()
    slots = {}
    for ts, dev, value_avg, energy_wh, quality in rows:
        slots.setdefault(ts, {})[dev] = {
            "w": float(value_avg or 0),
            "wh": None if energy_wh is None else float(energy_wh),
            "quality": quality,
        }
    return slots


def day_boiler_input_kwh(slots):
    total_wh = 0.0
    seen = 0
    for s in slots.values():
        b = s.get("boiler")
        if not b:
            continue
        seen += 1
        total_wh += b["wh"] if b["wh"] is not None else max(0.0, b["w"]) * 0.25
    return total_wh / 1000.0 if seen else None


def eligible_counterfactual_slots(slots):
    out = []
    for ts, s in slots.items():
        g = s.get("grid_p1")
        if not g:
            continue
        local = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TZ)
        hm = (local.hour, local.minute)
        if WINDOW_START <= hm < WINDOW_END:
            out.append((local, s))
    return out


def simulate_day(day, slots, required_input_kwh, contract):
    candidates = eligible_counterfactual_slots(slots)
    # Require meaningful coverage of the 09:30-19:00 window (38 quarter hours).
    if len(candidates) < 30:
        return None

    slot_need = BOILER_W * 0.25 / 1000.0
    remaining = required_input_kwh
    ranked = []

    for local, s in candidates:
        grid_w = s["grid_p1"]["w"]
        boiler_w_observed = s.get("boiler", {}).get("w", 0.0)
        # Remove observed boiler from P1 before inserting the counterfactual load.
        base_grid_w = grid_w - max(0.0, boiler_w_observed)
        export_kwh_available = max(0.0, -base_grid_w) * 0.25 / 1000.0
        pv_price = pv_opportunity_tariff(contract, local)
        grid_price = import_tariff(contract, local)

        pv_part = min(slot_need, export_kwh_available)
        grid_part = slot_need - pv_part
        marginal_cost = pv_part * pv_price + grid_part * grid_price
        ranked.append((marginal_cost / slot_need, local, export_kwh_available, pv_price, grid_price))

    ranked.sort(key=lambda x: (x[0], x[1]))
    cost = pv_kwh = grid_kwh = used = 0.0
    for _, local, export_avail, pv_price, grid_price in ranked:
        if remaining <= 1e-9:
            break
        take = min(slot_need, remaining)
        pv_part = min(take, export_avail)
        grid_part = take - pv_part
        cost += pv_part * pv_price + grid_part * grid_price
        pv_kwh += pv_part
        grid_kwh += grid_part
        used += take
        remaining -= take

    if remaining > 0.05:
        return None
    useful = used * BOILER_EFFICIENCY
    return {
        "date": day.isoformat(),
        "contractId": contract["id"],
        "inputKWh": round(used, 4),
        "usableHeatKWh": round(useful, 4),
        "costEur": round(cost, 5),
        "costEurPerUsableKWh": round(cost / useful, 5),
        "pvOpportunityKWh": round(pv_kwh, 4),
        "gridKWh": round(grid_kwh, 4),
        "pvOpportunityShare": round(pv_kwh / used, 4) if used else 0,
    }


def cv_cost_for_days(days, required_input_kwh, contracts):
    useful = required_input_kwh * BOILER_EFFICIENCY
    costs = []
    for d in days:
        c = contract_for(d, contracts)
        per_useful = float(c["gas_eur_m3"]) / (GAS_USABLE_KWH_PER_M3 * CV_EFFICIENCY)
        costs.append(per_useful)
    return sum(costs) / len(costs), useful


def evaluate(db_path, contracts_path, state_path, mode, now=None):
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(TZ)
    as_of = now_local.date() - timedelta(days=1)
    window_start = as_of - timedelta(days=WINDOW_DAYS - 1)
    contracts = load_json(contracts_path)
    prior = load_json(state_path, {})

    con = sqlite3.connect(db_path)
    try:
        by_day = {}
        observed_inputs = []
        for i in range(WINDOW_DAYS):
            d = window_start + timedelta(days=i)
            slots = fetch_slots(con, d)
            by_day[d] = slots
            kwh = day_boiler_input_kwh(slots)
            if kwh is not None and kwh >= 0.5:
                observed_inputs.append(kwh)
    finally:
        con.close()

    latest_with_grid = max((d for d, slots in by_day.items() if any("grid_p1" in s for s in slots.values())), default=None)
    generated = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    base = {
        "schema": SCHEMA,
        "generatedAt": generated,
        "controlMode": "PURE_SHADOW",
        "readOnly": True,
        "manualSwitchOnly": True,
        "currentMode": mode,
        "policy": {
            "windowDays": WINDOW_DAYS,
            "minValidDays": MIN_VALID_DAYS,
            "confirmDays": CONFIRM_DAYS,
            "hysteresisEurPerUsableKWh": HYSTERESIS_EUR_USEFUL_KWH,
            "analysisCadence": "DAILY_20:30_EUROPE_AMSTERDAM",
            "completeDaysOnly": True,
            "freshnessHours": FRESHNESS_HOURS,
            "boilerSimulationWindow": "09:30-19:00",
            "boilerExpectedW": int(BOILER_W),
        },
        "safety": {"deviceReads": False, "deviceWrites": False, "automaticSourceSwitch": False},
    }

    if latest_with_grid is None or (as_of - latest_with_grid).days * 24 > FRESHNESS_HOURS:
        base.update({
            "status": "BLOCKED_DATA_STALE",
            "advice": "KEEP_CURRENT",
            "candidate": "KEEP_CURRENT",
            "reason": f"latest complete usable history day={latest_with_grid}",
            "confirmation": {"streakDays": 0, "requiredDays": CONFIRM_DAYS, "confirmed": False},
            "analysis": {"asOfDate": as_of.isoformat(), "latestDataDate": None if latest_with_grid is None else latest_with_grid.isoformat()},
        })
        return base

    if len(observed_inputs) < MIN_VALID_DAYS:
        base.update({
            "status": "WARMUP_INSUFFICIENT_HISTORY",
            "advice": "KEEP_CURRENT",
            "candidate": "KEEP_CURRENT",
            "reason": f"{len(observed_inputs)}/{MIN_VALID_DAYS} measured boiler days in 14-day window",
            "confirmation": {"streakDays": 0, "requiredDays": CONFIRM_DAYS, "confirmed": False},
            "analysis": {"asOfDate": as_of.isoformat(), "validDays": len(observed_inputs)},
        })
        return base

    reference_input = median(observed_inputs)
    simulations = []
    for d, slots in by_day.items():
        sim = simulate_day(d, slots, reference_input, contract_for(d, contracts))
        if sim:
            simulations.append(sim)

    if len(simulations) < MIN_VALID_DAYS:
        base.update({
            "status": "WARMUP_INSUFFICIENT_HISTORY",
            "advice": "KEEP_CURRENT",
            "candidate": "KEEP_CURRENT",
            "reason": f"{len(simulations)}/{MIN_VALID_DAYS} valid counterfactual days in 14-day window",
            "confirmation": {"streakDays": 0, "requiredDays": CONFIRM_DAYS, "confirmed": False},
            "analysis": {"asOfDate": as_of.isoformat(), "validDays": len(simulations), "referenceBoilerInputKWh": round(reference_input, 3)},
        })
        return base

    boiler_cost = sum(x["costEur"] for x in simulations) / sum(x["usableHeatKWh"] for x in simulations)
    sim_dates = [date.fromisoformat(x["date"]) for x in simulations]
    cv_cost, _ = cv_cost_for_days(sim_dates, reference_input, contracts)
    pv_share = sum(x["pvOpportunityKWh"] for x in simulations) / sum(x["inputKWh"] for x in simulations)

    if mode == "BOILER" and cv_cost + HYSTERESIS_EUR_USEFUL_KWH < boiler_cost:
        candidate = "ADVISE_SWITCH_TO_CV"
    elif mode == "CV" and boiler_cost + HYSTERESIS_EUR_USEFUL_KWH < cv_cost:
        candidate = "ADVISE_SWITCH_TO_BOILER"
    else:
        candidate = "KEEP_CURRENT"

    prior_candidate = prior.get("candidate")
    prior_streak = int(prior.get("confirmation", {}).get("streakDays", 0) or 0)
    streak = (prior_streak + 1) if candidate != "KEEP_CURRENT" and candidate == prior_candidate else (1 if candidate != "KEEP_CURRENT" else 0)
    confirmed = streak >= CONFIRM_DAYS
    advice = candidate if confirmed else "KEEP_CURRENT"

    base.update({
        "status": "OK",
        "advice": advice,
        "candidate": candidate,
        "reason": "confirmed economic switch" if confirmed else ("candidate awaiting confirmation" if candidate != "KEEP_CURRENT" else "difference within hysteresis/current source remains preferable"),
        "confirmation": {"streakDays": streak, "requiredDays": CONFIRM_DAYS, "confirmed": confirmed},
        "analysis": {
            "asOfDate": as_of.isoformat(),
            "windowStartDate": window_start.isoformat(),
            "validDays": len(simulations),
            "minValidDays": MIN_VALID_DAYS,
            "referenceBoilerInputKWh": round(reference_input, 3),
            "boilerCostEurPerUsableKWh": round(boiler_cost, 5),
            "cvCostEurPerUsableKWh": round(cv_cost, 5),
            "deltaBoilerMinusCv": round(boiler_cost - cv_cost, 5),
            "pvOpportunityShare": round(pv_share, 4),
            "costMethod": "PI_15M_COUNTERFACTUAL_1900W_CONTRACT_EFFECTIVE",
            "contractsUsed": sorted(set(x["contractId"] for x in simulations)),
        },
    })
    return base


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DB_DEFAULT)
    p.add_argument("--contracts", type=Path, default=CONTRACTS_DEFAULT)
    p.add_argument("--state", type=Path, default=STATE_DEFAULT)
    p.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    p.add_argument("--mode", choices=["BOILER", "CV"], required=True)
    p.add_argument("--no-write-state", action="store_true")
    args = p.parse_args()

    result = evaluate(args.db, args.contracts, args.state, args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if not args.no_write_state:
        args.state.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

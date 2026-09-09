#!/usr/bin/env python3

"""Daily PV self-consumption validation for the Dynamic Pi Planner.

Read-only analysis only. Uses measured 5-minute P1/PV/Tesla/boiler history from
ems-history.sqlite and derives the amount of otherwise exported PV absorbed by
flexible loads. The residual measured export is the battery-relevant starting
point for later ROI analysis.
"""

import argparse
import json
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
OUTPUT = Path("/home/jeroen/ems/data/pv-capture-validation.json")
HISTORY = Path("/home/jeroen/ems/data/pv-capture-history.json")
TZ = ZoneInfo("Europe/Amsterdam")
MAX_INTERVAL_S = 600

DEVICES = ("grid_p1", "pv_solaredge", "pv_goodwe4200", "pv_goodwe2000", "tesla", "boiler")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="local date YYYY-MM-DD; default yesterday")
    return p.parse_args()


def local_bounds(day):
    start = datetime.combine(day, time.min, TZ)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def load_rows(day):
    start, end = local_bounds(day)
    con = sqlite3.connect(DB)
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
        metric_id = metric[0]
        placeholders = ",".join("?" * len(ids))
        q = f"""
            SELECT m.ts_utc,d.device_key,m.value_real
            FROM measurements m
            JOIN devices d ON d.id=m.device_id
            WHERE m.metric_id=? AND m.ts_utc>=? AND m.ts_utc<?
              AND m.device_id IN ({placeholders})
            ORDER BY m.ts_utc
        """
        params = [metric_id, start.isoformat().replace('+00:00','Z'), end.isoformat().replace('+00:00','Z'), *ids.values()]
        rows = con.execute(q, params).fetchall()
    finally:
        con.close()

    by_ts = {}
    for ts, key, value in rows:
        by_ts.setdefault(ts, {})[key] = float(value)
    out = []
    for ts, values in by_ts.items():
        if all(k in values for k in DEVICES):
            out.append((datetime.fromisoformat(ts.replace('Z', '+00:00')), values))
    out.sort(key=lambda x: x[0])
    return out


def integrate(day, rows):
    totals = {
        "pv_kwh": 0.0,
        "grid_import_kwh": 0.0,
        "grid_export_kwh": 0.0,
        "house_consumption_kwh": 0.0,
        "direct_pv_self_use_kwh": 0.0,
        "flex_load_kwh": 0.0,
        "flex_pv_capture_kwh": 0.0,
        "tesla_pv_capture_kwh": 0.0,
        "boiler_pv_capture_kwh": 0.0,
        "pre_flex_export_counterfactual_kwh": 0.0,
    }
    integrated_s = 0

    for i in range(len(rows) - 1):
        ts, v = rows[i]
        dt = (rows[i + 1][0] - ts).total_seconds()
        if dt <= 0 or dt > MAX_INTERVAL_S:
            continue
        h = dt / 3600.0
        integrated_s += dt

        grid = v["grid_p1"]
        pv = max(0.0, v["pv_solaredge"] + v["pv_goodwe4200"] + v["pv_goodwe2000"])
        tesla = max(0.0, v["tesla"])
        boiler = max(0.0, v["boiler"])
        flex = tesla + boiler
        house = max(0.0, pv + grid)
        base = max(0.0, house - flex)
        export = max(0.0, -grid)
        imp = max(0.0, grid)
        direct_self = max(0.0, min(pv, house))

        # Counterfactual PV surplus before Tesla/boiler. With no battery currently
        # controlling the site, measured export + PV-fed flexible demand is the
        # surplus that would otherwise have left the house.
        pv_available_for_flex = max(0.0, pv - base)
        flex_pv = min(flex, pv_available_for_flex)
        if flex > 0:
            tesla_share = tesla / flex
            boiler_share = boiler / flex
        else:
            tesla_share = boiler_share = 0.0

        totals["pv_kwh"] += pv / 1000 * h
        totals["grid_import_kwh"] += imp / 1000 * h
        totals["grid_export_kwh"] += export / 1000 * h
        totals["house_consumption_kwh"] += house / 1000 * h
        totals["direct_pv_self_use_kwh"] += direct_self / 1000 * h
        totals["flex_load_kwh"] += flex / 1000 * h
        totals["flex_pv_capture_kwh"] += flex_pv / 1000 * h
        totals["tesla_pv_capture_kwh"] += flex_pv * tesla_share / 1000 * h
        totals["boiler_pv_capture_kwh"] += flex_pv * boiler_share / 1000 * h
        totals["pre_flex_export_counterfactual_kwh"] += (export + flex_pv) / 1000 * h

    pv = totals["pv_kwh"]
    preflex = totals["pre_flex_export_counterfactual_kwh"]
    self_rate = totals["direct_pv_self_use_kwh"] / pv if pv > 0 else None
    capture_rate = totals["flex_pv_capture_kwh"] / preflex if preflex > 0 else None

    return {
        "schema": "EMS_PI_PV_CAPTURE_VALIDATION_V0.1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "dateLocal": day.isoformat(),
        "mode": "READ_ONLY_VALIDATION",
        "measurementControlIndependent": True,
        "objective": "MAXIMIZE_PV_SELF_CONSUMPTION",
        "sampleCount": len(rows),
        "integratedMinutes": round(integrated_s / 60, 1),
        "quality": "GOOD" if integrated_s >= 20 * 3600 else "PARTIAL",
        "metrics": {k: round(v, 3) for k, v in totals.items()},
        "kpi": {
            "pvSelfConsumptionRate": None if self_rate is None else round(self_rate, 4),
            "flexiblePvCaptureRate": None if capture_rate is None else round(capture_rate, 4),
            "batteryRelevantResidualExportKWh": round(totals["grid_export_kwh"], 3),
        },
        "method": {
            "gridSign": "positive=import, negative=export",
            "houseLoadW": "max(0, pvW + p1W)",
            "baseLoadW": "max(0, houseLoadW - teslaW - boilerW)",
            "flexPvCaptureW": "min(teslaW+boilerW, max(0,pvW-baseLoadW))",
            "preFlexExportCounterfactual": "measuredExport + flexPvCapture",
            "note": "Residual measured export is the battery ROI starting point; planner remains shadow/read-only.",
        },
    }


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(path)


def update_history(result):
    try:
        history = json.loads(HISTORY.read_text())
    except Exception:
        history = {"schema": "EMS_PI_PV_CAPTURE_HISTORY_V0.1", "days": []}
    days = [d for d in history.get("days", []) if d.get("dateLocal") != result["dateLocal"]]
    days.append(result)
    days.sort(key=lambda d: d.get("dateLocal", ""))
    history["days"] = days[-90:]
    history["generatedAt"] = result["generatedAt"]
    atomic_write(HISTORY, history)


def main():
    args = parse_args()
    day = date.fromisoformat(args.date) if args.date else (datetime.now(TZ).date() - timedelta(days=1))
    rows = load_rows(day)
    if len(rows) < 2:
        raise SystemExit(f"FAIL: insufficient measured samples for {day}")
    result = integrate(day, rows)
    atomic_write(OUTPUT, result)
    update_history(result)
    print("PASS: PV capture validation")
    print("date:", result["dateLocal"])
    print("quality:", result["quality"])
    print("PV self-consumption:", result["kpi"]["pvSelfConsumptionRate"])
    print("flexible PV capture:", result["kpi"]["flexiblePvCaptureRate"])
    print("battery residual export kWh:", result["kpi"]["batteryRelevantResidualExportKWh"])


if __name__ == "__main__":
    main()

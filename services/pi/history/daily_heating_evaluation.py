#!/usr/bin/env python3
"""Daily, observational heating evidence from canonical Pi SQLite (no controls)."""
import argparse
import json
import math
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
LATEST = Path("/home/jeroen/ems/data/heating-daily-evaluation.json")
ARCHIVE = Path("/home/jeroen/ems/data/heating-daily-archive.json")
SCHEMA = "EMS_HEATING_DAILY_EVALUATION_V0.1"
ARCHIVE_SCHEMA = "EMS_HEATING_DAILY_ARCHIVE_V0.1"
ROOMS = (
    "woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer",
    "erker_douwe", "krijn_slaapkamer", "master_bedroom",
)
PERIODS = (("00-09", 0, 9), ("09-12", 9, 12),
           ("12-17", 12, 17), ("17-24", 17, 24))


def utc(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def bounds(day, start_hour=0, end_hour=24):
    start = datetime.combine(day, time.min, TZ) + timedelta(hours=start_hour)
    # Advance calendar date rather than adding 24h to UTC (DST days differ).
    end = (datetime.combine(day + timedelta(days=1), time.min, TZ)
           if end_hour == 24 else datetime.combine(day, time(end_hour), TZ))
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def power_and_rooms(con, start, end):
    """15m power uses complete elapsed-time weighted buckets; room state is evidence only."""
    rows = con.execute("""
        SELECT x.slot_start_utc, d.device_key, m.metric_key,
               x.value_avg, x.energy_wh, x.quality
        FROM measurements_15m x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE julianday(x.slot_start_utc)>=julianday(?)
          AND julianday(x.slot_start_utc)<julianday(?)
          AND (d.device_key='quatt_cic' OR d.device_key LIKE 'honeywell_%')
          AND m.metric_key IN (
            'electrical_power_w','hp1_thermal_power_w','hp2_thermal_power_w',
            'outside_temperature_c','heating_on',
            'room_temperature_c','room_setpoint_c')
    """, (utc(start), utc(end))).fetchall()
    slots = {}
    for slot, device, metric, value, wh, quality in rows:
        slots.setdefault(slot, {}).setdefault(device, {})[metric] = (value, wh, quality)
    expected = int((end-start).total_seconds()/900)
    metrics = {}
    for key in ("electrical_power_w", "hp1_thermal_power_w", "hp2_thermal_power_w"):
        complete = {slot: item["quatt_cic"][key][1] / 1000
                    for slot, item in slots.items()
                    if key in item.get("quatt_cic", {})
                    and item["quatt_cic"][key][2] == "complete"
                    and item["quatt_cic"][key][1] is not None}
        metrics[key] = complete

    paired = set(metrics["electrical_power_w"]) & set(metrics["hp1_thermal_power_w"])
    electric = sum(metrics["electrical_power_w"].values())
    thermal1 = sum(metrics["hp1_thermal_power_w"].values())
    thermal2 = sum(metrics["hp2_thermal_power_w"].values())
    paired_electric = sum(metrics["electrical_power_w"][s] for s in paired)
    paired_heat = sum(metrics["hp1_thermal_power_w"][s] for s in paired)
    heating = [v[0] for item in slots.values()
               if (v := item.get("quatt_cic", {}).get("heating_on"))
               and v[0] is not None and v[2] == "complete"]
    outside = [v[0] for item in slots.values()
               if (v := item.get("quatt_cic", {}).get("outside_temperature_c"))
               and v[0] is not None and v[2] == "complete"]

    rooms = {}
    for room in ROOMS:
        pairs = []
        for slot in sorted(slots):
            item = slots[slot].get("honeywell_" + room, {})
            actual = item.get("room_temperature_c")
            target = item.get("room_setpoint_c")
            if (actual is not None and target is not None
                and actual[0] is not None and target[0] is not None
                and actual[2] == "complete" and target[2] == "complete"):
                pairs.append((slot, float(actual[0]), float(target[0])))
        rooms[room] = {
            "completePairedSlots": len(pairs),
            "coverage": round(len(pairs)/expected, 4) if expected else 0,
            "firstTemperatureC": round(pairs[0][1], 2) if pairs else None,
            "lastTemperatureC": round(pairs[-1][1], 2) if pairs else None,
            "lastSetpointC": round(pairs[-1][2], 2) if pairs else None,
            "belowSetpointBy02CSlots": sum(t-a >= 0.2 for _, a, t in pairs),
            "atOrNearSetpointSlots": sum(abs(t-a) < 0.2 for _, a, t in pairs),
        }

    return {
        "expectedSlots": expected,
        "quattElectricCompleteSlots": len(metrics["electrical_power_w"]),
        "quattHeatHP1CompleteSlots": len(metrics["hp1_thermal_power_w"]),
        "quattElectricKWh": round(electric, 4),
        "quattHeatHP1SensorKWh": round(thermal1, 4),
        "quattHeatHP2SensorKWh": round(thermal2, 4),
        "pairedHP1ElectricSlots": len(paired),
        "pairedHP1HeatToElectricRatio": (
            round(paired_heat/paired_electric, 3) if paired_electric > 0.05
            and len(paired) / expected >= .95 else None),
        "heatingSignalMean": round(sum(heating)/len(heating), 4) if heating else None,
        "outsideTempMeanC": round(sum(outside)/len(outside), 2) if outside else None,
        "rooms": rooms,
    }


def grid_pv(con, start, end):
    """Pair P1 and PV by archived intervals, including explicitly marked held PV."""
    rows = con.execute("""
        SELECT start_ts_utc,end_ts_utc,import_kwh,export_kwh,pv_total_kwh,
               quality,p1_quality,pv_quality
        FROM house_energy_intervals
        WHERE julianday(end_ts_utc)>julianday(?)
          AND julianday(start_ts_utc)<julianday(?)
        ORDER BY julianday(start_ts_utc)
    """, (utc(start), utc(end))).fetchall()
    result = {"pairedHours": 0., "heldPvHours": 0., "estimatedPvHours": 0.,
              "importKWh": 0., "exportKWh": 0., "pvProducedKWh": 0.}
    for a, b, imp, exp, pv, quality, p1, pq in rows:
        a, b = parse_ts(a), parse_ts(b)
        duration = (b-a).total_seconds()
        overlap = max(0., (min(b, end)-max(a, start)).total_seconds())
        if not overlap or duration <= 0:
            continue
        if (quality in ("gap", "discontinuity") or p1 not in ("observed", "held")
            or pq not in ("observed", "held", "estimated")
            or any(v is None or not math.isfinite(v) for v in (imp, exp, pv))):
            continue
        ratio = overlap/duration
        result["pairedHours"] += overlap/3600
        result["importKWh"] += imp*ratio
        result["exportKWh"] += exp*ratio
        result["pvProducedKWh"] += pv*ratio
        if pq == "held":
            result["heldPvHours"] += overlap/3600
        if pq == "estimated":
            result["estimatedPvHours"] += overlap/3600
    expected = (end-start).total_seconds()/3600
    valid = (result["pairedHours"] >= .95*expected and
             result["pvProducedKWh"] + 1e-6 >= result["exportKWh"])
    result["expectedHours"] = expected
    result["pairedCoverage"] = round(min(1., result["pairedHours"]/expected), 4)
    result["balanceQuality"] = ("GOOD" if valid else "INSUFFICIENT_OR_INCONSISTENT")
    result["houseKWh"] = (round(result["importKWh"] + result["pvProducedKWh"] -
                                  result["exportKWh"], 4) if valid else None)
    result["selfConsumedPvKWh"] = (round(result["pvProducedKWh"] -
                                           result["exportKWh"], 4) if valid else None)
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in result.items()}


def observe_cic_gas(con, start, end):
    rows = con.execute("""
        SELECT d.device_key,m.metric_key,x.ts_utc,x.value_real
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE x.quality='observed' AND x.value_real IS NOT NULL
          AND julianday(x.ts_utc)>=julianday(?)
          AND julianday(x.ts_utc)<julianday(?)
          AND ((d.device_key='quatt_cic' AND m.metric_key='supervisory_control_mode')
            OR (d.device_key='grid_p1' AND m.metric_key='gas_meter_m3'))
        ORDER BY julianday(x.ts_utc)
    """, (utc(start), utc(end))).fetchall()
    modes, gas = {}, []
    for device, metric, _, val in rows:
        if metric == "supervisory_control_mode" and 0 <= val <= 65535 and float(val).is_integer():
            modes[str(int(val))] = modes.get(str(int(val)), 0) + 1
        elif metric == "gas_meter_m3" and val >= 0:
            gas.append(float(val))
    monotonic = len(gas) >= 2 and all(b >= a for a, b in zip(gas, gas[1:]))
    return {"cicModeObservedSampleCounts": modes,
            "cicBoilerSelectedSamples": sum(modes.get(str(k), 0) for k in (3, 4)),
            "gasMeterObservedSamples": len(gas),
            "gasObservedSpanDeltaM3": round(gas[-1]-gas[0], 4) if monotonic else None,
            "gasCaveat": "Whole-house counter including domestic hot water; span may not cover full day."}


def analyze(con, day, generated_at=None):
    day_start, day_end = bounds(day)
    parts = {}
    for label, start_hour, end_hour in PERIODS:
        start, end = bounds(day, start_hour, end_hour)
        parts[label] = {"quattAndRooms": power_and_rooms(con, start, end),
                        "energy": grid_pv(con, start, end)}
    q = power_and_rooms(con, day_start, day_end)
    energy = grid_pv(con, day_start, day_end)
    evidence = observe_cic_gas(con, day_start, day_end)
    expected = q["expectedSlots"]
    issues = []
    if q["quattElectricCompleteSlots"] < .95*expected:
        issues.append("QUATT_ELECTRICAL_COVERAGE")
    if q["quattHeatHP1CompleteSlots"] < .95*expected:
        issues.append("QUATT_THERMAL_SENSOR_COVERAGE")
    if energy["balanceQuality"] != "GOOD":
        issues.append("P1_PV_PAIRED_COVERAGE_OR_BALANCE")
    if any(v["coverage"] < .90 for v in q["rooms"].values()):
        issues.append("HONEYWELL_ROOM_COVERAGE")
    status = ("GOOD" if not issues else
              "INSUFFICIENT" if q["quattElectricCompleteSlots"] < .50*expected
              or energy["pairedCoverage"] < .50 else "PARTIAL")
    return {"schema": SCHEMA, "dateLocal": day.isoformat(),
            "generatedAt": utc(generated_at or datetime.now(timezone.utc)),
            "mode": "READ_ONLY", "controlMode": "SHADOW", "controlWrites": False,
            "quality": {"status": status, "issues": issues},
            "quattAndRooms": q, "energy": energy, "cicAndGas": evidence,
            "periods": parts,
            "limitations": [
                "Heating-on is Quatt thermostat signal, not a room-specific demand cause.",
                "Room temperatures and setpoints are 15m averages; thermostat hysteresis is unknown.",
                "Quatt heat is sensor evidence, not independently metered heat per room.",
                "Held PV counter observations and plateau-estimated PV timing remain flagged.",
                "PV export coincident with heat does not prove Quatt PV sourcing or savings.",
                "Gas is whole-house including domestic hot water; CiC mode 3/4 is not flame proof.",
                "No causal savings or validated preheat parameter is inferred.",
            ]}


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".heating-eval-", delete=False) as f:
            tmp = Path(f.name)
            os.chmod(tmp, 0o600)
            json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", nargs="?", help="Completed Amsterdam day (YYYY-MM-DD); default yesterday")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--latest", type=Path, default=LATEST)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--no-write-output", action="store_true")
    parser.add_argument("--archive-only", action="store_true")
    args = parser.parse_args(argv)
    if args.no_write_output and args.archive_only:
        parser.error("--no-write-output and --archive-only conflict")
    target = date.fromisoformat(args.day) if args.day else datetime.now(TZ).date()-timedelta(days=1)
    if target >= datetime.now(TZ).date():
        parser.error("Only completed local days; never archive an unfinished day")
    os.umask(0o077)
    try:
        with closing(sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)) as con:
            con.execute("PRAGMA query_only=ON")
            report = analyze(con, target)
        if not args.no_write_output:
            if args.archive.exists():
                archived = json.loads(args.archive.read_text(encoding="utf-8"))
                if (archived.get("schema") != ARCHIVE_SCHEMA or
                    not isinstance(archived.get("days"), dict)):
                    raise ValueError("Invalid existing heating archive: no overwrite")
                days = archived["days"]
            else:
                days = {}
            days[target.isoformat()] = report
            atomic_json(args.archive, {"schema": ARCHIVE_SCHEMA,
                                       "days": {key: days[key] for key in sorted(days)}})
            if not args.archive_only:
                atomic_json(args.latest, report)
        print(json.dumps({"date": str(target), "status": report["quality"]["status"],
                          "issues": report["quality"]["issues"],
                          "quattKWh": report["quattAndRooms"]["quattElectricKWh"],
                          "pairedCoverage": report["energy"]["pairedCoverage"],
                          "readOnly": True, "controlWrites": False}))
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        print(f"ERROR: daily heating evaluation: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

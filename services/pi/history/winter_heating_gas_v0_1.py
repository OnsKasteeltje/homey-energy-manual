#!/usr/bin/env python3
"""One-off, read-only winter evidence from Homey Insights; no actuator writes."""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
DEFAULT_FILE = Path("/home/jeroen/ems/data/analysis/winter-heating-gas-v0.1.json")
HOMEY_CLI = Path.home() / "ems-homey-adapter/node_modules/.bin/homey"
HOMEY_PROJECT = HOMEY_CLI.parents[2]
NODE24_BIN = "/opt/node-v24.20.0/bin"
QUATT = "1e5dcde5-c1cf-4c32-9141-33e00ce36de9"
P1 = "7a696d77-15fb-4b68-9bce-f1e39bff5045"
ROOMS = {
    "woonkamer": "6a79bb86-8c02-43db-be22-6f51e01efc6d",
    "eetkamer": "dd7ef4a3-ed9f-4e4d-92bb-090502068421",
    "keuken": "b7aec05b-953f-41e1-a7b4-ad09c9bf911e",
    "serre": "13625cb2-8fb5-4466-a21f-7addd8d72a88",
    "douwe_slaapkamer": "f74252a1-2879-4967-ba2d-41f56364e39b",
    "erker_douwe": "f9db36cd-8c0f-4beb-aa28-0127597652cf",
}


def sources(rooms):
    result = {
        "gas_m3": (f"homey:device:{P1}", "meter_gas"),
        "outside_c": ("homey:manager:weather", "temperature"),
        "quatt_hp1_w": (f"homey:device:{QUATT}", "measure_heatpump_thermal_power.heatpump1"),
        "quatt_hp2_w": (f"homey:device:{QUATT}", "measure_heatpump_thermal_power.heatpump2"),
    }
    for room in rooms:
        if room not in ROOMS:
            raise ValueError(f"Unknown room: {room}")
        result[f"{room}_target_c"] = (f"homey:device:{ROOMS[room]}", "target_temperature")
        result[f"{room}_actual_c"] = (f"homey:device:{ROOMS[room]}", "measure_temperature")
    return result


def read_insights(uri, capability, resolution):
    command = [str(HOMEY_CLI), "api", "insights", "get-log-entries",
               "--uri", uri, "--id", f"{uri}:{capability}",
               "--resolution", resolution, "--json"]
    env = os.environ.copy()
    env["PATH"] = f"{NODE24_BIN}:{env.get('PATH', '')}"
    result = subprocess.run(command, cwd=HOMEY_PROJECT, env=env,
                            text=True, capture_output=True, timeout=90, check=False)
    if result.returncode:
        err = (result.stderr or result.stdout).strip()
        if "429" in err or "Too many requests" in err:
            raise RuntimeError("Homey 429: stop immediately; no automatic retry")
        raise RuntimeError(f"Homey Insights read failed: {err[:250]}")
    payload = json.loads(result.stdout)
    entries = (payload.get("values", payload.get("entries"))
               if isinstance(payload, dict) else payload)
    if not isinstance(entries, list):
        raise ValueError("Unexpected Homey Insights response")
    good = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("t"):
            continue
        v = entry.get("v")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue  # Homey may return null buckets for historical periods
        good.append({"t": entry["t"], "v": float(v)})
    return good


def save_private(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        os.chmod(temp, 0o600)
        json.dump(data, f, separators=(",", ":"))
        f.write("\n")
    os.replace(temp, path)


def collect(path, years, rooms):
    if datetime.now(TZ).year != 2026:
        raise RuntimeError("Homey lastYear/thisYear resolution mapping is pinned to calendar year 2026")
    if not HOMEY_CLI.is_file():
        raise RuntimeError(f"Existing Homey CLI not found: {HOMEY_CLI}")
    evidence = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
                else {"schema": "EMS_WINTER_HEATING_GAS_EVIDENCE_V0.1", "series": {}})
    if evidence.get("schema") != "EMS_WINTER_HEATING_GAS_EVIDENCE_V0.1":
        raise ValueError("Wrong input schema")
    jobs = sources(rooms)
    for year in years:
        if year not in (2025, 2026):
            raise ValueError("Only winter years 2025 and 2026 are supported")
        resolution = "lastYear" if year == 2025 else "thisYear"
        for name, (uri, capability) in jobs.items():
            if str(year) in evidence["series"].get(name, {}):
                print(f"SKIP {name} {year}: already exported")
                continue
            print(f"FETCH {name} {year}: {resolution}", flush=True)
            # A single bounded Insights read. 429/error => stop (no retries).
            points = read_insights(uri, capability, resolution)
            evidence["series"].setdefault(name, {})[str(year)] = points
            save_private(path, evidence)  # resumable after partial successful export
            print(f"SAVED {name} {year}: {len(points)} valid samples", flush=True)
            time.sleep(8)  # yield to production Homey traffic
    print(f"Export complete: {path}")


def utc_time(raw):
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def samples(evidence, key):
    vals = {}
    for year_series in evidence.get("series", {}).get(key, {}).values():
        for p in year_series:
            v = p.get("v")
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                vals[utc_time(p["t"])] = float(v)
    return sorted(vals.items())


def evaluate(evidence, start="2025-11-01", end="2026-04-01"):
    """Six-hour observational comparison. Never attributes central gas to a room."""
    if evidence.get("schema") != "EMS_WINTER_HEATING_GAS_EVIDENCE_V0.1":
        raise ValueError("Wrong input schema")
    start_day = datetime.fromisoformat(start).date()
    end_day = datetime.fromisoformat(end).date()
    if start_day >= end_day:
        raise ValueError("Invalid date range")
    gas = samples(evidence, "gas_m3")
    by_day = defaultdict(lambda: {"gas_m3": 0.0, "gas_intervals": 0,
                                  "weather": [], "hp1": [], "hp2": []})
    rejected = 0
    for (t0, v0), (t1, v1) in zip(gas, gas[1:]):
        delta = v1 - v0
        # Homey historical counter readings are six-hour bucket aggregates.
        # Missing buckets/counter resets cannot be distributed over adjacent days.
        if not (timedelta(hours=5, minutes=55) <= t1 - t0 <= timedelta(hours=6, minutes=5)) or delta < 0:
            rejected += 1
            continue
        date = t1.astimezone(TZ).date()
        if start_day <= date < end_day:
            by_day[date]["gas_m3"] += delta
            by_day[date]["gas_intervals"] += 1
    for field, key in (("weather", "outside_c"), ("hp1", "quatt_hp1_w"),
                       ("hp2", "quatt_hp2_w")):
        for timestamp, value in samples(evidence, key):
            date = timestamp.astimezone(TZ).date()
            if start_day <= date < end_day:
                by_day[date][field].append(value)

    days = []
    date = start_day
    while date < end_day:
        d = by_day[date]
        # Counter buckets are approximate, especially around DST.
        complete = d["gas_intervals"] == 4 and len(d["weather"]) == 4
        outside = sum(d["weather"]) / len(d["weather"]) if d["weather"] else None
        hdd18 = max(0.0, 18 - outside) if complete else None
        row = {"date": date.isoformat(), "month": date.strftime("%Y-%m"),
               "quality": "approx_6h" if complete else "incomplete",
               "gas_m3": round(d["gas_m3"], 3) if complete else None,
               "outdoor_c": round(outside, 2) if outside is not None else None,
               "hdd18": round(hdd18, 2) if hdd18 is not None else None,
               "hp1_avg_w": round(sum(d["hp1"]) / len(d["hp1"])) if len(d["hp1"]) == 4 else None,
               "hp2_avg_w": round(sum(d["hp2"]) / len(d["hp2"])) if len(d["hp2"]) == 4 else None}
        days.append(row)
        date += timedelta(days=1)

    month_rows = []
    for month in sorted({d["month"] for d in days}):
        items = [d for d in days if d["month"] == month]
        complete = [d for d in items if d["quality"] == "approx_6h"]
        month_rows.append({"month": month, "observed_days": len(complete),
                           "total_days": len(items),
                           "gas_m3_on_observed_days": round(sum(d["gas_m3"] for d in complete), 2),
                           "hdd18_on_observed_days": round(sum(d["hdd18"] for d in complete), 1)})

    room_rows = []
    for name in ROOMS:
        target = dict(samples(evidence, f"{name}_target_c"))
        actual = dict(samples(evidence, f"{name}_actual_c"))
        pairs = [(target[t], actual[t]) for t in target.keys() & actual.keys()
                 if start_day <= t.astimezone(TZ).date() < end_day]
        room_rows.append({"room": name, "matched_6h_buckets": len(pairs),
                          "pct_target_above_actual_by_05c":
                          round(100 * sum(s > a + 0.5 for s, a in pairs) / len(pairs), 1)
                          if pairs else None})
    return {"schema": "EMS_WINTER_HEATING_GAS_ANALYSIS_V0.1",
            "method": "read-only; approx 6h counters; combined gas includes DHW; no causality",
            "rejected_gas_intervals": rejected,
            "months": month_rows, "rooms": room_rows, "days": days}


def report(analysis):
    lines = ["# Winterverwarming — eerste nulmeting (READ_ONLY)", "",
             "P1-gas is **totaal gas inclusief tapwater**. Gas per kamer of cv-branduren",
             "kunnen niet uit deze bron worden afgeleid. Homey 6-uurswaarden zijn",
             "geaggregeerde snapshots; dagtotalen zijn benaderingen, geen factuurstanden.", "",
             "## Historische dekking", "",
             "| Maand | Dagen met volledige gas+weerreeks | Gas op die dagen | Graaddagen (18 °C) |",
             "|---|---:|---:|---:|"]
    for m in analysis["months"]:
        lines.append(f'| {m["month"]} | {m["observed_days"]}/{m["total_days"]} | '
                     f'{m["gas_m3_on_observed_days"]:.2f} m³ | {m["hdd18_on_observed_days"]:.1f} |')
    lines.extend(["", "## Honeywell indicatie", "",
                  "Onderstaand percentage toont in hoeveel *zesuursgemiddelden* het",
                  "setpoint > actuele kamertemperatuur + 0,5 °C was. Geen bewezen branderactiviteit.", "",
                  "| Ruimte | Gekoppelde meetvakken | Onder setpoint >0,5 °C |",
                  "|---|---:|---:|"])
    for r in analysis["rooms"]:
        share = (str(r["pct_target_above_actual_by_05c"]) + "%"
                 if r["pct_target_above_actual_by_05c"] is not None else "onbekend")
        lines.append(f'| {r["room"]} | {r["matched_6h_buckets"]} | {share} |')
    lines.extend(["", f'Afgewezen/gemiste gasintervallen: {analysis["rejected_gas_intervals"]}.',
                  "", "**Vervolg:** eerst cv/WW-attributie en betere temporele resolutie;",
                  "geen automatische setpointaanpassing of besparingsclaim."])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--collect", action="store_true", help="one-off Insights reads, no timer")
    parser.add_argument("--years", default="2026", help="2026 or 2025,2026")
    parser.add_argument("--rooms", default="woonkamer,eetkamer")
    parser.add_argument("--start", default="2025-11-01")
    parser.add_argument("--end", default="2026-04-01")
    args = parser.parse_args()
    os.umask(0o077)
    rooms = [r.strip() for r in args.rooms.split(",") if r.strip()]
    try:
        if args.collect:
            collect(args.file, [int(y) for y in args.years.split(",")], rooms)
        if not args.file.is_file():
            parser.error("private historical evidence file missing; run --collect explicitly")
        evidence = json.loads(args.file.read_text(encoding="utf-8"))
        print(report(evaluate(evidence, args.start, args.end)))
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

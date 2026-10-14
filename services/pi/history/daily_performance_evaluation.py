#!/usr/bin/env python3
"""Compact deterministic daily EMS evaluation; no AI call or device writes."""

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
OUTPUT = Path("/home/jeroen/ems/data/daily-performance-evaluation.json")
SCHEMA = "EMS_PI_DAILY_PERFORMANCE_EVALUATION_V0.1"


def yesterday():
    return datetime.now(TZ).date() - timedelta(days=1)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _run(command):
    p = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    if p.returncode:
        raise RuntimeError(f"{command[0]} exited {p.returncode}: {p.stderr[-250:]}")
    result = json.loads(p.stdout)
    if not isinstance(result, dict):
        raise ValueError("command returned non-object JSON")
    return result


def build_digest(day, performance, replay=None, now=None):
    if performance.get("schema") != "EMS_PI_DAY_PERFORMANCE_V0.1":
        raise ValueError("performance schema invalid")
    if performance.get("dateLocal") != day.isoformat():
        raise ValueError("performance date mismatch")

    account = performance.get("energyAccounting") or {}
    quality = performance.get("quality") or {}
    power_quality = performance.get("powerSampleQuality") or {}
    source_quality = account.get("sourceQualityCounts") or {}
    p1_coverage = account.get("p1Coverage")
    paired_coverage = account.get("pairedCoverage")
    meter_ok = (
        finite_number(p1_coverage) and p1_coverage >= 0.95
        and finite_number(account.get("importKWh"))
        and finite_number(account.get("exportKWh"))
    )
    pv_ok = (
        meter_ok and account.get("available") is True
        and finite_number(paired_coverage) and paired_coverage >= 0.95
        and finite_number(account.get("pvKWh"))
        and finite_number(account.get("pvSelfConsumedKWh"))
        and finite_number(account.get("pvSelfConsumptionRate"))
    )

    start = datetime.combine(day, datetime.min.time(), TZ)
    day_hours = ((start + timedelta(days=1)).astimezone(timezone.utc)
                 - start.astimezone(timezone.utc)).total_seconds() / 3600
    valid_replay = (
        isinstance(replay, dict)
        and replay.get("schema") == "EMS_PI_CONSTRAINED_REPLAY_V0.1.1"
        and replay.get("scope") == "EV_EXPORT_ONLY"
        and replay.get("readOnly") is True
        and replay.get("controlWrites") is False
    )
    replay_totals = replay.get("totals") or {} if valid_replay else {}
    replay_coverage = replay.get("coverage") or {} if valid_replay else {}
    integrated_hours = replay_coverage.get("integratedHours")
    replay_complete = (
        valid_replay and finite_number(integrated_hours)
        and integrated_hours >= day_hours * 0.90
    )

    issues = []
    if quality.get("status") != "GOOD":
        issues.append("INCOMPLETE_DAY_POWER_EVIDENCE")
    if not meter_ok:
        issues.append("P1_COUNTER_ENERGY_UNAVAILABLE")
    if not pv_ok:
        issues.append("PV_SELF_CONSUMPTION_UNAVAILABLE")
    if not valid_replay:
        issues.append("EV_REPLAY_UNAVAILABLE")
    elif not replay_complete:
        issues.append("EV_REPLAY_LIMITED_COVERAGE")
    if (power_quality.get("impossibleExportIntervals") or 0) > 0:
        issues.append("REVIEW_PV_P1_SAMPLE_ALIGNMENT")

    feasible = replay_totals.get("additionalFeasibleCaptureKWh")
    if not (replay_complete and finite_number(feasible) and feasible >= 0):
        feasible = None
    classes = replay_totals.get("byClassificationKWh") or {}
    estimated_classes = {
        key: value for key, value in classes.items()
        if isinstance(key, str) and finite_number(value) and value >= 0
    } if replay_complete and isinstance(classes, dict) else {}

    status = (
        "INSUFFICIENT_EVIDENCE" if not meter_ok or not pv_ok or quality.get("status") != "GOOD"
        else "PARTIAL" if not replay_complete
        else "READY"
    )

    lines = []
    if meter_ok:
        lines.append(
            f"P1 gemeten: {account['importKWh']:.3f} kWh import, "
            f"{account['exportKWh']:.3f} kWh export."
        )
    else:
        lines.append("P1 tellerenergie onvoldoende onderbouwd; geen dag-kWh gerapporteerd.")
    if pv_ok:
        lines.append(
            f"PV: {account['pvKWh']:.3f} kWh opgewekt, "
            f"{account['pvSelfConsumptionRate'] * 100:.1f}% zelfverbruik "
            "(afgeleid uit energietellers)."
        )
    else:
        lines.append("PV-zelfverbruik onvoldoende onderbouwd.")
    if feasible is not None:
        lines.append(
            f"EV-only replay: circa {feasible:.4f} kWh extra opname haalbaar "
            "volgens vermogenssteekproeven; geen exacte kWh of bewezen besparing."
        )
    else:
        lines.append("EV-only replay niet voldoende onderbouwd voor een dagtotaal.")
    if "REVIEW_PV_P1_SAMPLE_ALIGNMENT" in issues:
        lines.append("PV/P1 momentopnamen vragen tijdaligneringscontrole; geen bewezen EMS-fout.")

    return {
        "schema": SCHEMA,
        "dateLocal": day.isoformat(),
        "generatedAt": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "readOnly": True,
        "controlWrites": False,
        "accounting": {
            "authority": "P1_CUMULATIVE_ENERGY_COUNTERS",
            "gridImportKWh": round(account["importKWh"], 3) if meter_ok else None,
            "gridExportKWh": round(account["exportKWh"], 3) if meter_ok else None,
            "pvProducedKWh": round(account["pvKWh"], 3) if pv_ok else None,
            "pvSelfConsumedKWh": round(account["pvSelfConsumedKWh"], 3) if pv_ok else None,
            "pvSelfConsumptionRate": account["pvSelfConsumptionRate"] if pv_ok else None,
            "p1Coverage": p1_coverage,
            "pairedCoverage": paired_coverage,
            "pvIntervalQualityCounts": source_quality.get("pv") or {},
        },
        "evReplay": {
            "available": replay_complete,
            "scope": "EV_EXPORT_ONLY",
            "energyAuthority": "SAMPLED_POWER_ESTIMATE_NOT_P1_COUNTER",
            "integratedHours": integrated_hours if finite_number(integrated_hours) else None,
            "estimatedAdditionalFeasibleCaptureKWh": feasible,
            "estimatedByClassificationKWh": estimated_classes,
        },
        "quality": {
            "performance": quality.get("status"),
            "sampleAlignmentFlaggedIntervals": power_quality.get("impossibleExportIntervals") or 0,
            "issues": issues,
        },
        "lines": lines,
    }


def _write_atomic(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".daily-performance-", delete=False) as file:
            tmp_path = Path(file.name)
            json.dump(result, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", nargs="?", default=None, help="Amsterdam date YYYY-MM-DD; default yesterday")
    parser.add_argument("--no-write-output", action="store_true")
    args = parser.parse_args(argv)
    day = date.fromisoformat(args.day) if args.day else yesterday()
    if day >= datetime.now(TZ).date():
        parser.error("only completed local calendar days are supported")

    try:
        performance = _run(["/usr/local/bin/ems-performance", day.isoformat()])
        try:
            replay = _run([
                "/usr/local/bin/ems-constrained-replay",
                day.isoformat(), "--no-write-output"
            ])
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            replay = None
        result = build_digest(day, performance, replay)
        if not args.no_write_output:
            _write_atomic(OUTPUT, result)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"ERROR: daily EMS evaluation: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

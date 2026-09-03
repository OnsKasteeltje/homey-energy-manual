#!/usr/bin/env python3
"""Recover missed day-rollovers from committed energy-day-v2 snapshots.

The Homey day-series publisher continuously commits ``energy-day-v2.json``.  If
its separate midnight archive flow misses a run, those measurements still exist
in Git history.  This build-time repair uses that durable source to reconstruct
missing completed days without treating an archive gap as a zero-energy day.

The script is intentionally idempotent. Existing archived dates always win; only
missing completed dates are backfilled. Nothing is committed by this script: it
repairs the Pages build workspace, so a later healthy Homey archive remains the
canonical producer.
"""
from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
DAY_PATH = "docs/data/energy-day-v2.json"
ROLLING_PATH = DATA / "energy-day-series-7d.json"
HISTORY_PATH = DATA / "energy-daily-history.json"
DEFAULT_LOOKBACK_DAYS = 7


def local_date_from_iso(value: str) -> date:
    return date.fromisoformat(value)


def integrate(samples: list[dict], getter) -> float:
    """Trapezoidal integration with the same 10-minute gap cap as the UI."""
    energy_kwh = 0.0
    for left, right in zip(samples, samples[1:]):
        try:
            a = datetime.fromisoformat(str(left["ts"]).replace("Z", "+00:00"))
            b = datetime.fromisoformat(str(right["ts"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        hours = min(600.0, (b - a).total_seconds()) / 3600.0
        if hours <= 0:
            continue
        energy_kwh += (getter(left) + getter(right)) / 2.0 * hours / 1000.0
    return max(0.0, energy_kwh)


def normalized_power(sample: dict) -> dict[str, float]:
    pv = max(
        0.0,
        float(sample.get("solarEdgeW") or 0)
        + float(sample.get("goodWe4200W") or 0)
        + float(sample.get("goodWe2000W") or 0),
    )
    p1 = float(sample.get("p1W") or 0)
    return {
        "import": max(0.0, p1),
        "export": max(0.0, -p1),
        "boiler": max(0.0, float(sample.get("boilerW") or 0)),
        "tesla": max(0.0, float(sample.get("teslaW") or 0)),
        "pv": pv,
    }


def summarize_day(day_doc: dict, commit_sha: str) -> dict:
    samples = list(day_doc.get("samples") or [])
    powers = [normalized_power(sample) for sample in samples]
    paired = list(zip(samples, powers))

    def metric(name: str) -> float:
        by_id = {id(sample): power for sample, power in paired}
        return round(integrate(samples, lambda sample: by_id[id(sample)][name]), 3)

    first_ts = samples[0].get("ts") if samples else None
    last_ts = samples[-1].get("ts") if samples else None
    coverage_minutes = 0.0
    if first_ts and last_ts:
        try:
            first = datetime.fromisoformat(str(first_ts).replace("Z", "+00:00"))
            last = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            coverage_minutes = max(0.0, (last - first).total_seconds() / 60.0)
        except ValueError:
            pass

    sample_count = len(samples)
    # At a 5-minute cadence, >= 276 points and >= 22.5h span is a strong
    # completed-day signal. Anything shorter remains explicitly PARTIAL.
    complete = sample_count >= 276 and coverage_minutes >= 1350
    return {
        "date": day_doc.get("date_local"),
        "source": f"recovered from energy-day-v2 Git snapshot {commit_sha[:12]}",
        "quality": "RECOVERED_COMPLETE" if complete else "RECOVERED_PARTIAL",
        "sample_count": sample_count,
        "coverage_minutes": round(coverage_minutes, 1),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "p1_import_kWh_est": metric("import") if samples else 0.0,
        "p1_export_kWh_est": metric("export") if samples else 0.0,
        "boiler_kWh_est": metric("boiler") if samples else 0.0,
        "tesla_kWh_est": metric("tesla") if samples else 0.0,
        "pv_available_kWh_est": metric("pv") if samples else 0.0,
        "recovery_status": "COMPLETE" if complete else "PARTIAL",
    }


def git_commits_for_day_file() -> Iterable[str]:
    result = subprocess.run(
        ["git", "log", "--format=%H", "--", DAY_PATH],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return (line.strip() for line in result.stdout.splitlines() if line.strip())


def day_at_commit(commit_sha: str) -> dict | None:
    result = subprocess.run(
        ["git", "show", f"{commit_sha}:{DAY_PATH}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def best_snapshots(target_dates: set[str]) -> dict[str, tuple[str, dict]]:
    """Return the largest committed snapshot for every requested local date."""
    best: dict[str, tuple[str, dict]] = {}
    if not target_dates:
        return best
    for commit_sha in git_commits_for_day_file():
        doc = day_at_commit(commit_sha)
        if not doc:
            continue
        day_key = doc.get("date_local")
        if day_key not in target_dates:
            continue
        count = int(doc.get("sample_count") or len(doc.get("samples") or []))
        existing = best.get(day_key)
        existing_count = -1
        if existing:
            old_doc = existing[1]
            existing_count = int(old_doc.get("sample_count") or len(old_doc.get("samples") or []))
        if count > existing_count:
            best[day_key] = (commit_sha, doc)
        # A normal 5-minute day contains about 288 points. Once all targets have
        # a near-full snapshot, older commits cannot materially improve recovery.
        if len(best) == len(target_dates) and all(
            int(doc_.get("sample_count") or len(doc_.get("samples") or [])) >= 283
            for _, doc_ in best.values()
        ):
            break
    return best


def repair_documents(rolling: dict, history: dict, snapshots: dict[str, tuple[str, dict]]) -> tuple[dict, dict, list[str]]:
    rolling_days = [d for d in (rolling.get("days") or []) if isinstance(d, dict)]
    history_days = [d for d in (history.get("days") or []) if isinstance(d, dict)]
    rolling_dates = {d.get("date_local") for d in rolling_days}
    history_dates = {d.get("date") for d in history_days}
    recovered: list[str] = []

    for day_key in sorted(snapshots):
        commit_sha, day_doc = snapshots[day_key]
        samples = day_doc.get("samples") or []
        if not samples:
            continue
        if day_key not in rolling_dates:
            recovered_day = dict(day_doc)
            recovered_day["recovery"] = {
                "status": summarize_day(day_doc, commit_sha)["recovery_status"],
                "source": "GIT_SNAPSHOT_FALLBACK",
                "commit": commit_sha[:12],
            }
            rolling_days.append(recovered_day)
            rolling_dates.add(day_key)
            recovered.append(day_key)
        if day_key not in history_dates:
            history_days.append(summarize_day(day_doc, commit_sha))
            history_dates.add(day_key)

    rolling_days.sort(key=lambda d: str(d.get("date_local") or ""))
    # The day picker only needs recent completed days; keep bounded growth while
    # preserving any producer-defined retention if it is larger.
    keep = max(DEFAULT_LOOKBACK_DAYS, int(rolling.get("retention_completed_days") or 0) + 1)
    rolling["days"] = rolling_days[-keep:]
    history_days.sort(key=lambda d: str(d.get("date") or ""))
    retention = int(history.get("retention_days") or 90)
    history["days"] = history_days[-retention:]
    return rolling, history, recovered


def main() -> int:
    rolling = json.loads(ROLLING_PATH.read_text(encoding="utf-8"))
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    current = json.loads((DATA / "energy-day-v2.json").read_text(encoding="utf-8"))
    current_date = local_date_from_iso(current["date_local"])

    existing = {d.get("date_local") for d in (rolling.get("days") or []) if isinstance(d, dict)}
    existing |= {d.get("date") for d in (history.get("days") or []) if isinstance(d, dict)}
    target_dates = {
        (current_date - timedelta(days=offset)).isoformat()
        for offset in range(1, DEFAULT_LOOKBACK_DAYS + 1)
        if (current_date - timedelta(days=offset)).isoformat() not in existing
    }
    if not target_dates:
        print("energy history recovery: no archive gaps in lookback window")
        return 0

    snapshots = best_snapshots(target_dates)
    rolling, history, recovered = repair_documents(rolling, history, snapshots)
    if recovered or any(day in snapshots for day in target_dates):
        ROLLING_PATH.write_text(json.dumps(rolling, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    unresolved = sorted(target_dates - snapshots.keys())
    print(f"energy history recovery: recovered={recovered or []}; unresolved={unresolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

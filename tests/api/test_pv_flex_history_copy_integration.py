#!/usr/bin/env python3
"""Integration check of PV & Flex against a disposable SQLite history copy."""
import importlib.util
import sqlite3
import sys
from pathlib import Path

DB = Path("/tmp/ems-pv-validation.sqlite")
API = Path("services/pi/api/web-data/server.py")
DAY = "2026-10-08"

def main():
    if not DB.is_file():
        raise SystemExit(f"FAIL: missing database copy: {DB}")
    spec = importlib.util.spec_from_file_location("ems_web_data_validation", API)
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    server.HISTORY_DB = str(DB)
    # No external heating files are needed for this isolated read-only check.
    server.heating_preheat_progression_resource = lambda: {"rooms": [], "generatedAt": None}
    result = server.pv_flex_analysis_resource(DAY)
    slots = result["series"]
    assert len(slots) == 96, f"unexpected slot count: {len(slots)}"

    # Mirror the API's fractional overlap at Amsterdam calendar boundaries.
    from datetime import datetime, timezone
    period_start = datetime.fromisoformat(result["period"]["start"]).astimezone(timezone.utc)
    period_end = datetime.fromisoformat(result["period"]["end"]).astimezone(timezone.utc)
    expected = [0.0, 0.0]
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
        rows = con.execute("""
            SELECT start_ts_utc,end_ts_utc,import_kwh,export_kwh
            FROM house_energy_intervals
            WHERE end_ts_utc > ? AND start_ts_utc < ?
              AND p1_quality IN ('observed','held')
        """, (period_start.isoformat().replace("+00:00", "Z"),
              period_end.isoformat().replace("+00:00", "Z"))).fetchall()
    for start, end, imp, exp in rows:
        a = datetime.fromisoformat(start.replace("Z","+00:00"))
        b = datetime.fromisoformat(end.replace("Z","+00:00"))
        fraction = max(0.0, (min(b, period_end)-max(a, period_start)).total_seconds()) / max(1.0,(b-a).total_seconds())
        expected[0] += (imp or 0.0) * fraction
        expected[1] += (exp or 0.0) * fraction
    summary = result["summary"]
    for field, value in zip(("importKWh", "exportKWh"), expected):
        actual = summary[field]
        assert abs(actual - value) <= 0.002, (
            f"{field}: API={actual}, SQLite={value}")
        print(f"PASS {field}: API={actual:.3f} SQLite={value:.3f}")

    assert summary["pvSelfConsumedKWh"] is None, "partial day must not report self-use total"
    assert summary["pvSelfConsumptionStatus"] == "INCOMPLETE_COVERAGE"
    print("PASS incomplete PV self-use: null with explicit status")

    quality = result["quality"]
    assert quality["p1Coverage"] >= quality["pvCoverage"], quality
    assert 0 <= quality["actualCoverage"] <= quality["pvCoverage"] <= 1
    print(f"PASS coverage: P1={quality['p1Coverage']:.3f} PV={quality['pvCoverage']:.3f} joint={quality['actualCoverage']:.3f}")

    # 02:00-09:15 local: import remains visible when PV cannot be assigned.
    overnight = [x for x in slots if
                 x["start"].startswith("2026-10-08T") and
                 "02:00:00" <= x["start"][11:19] < "09:15:00"]
    assert overnight, "overnight slots missing"
    assert any(x["actual"]["p1Coverage"] > 0 and
               x["actual"]["pvCoverage"] == 0 and
               x["actual"]["importKWh"] > 0 for x in overnight), (
                   "PV gap still hides valid P1 import")
    print("PASS overnight: P1 visible despite PV gap")
    print("PASS: isolated PV & Flex integration; no runtime changes")

if __name__ == "__main__":
    main()

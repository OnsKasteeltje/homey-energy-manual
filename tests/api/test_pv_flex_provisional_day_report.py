#!/usr/bin/env python3
"""In-progress EMS day subtotal: closed slots only, strict paired coverage, no writes."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

source = Path("services/pi/api/web-data/server.py")
spec = importlib.util.spec_from_file_location("ems_provisional_day", source)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
tz = ZoneInfo("Europe/Amsterdam")
day = "2026-10-14"
base = datetime(2026, 10, 14, 0, 0, tzinfo=tz)
now = datetime(2026, 10, 14, 1, 6, tzinfo=tz).astimezone(timezone.utc)

def slots(coverage=1.0, bad_slot=None, pv=1.25, export=0.25):
    rows, paired = [], {}
    for i in range(5):  # Fifth interval is open at 01:06.
        start = (base + timedelta(minutes=15*i)).astimezone(timezone.utc)
        end = start + timedelta(minutes=15)
        c = coverage if i == bad_slot else 1.0
        rows.append({
            "start": start.astimezone(tz).isoformat(),
            "end": end.astimezone(tz).isoformat(),
            "actual": {"pvKWh": pv, "importKWh": 0.1, "exportKWh": export,
                       "p1Coverage": c, "pvCoverage": c}
        })
        paired[api._utc_text(start)] = 900*c
    return rows, paired

rows, paired = slots()
result = api.provisional_daily_report_resource(day, rows, paired, now)
assert result["schema"] == "EMS_WEB_DAILY_PERFORMANCE_V1"
assert result["readOnly"] is True and result["controlWrites"] is False
assert result["status"] == "PROVISIONAL"
assert result["throughLocal"] == "2026-10-14T01:00:00+02:00"
assert result["accounting"]["pvProducedKWh"] == 5.0
assert result["accounting"]["gridImportKWh"] == .4
assert result["accounting"]["gridExportKWh"] == 1.0
assert result["accounting"]["pvSelfConsumedKWh"] == 4.0
assert result["accounting"]["pvSelfConsumptionRate"] == .8

# An older/finished day must never masquerade as a live provisional report.
assert api.provisional_daily_report_resource("2026-10-13", rows, paired, now) is None

# Missing one interior quarter fails closed (75% coverage from midnight).
rows, paired = slots(bad_slot=1, coverage=0)
result = api.provisional_daily_report_resource(day, rows, paired, now)
assert result["status"] == "INSUFFICIENT_EVIDENCE"
assert result["accounting"]["pvProducedKWh"] is None
assert result["accounting"]["gridImportKWh"] is None
assert result["quality"]["pairedCoverage"] == .75

# Only a single finished quarter is not sufficient to claim a day subtotal.
early = datetime(2026, 10, 14, 0, 18, tzinfo=tz).astimezone(timezone.utc)
rows, paired = slots()
result = api.provisional_daily_report_resource(day, rows, paired, early)
assert result["status"] == "INSUFFICIENT_EVIDENCE"
assert result["throughLocal"] == "2026-10-14T00:15:00+02:00"

# Never invent self-use when P1 export is greater than total PV production.
rows, paired = slots(pv=.1, export=.2)
result = api.provisional_daily_report_resource(day, rows, paired, now)
assert result["status"] == "PROVISIONAL"
assert result["accounting"]["pvProducedKWh"] == .4
assert result["accounting"]["pvSelfConsumedKWh"] is None
assert result["accounting"]["pvSelfConsumptionRate"] is None

# No PV production => no fabricated percentage, but proven P1 energy remains visible.
rows, paired = slots(pv=0, export=0)
result = api.provisional_daily_report_resource(day, rows, paired, now)
assert result["status"] == "PROVISIONAL"
assert result["accounting"]["gridImportKWh"] == .4
assert result["accounting"]["pvSelfConsumptionRate"] is None

print("PASS: provisional daily P1/PV subtotal uses closed intervals and paired coverage")

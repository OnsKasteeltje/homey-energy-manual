#!/usr/bin/env python3
"""Single read-only financial Evaluatie API acceptance test, no network."""
import importlib.util
import json
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
api_path = ROOT / "services/pi/api/web-data/server.py"
spec = importlib.util.spec_from_file_location("ems_web_financial_test", api_path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
api.FINANCIAL_PERFORMANCE_MODULE = str(ROOT / "services/pi/history/ems_performance.py")
assert '["web", "analysis", "financial", "day"]' in api_path.read_text()

with tempfile.TemporaryDirectory() as temp:
    db = Path(temp) / "ems-history.sqlite"
    api.HISTORY_DB = str(db)
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE house_energy_intervals(
            start_ts_utc TEXT, end_ts_utc TEXT, import_kwh REAL,
            export_kwh REAL, pv_total_kwh REAL, quality TEXT,
            p1_quality TEXT, pv_quality TEXT
        );
    """)
    target = date(2027, 2, 1)
    start = datetime.combine(target, time.min, ZoneInfo("Europe/Amsterdam"))
    for i in range(288):
        t1 = (start + timedelta(minutes=5*i)).astimezone(timezone.utc)
        t2 = (start + timedelta(minutes=5*(i+1))).astimezone(timezone.utc)
        con.execute("INSERT INTO house_energy_intervals VALUES (?,?,?,?,?,?,?,?)", (
            t1.isoformat().replace("+00:00", "Z"),
            t2.isoformat().replace("+00:00", "Z"),
            10/288, 4/288, None, "partial", "observed", None
        ))
    con.commit()
    con.close()

    result = api.financial_day_resource("2027-02-01",
        now=datetime(2027, 2, 3, 12, tzinfo=ZoneInfo("Europe/Amsterdam")))
    f = result["financialAccounting"]
    assert result["schema"] == "EMS_WEB_FINANCIAL_DAY_V1"
    assert result["readOnly"] is True and result["controlWrites"] is False
    assert f["status"] == "SUPPLIER_VARIABLE_SUBTOTAL_ONLY", f
    assert f["p1Coverage"] == 1, f
    assert f["importKWh"] == 10 and f["exportKWh"] == 4
    assert f["netVariableSupplierCostEur"] == 1.46, f
    assert f["batterySavingsEur"] is None and f["fullBillAvailable"] is False
    assert "source" not in json.dumps(result)

    con = sqlite3.connect(db)
    con.execute("DELETE FROM house_energy_intervals WHERE rowid > 100")
    con.commit()
    con.close()
    partial = api.financial_day_resource("2027-02-01",
        now=datetime(2027, 2, 3, 12, tzinfo=ZoneInfo("Europe/Amsterdam")))
    assert partial["financialAccounting"]["status"] == "INSUFFICIENT_P1_COUNTER_COVERAGE"
    assert partial["financialAccounting"]["netVariableSupplierCostEur"] is None

    old = api.financial_day_resource("2026-11-20",
        now=datetime(2026, 11, 21, 12, tzinfo=ZoneInfo("Europe/Amsterdam")))
    assert old["financialAccounting"]["status"] == "ANNUAL_SALDERING_NO_DAILY_SETTLEMENT"
    assert old["financialAccounting"]["netVariableSupplierCostEur"] is None

    for invalid in ("today", "2026-02-30", "2027-02-01/../../secret", "2027-02-03"):
        try:
            api.financial_day_resource(invalid,
                now=datetime(2027, 2, 3, 12, tzinfo=ZoneInfo("Europe/Amsterdam")))
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid or open day accepted: "+invalid)
print("PASS: read-only ENGIE financial Evaluatie API and missing-data boundaries")

#!/usr/bin/env python3
"""Archive each PV Forecast V2 run for future closed-period validation."""
import json, sqlite3
from pathlib import Path
SRC=Path("/home/jeroen/ems/data/pv-forecast-v2.json")
DB=Path("/home/jeroen/ems/data/ems-history.sqlite")
def main():
 d=json.loads(SRC.read_text()); assert d.get("schema")=="EMS_PI_PV_FORECAST_V2"
 con=sqlite3.connect(DB,timeout=2); con.execute("PRAGMA busy_timeout=2000")
 con.execute("""CREATE TABLE IF NOT EXISTS pv_forecast_v2_archive(
 generated_at TEXT NOT NULL, slot_start_utc TEXT NOT NULL, forecast_w REAL NOT NULL,
 confidence REAL, model_basis TEXT, PRIMARY KEY(generated_at,slot_start_utc))""")
 for s in d.get("slots",[]): con.execute("INSERT OR IGNORE INTO pv_forecast_v2_archive VALUES(?,?,?,?,?)",(d["generatedAt"],s["start"],s["pvForecastW"],s.get("confidence"),s.get("modelBasis")))
 con.commit(); n=con.execute("SELECT changes()").fetchone()[0]; con.close()
 print("PASS: PV Forecast V2 archived")
if __name__=="__main__": main()

#!/usr/bin/env python3
"""Read-only audit of historical PV energy suitable for forecast validation."""
import argparse, json, sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
DB=Path("/home/jeroen/ems/data/ems-history.sqlite")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--db",default=str(DB)); ap.add_argument("--json",action="store_true"); a=ap.parse_args()
    con=sqlite3.connect(a.db,timeout=2.0)
    try:
        rows=con.execute("""SELECT start_ts_utc,end_ts_utc,duration_seconds,pv_total_kwh,quality,discontinuity_reason FROM house_energy_intervals WHERE pv_total_kwh IS NOT NULL ORDER BY end_ts_utc""").fetchall()
    finally: con.close()
    q=Counter(r[4] for r in rows)
    valid=[r for r in rows if r[4]=="observed" and 60<=int(r[2])<=900 and float(r[3])>=0]
    days=sorted({r[1][:10] for r in valid})
    out={"schema":"EMS_PI_PV_HISTORY_VALIDATION_AUDIT_V0.1","generatedAt":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"readOnly":True,"source":"house_energy_intervals","totalIntervals":len(rows),"qualityCounts":dict(q),"validIntervals":len(valid),"validDays":len(days),"firstValid":valid[0][0] if valid else None,"lastValid":valid[-1][1] if valid else None,"validEnergyKWh":round(sum(float(r[3]) for r in valid),3),"acceptance":"quality=observed; 60<=duration_seconds<=900; pv_total_kwh>=0","excludedIntervals":len(rows)-len(valid)}
    if a.json: print(json.dumps(out,indent=2))
    else:
        for k,v in out.items(): print(f"{k}: {v}")
if __name__=="__main__": main()

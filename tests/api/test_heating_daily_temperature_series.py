#!/usr/bin/env python3
"""Focused read-only heating day series: steps, cooling, gaps, DST, archive gate."""
import importlib.util
import json
import sqlite3
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SPEC=importlib.util.spec_from_file_location(
    "heating_timeseries_api", Path("services/pi/api/web-data/server.py"))
api=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)
TZ=ZoneInfo("Europe/Amsterdam")
ROOMS=("woonkamer","eetkamer","keuken","serre","douwe_slaapkamer",
       "erker_douwe","krijn_slaapkamer","master_bedroom")
DAY=date(2026,10,17)
def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def build(path, day, gap=None, no_heating_off=False):
    start=datetime.combine(day,time.min,TZ).astimezone(timezone.utc)
    end=datetime.combine(day+timedelta(days=1),time.min,TZ).astimezone(timezone.utc)
    count=int((end-start).total_seconds()/900)
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE devices (id INTEGER PRIMARY KEY,device_key TEXT);
        CREATE TABLE metrics (id INTEGER PRIMARY KEY,metric_key TEXT);
        CREATE TABLE measurements_15m
          (slot_start_utc TEXT,device_id INTEGER,metric_id INTEGER,
           value_avg REAL,quality TEXT);
        """)
        dev={key:i+1 for i,key in enumerate(["quatt_cic"]+
             ["honeywell_"+key for key in ROOMS])}
        metric={key:i+1 for i,key in enumerate([
            "room_temperature_c","room_setpoint_c",
            "outside_temperature_c","heating_on"])}
        db.executemany("INSERT INTO devices VALUES (?,?)",[(v,k) for k,v in dev.items()])
        db.executemany("INSERT INTO metrics VALUES (?,?)",[(v,k) for k,v in metric.items()])
        def add(at,d,m,v,q="complete"):
            db.execute("INSERT INTO measurements_15m VALUES (?,?,?,?,?)",
                       (at,dev[d],metric[m],v,q))
        for i in range(count):
            stamp=iso(start+timedelta(minutes=15*i))
            off=(i<24 or i>=72) and not no_heating_off
            add(stamp,"quatt_cic","heating_on",0. if off else 1.)
            add(stamp,"quatt_cic","outside_temperature_c",11.5)
            for room in ROOMS:
                target=19 if i<60 else 20
                actual=(19.5-0.02*i if i<24 else
                        19.04 if i<60 else
                        18.3+0.4*(i-60) if i<72 else
                        20.5-0.08*(i-72))
                add(stamp,"honeywell_"+room,"room_setpoint_c",target)
                if not (gap is not None and i==gap):
                    add(stamp,"honeywell_"+room,"room_temperature_c",actual)
        db.commit()
    return count

old=api.heating_daily_resource
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/"h.sqlite"
    api.HISTORY_DB=str(path)
    api.heating_daily_resource=lambda value: {"dateLocal":value} if value==DAY.isoformat() else None
    n=build(path,DAY)
    assert n==96
    report=api.heating_daily_temperature_resource(DAY.isoformat())
    assert report["schema"]=="EMS_WEB_HEATING_DAILY_TEMPERATURE_V1"
    assert report["controlWrites"] is False and report["mode"]=="READ_ONLY"
    assert report["setpointProvenance"].startswith("OBSERVED_HONEYWELL_")
    assert len(report["rooms"])==8 and len(report["quatt"])==96
    room=report["rooms"][0]
    assert room["completePairedSlots"]==96
    assert room["responseEvents"][0]["status"]=="REACHED"
    assert room["responseEvents"][0]["minutesToTarget"]==60
    assert room["cooling"]["night"]["status"]=="OBSERVED_WITH_QUATT_SIGNAL_OFF"
    assert room["cooling"]["evening"]["status"]=="OBSERVED_WITH_QUATT_SIGNAL_OFF"
    assert room["cooling"]["night"]["coolingCPerHour"]>0
    assert report["quatt"][0]["heatingOnFraction"]==0
    assert api.heating_daily_temperature_resource("2026-10-16") is None
    # Missing quarter: graph has explicit null, no interpolation or invented reaction.
    path.unlink()
    build(path,DAY,gap=62)
    report=api.heating_daily_temperature_resource(DAY.isoformat())
    assert report["rooms"][0]["series"][62]["temperatureC"] is None
    assert report["rooms"][0]["responseEvents"][0]["status"]=="INSUFFICIENT_DATA"
    # If Quatt heating signal is active, do not report a "free cooling" estimate.
    path.unlink()
    build(path,DAY,no_heating_off=True)
    report=api.heating_daily_temperature_resource(DAY.isoformat())
    assert report["rooms"][0]["cooling"]["night"]["coolingCPerHour"] is None
    assert report["rooms"][0]["cooling"]["evening"]["coolingCPerHour"] is None
    # Local day during the autumn DST change contains 25h, never forced to 96.
    fall=date(2026,10,25)
    path.unlink()
    assert build(path,fall)==100
    api.heating_daily_resource=lambda value: {"dateLocal":value} if value==fall.isoformat() else None
    report=api.heating_daily_temperature_resource(fall.isoformat())
    assert report["expectedSlots"]==100 and len(report["quatt"])==100

api.heating_daily_resource=old
source=Path("services/pi/api/web-data/server.py").read_text()
front=Path("frontend/heating-analysis/render/heating-analysis.js").read_text()
html=Path("frontend/heating-analysis/index.html").read_text()
assert '["web", "analysis", "heating", "temperature", "day"]' in source
assert "/web/analysis/heating/temperature/day/" in front
assert 'id="room-select"' in html and 'id="temperature-chart"' in html
assert 'id="cooling-evening"' in html and 'id="cooling-night"' in html
assert 'id="reaction"' in html
assert 'id="temperature-chart"' not in Path("frontend/heating/index.html").read_text()
print("PASS: heating daily chart, guarded step response, guarded cooling and DST")

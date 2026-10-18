#!/usr/bin/env python3
"""Single focused contract: allowlisted Heating Analysis API and isolated V2 page."""
import importlib.util
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path("services/pi/api/web-data/server.py")
spec = importlib.util.spec_from_file_location("heating_web_daily", SOURCE)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
day = (datetime.now(ZoneInfo("Europe/Amsterdam")).date()-timedelta(days=2)).isoformat()

def quatt():
    return {
        "quattElectricKWh": 7.1972,
        "quattHeatHP1SensorKWh": 19.83,
        "quattHeatHP2SensorKWh": 0,
        "pairedHP1HeatToElectricRatio": 2.75,
        "quattElectricCompleteSlots": 96,
        "expectedSlots": 96,
        "heatingSignalMean": .65,
        "outsideTempMeanC": 12.3,
        "rooms": {
            k: {
                "coverage": 1.0, "firstTemperatureC": 19.0,
                "lastTemperatureC": 20.0, "lastSetpointC": 20.0,
                "belowSetpointBy02CSlots": 0,"completePairedSlots": 96
            } for k in (
                "woonkamer","eetkamer","keuken","serre",
                "douwe_slaapkamer","erker_douwe",
                "krijn_slaapkamer","master_bedroom")
        },
    }

def energy(quality="GOOD"):
    return {
        "balanceQuality": quality,"pairedCoverage": .99,
        "heldPvHours": 10.7, "estimatedPvHours": 12.1,
        "importKWh": 18.779, "exportKWh": 12.251,
        "pvProducedKWh": 28.124, "houseKWh": 34.652
    }

item = {
    "schema": "EMS_HEATING_DAILY_EVALUATION_V0.1", "dateLocal":day,
    "mode":"READ_ONLY","controlMode":"SHADOW","controlWrites":False,
    "quality":{"status":"GOOD","issues":[]},
    "energy":energy(),"quattAndRooms":quatt(),
    "periods":{
        key:{"energy":energy(),"quattAndRooms":quatt()}
        for key in ("00-09","09-12","12-17","17-24")
    },
    "cicAndGas":{
        "cicBoilerSelectedSamples":0,"gasObservedSpanDeltaM3":.15,
        "gasMeterObservedSamples":30,
        "secret":"must not escape"
    },
    "private_token":"never include this"
}
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/"heating-daily-archive.json"
    api.HEATING_DAILY_ARCHIVE_FILE=str(path)
    archive={"schema":"EMS_HEATING_DAILY_ARCHIVE_V0.1","days":{day:item}}
    path.write_text(json.dumps(archive))
    r=api.heating_daily_resource(day)
    assert r["schema"]=="EMS_WEB_HEATING_DAILY_V1"
    assert r["dateLocal"]==day and r["readOnly"] is True
    assert r["controlWrites"] is False and r["controlMode"]=="SHADOW"
    assert len(r["rooms"])==8 and len(r["periods"])==4
    assert r["energy"]["exportKWh"]==12.251
    assert r["quatt"]["electricKWh"]==7.1972
    assert "never include this" not in json.dumps(r)
    assert "must not escape" not in json.dumps(r)
    assert api.heating_daily_resource("2020-01-01") is None

    for invalid in ("tomorrow","2026-02-30","../secret",
                    datetime.now(ZoneInfo("Europe/Amsterdam")).date().isoformat()):
        try:
            api.heating_daily_resource(invalid)
            raise AssertionError("Open or invalid date allowed")
        except ValueError:
            pass

    # Bad paired energy may not be displayed as an exact total.
    archive["days"][day]["energy"]["balanceQuality"]="INSUFFICIENT_OR_INCONSISTENT"
    archive["days"][day]["periods"]["00-09"]["energy"]["balanceQuality"]="INSUFFICIENT"
    path.write_text(json.dumps(archive))
    r=api.heating_daily_resource(day)
    assert r["energy"]["importKWh"] is None and r["energy"]["exportKWh"] is None
    assert r["periods"][0]["energy"]["exportKWh"] is None

    # Never serve an archive record that could be interpreted as live control.
    archive["days"][day]["controlWrites"]=True
    path.write_text(json.dumps(archive))
    try:
        api.heating_daily_resource(day)
        raise AssertionError("Control report accepted")
    except RuntimeError:
        pass

nav=Path("frontend/shared/navigation.js").read_text()
html=Path("frontend/heating-analysis/index.html").read_text()
render=Path("frontend/heating-analysis/render/heating-analysis.js").read_text()
heating=Path("frontend/heating/index.html").read_text()
assert 'key: "heating-analysis"' in nav and '"heating-analysis"' in nav
assert 'href: "../heating-analysis/"' in nav
assert 'data-ems-main-nav' in html and '../shared/navigation.js' in html
assert '/web/analysis/heating/day/' in render
assert 'EMS_WEB_HEATING_DAILY_V1' in render
assert 'controlWrites!==false' in render
assert 'heating-analysis.js' not in heating
assert '["web", "analysis", "heating", "day"]' in SOURCE.read_text()
assert "import subprocess" not in SOURCE.read_text()
print("PASS: Heating Analysis separate page and allowlisted historical day API")

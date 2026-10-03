#!/usr/bin/env python3
import importlib.util
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services/pi/history/archive_flex_context_snapshot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("flex_context_archive_contract", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(at):
    iso = at.isoformat().replace("+00:00", "Z")
    return {
        "schema": "EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1",
        "capturedAt": iso,
        "readOnly": True,
        "controlWrites": False,
        "historicalBackfill": False,
        "heating": {
            "generatedAt": iso,
            "baselineAuthority": "HONEYWELL",
            "house": {"baselineHeatingDemandPresent": False},
            "cvGuard": {"status": "OK", "cvActive": False},
            "rooms": [{
                "key": "serre",
                "current": {"temperature_C": 20.0},
                "shadow": {"state": "PREHEAT_READY_FOR_GRANT", "reason": "AWAITING_CENTRAL_PV_PRIORITY"},
            }],
        },
        "priority": {
            "generatedAt": iso,
            "decision": {
                "priorityOwner": "HEATING",
                "heatingShadowGrant": "SHADOW_GRANT",
                "physicalWriteAllowed": False,
                "reason": "HEATING_SCARCE_WINDOW_WITH_NO_EV_DEADLINE_PRESSURE",
            },
        },
        "progression": {
            "generatedAt": iso,
            "physicalWriteAllowed": False,
            "sourceFreshness": {"heating": {"status": "OK"}, "priority": {"status": "OK"}},
            "rooms": [{
                "key": "serre",
                "currentTemperature_C": 20.0,
                "futureHoneywellTarget_C": 21.0,
                "heatingEligibility": {"state": "PREHEAT_READY_FOR_GRANT"},
                "planner": {"domainGrant": "SHADOW_GRANT"},
                "progression": {
                    "state": "STEP_WAIT",
                    "reason": "SHADOW_STEP_STARTED",
                    "activeStepTarget_C": 20.5,
                    "physicalWritePerformed": False,
                },
            }],
        },
        "warmWaterInput": {
            "fileMtimeAt": iso,
            "mode": "shadow",
            "controlWrites": False,
            "warmWater": {"goalReached": False, "remainingFallbackMin": 60},
        },
        "warmWaterSeasonal": {
            "generatedAt": iso,
            "status": "OK",
            "currentMode": "CV",
            "advice": "KEEP_CURRENT",
        },
        "energyState": {
            "sourceSampleAt": iso,
            "generatedAt": iso,
            "hotWater": {"mode": False, "boilerOn": False, "boilerPowerW": 0},
        },
    }


def main():
    module = load_module()
    t0 = datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "planner.sqlite"

        first = module.archive(snapshot(t0), db_path=db, now=t0)
        assert first["inserted"] is True

        t1 = t0 + timedelta(minutes=5)
        second = module.archive(snapshot(t1), db_path=db, now=t1)
        assert second["inserted"] is False
        assert second["dedupe"] == "UNCHANGED_WITHIN_HEARTBEAT"

        t2 = t0 + timedelta(minutes=16)
        third = module.archive(snapshot(t2), db_path=db, now=t2)
        assert third["inserted"] is True

        con = sqlite3.connect(db)
        count = con.execute("SELECT COUNT(*) FROM flex_context_snapshots").fetchone()[0]
        con.close()
        assert count == 2

    print("PASS: flex context history archive contract")


if __name__ == "__main__":
    main()

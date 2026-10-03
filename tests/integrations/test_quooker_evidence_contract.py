#!/usr/bin/env python3
import importlib.util
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INGEST = ROOT / "services/pi/integrations/homey/ingress/quooker_evidence_ingest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("quooker_evidence_contract", INGEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema": "EMS_HOMEY_QUOOKER_EVIDENCE_V0.1",
        "generatedAt": now,
        "readOnly": True,
        "observabilityOnly": True,
        "controlImpact": "NONE",
        "control": {
            "schema": "EM2_CONTROL_QUOOKER_V0.1",
            "mode": "OPPORTUNITY",
            "target_on": True,
            "reason": "OPPORTUNITY_START_EXPORT",
            "modeledPowerW": 1580,
            "thresholds": {"startExportW": 1250, "stopImportW": 600},
            "p1": {"avgGridW": -2100, "p1Fresh": True},
        },
        "actuator": {
            "schema": "EM2_QUOOKER_ACTUATOR_STATUS_V0.1",
            "controlValid": True,
            "controlFresh": True,
            "desiredOn": True,
            "actualOn": True,
            "wouldWrite": False,
            "reason": "OPPORTUNITY_START_EXPORT",
            "safety": {
                "shadow": True,
                "deviceWrites": False,
                "physicalWritePerformed": False,
            },
        },
        "detector": {
            "schema": "EM2_QUOOKER_DETECTOR_V0.5",
            "valid": True,
            "switchOn": True,
            "active": False,
            "status": "ON_IDLE",
            "powerW": 0,
            "reason": "ON_IDLE_BASELINE_TRACK",
            "lastHeatingAt": "2026-10-03T09:15:00Z",
            "lastHeatingPowerW": 1575,
            "safety": {
                "observeOnly": True,
                "physicalWritePerformed": False,
            },
        },
        "safety": {
            "targetedLogicReadsOnly": True,
            "deviceReads": False,
            "logicWrites": False,
            "deviceWrites": False,
            "physicalWritePerformed": False,
        },
    }


def main():
    module = load_module()
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "history.sqlite"

        first = module.archive_quooker_evidence(payload(), db_path=db)
        assert first["inserted"] is True

        second_payload = payload()
        second_payload["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        second_payload["control"]["p1"]["avgGridW"] = -2600
        second_payload["detector"]["powerW"] = 25
        second = module.archive_quooker_evidence(second_payload, db_path=db)
        assert second["inserted"] is False
        assert second["dedupe"] == "LATEST_NORMALIZED_EVIDENCE"

        third_payload = payload()
        third_payload["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        third_payload["control"]["target_on"] = False
        third_payload["control"]["reason"] = "OPPORTUNITY_STOP_IMPORT_LIMIT"
        third = module.archive_quooker_evidence(third_payload, db_path=db)
        assert third["inserted"] is True

        con = sqlite3.connect(db)
        rows = con.execute(
            """
            SELECT control_mode,control_target_on,control_reason,avg_grid_w,p1_fresh,
                   actuator_desired_on,actuator_actual_on,actuator_would_write,
                   detector_active,detector_status,detector_power_w,
                   physical_write_performed
            FROM quooker_control_events
            ORDER BY id
            """
        ).fetchall()
        con.close()

        assert len(rows) == 2
        assert rows[0] == (
            "OPPORTUNITY", 1, "OPPORTUNITY_START_EXPORT", -2100.0, 1,
            1, 1, 0, 0, "ON_IDLE", 0.0, 0,
        )
        assert rows[1][1:3] == (0, "OPPORTUNITY_STOP_IMPORT_LIMIT")

    print("PASS: Quooker evidence archive contract")


if __name__ == "__main__":
    main()

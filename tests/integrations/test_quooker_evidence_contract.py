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


def now_text():
    return datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")


def shadow_payload():
    return {
        "schema": "EMS_HOMEY_QUOOKER_EVIDENCE_V0.1",
        "generatedAt": now_text(),
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
            "mode": "SHADOW",
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


def live_payload():
    value = shadow_payload()
    value["generatedAt"] = now_text()
    value["actuator"] = {
        "schema": "EM2_QUOOKER_ACTUATOR_STATUS_V0.2",
        "mode": "LIVE",
        "controlValid": True,
        "controlFresh": True,
        "desiredOn": True,
        "actualOnBefore": False,
        "actualOnAfter": True,
        "physicalWritePerformed": True,
        "writeError": None,
        "reason": "OPPORTUNITY_START_EXPORT",
        "safety": {
            "shadow": False,
            "deviceWrites": True,
            "failClosed": True,
            "soleWriterClaimed": True,
            "idempotent": True,
        },
    }
    return value


def create_legacy_table(db):
    con = sqlite3.connect(db)
    con.execute(
        """
        CREATE TABLE quooker_control_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_hash TEXT NOT NULL UNIQUE,
            ts_utc TEXT NOT NULL,
            control_mode TEXT,
            control_target_on INTEGER,
            control_reason TEXT,
            modeled_power_w REAL,
            avg_grid_w REAL,
            p1_fresh INTEGER,
            start_export_w REAL,
            stop_import_w REAL,
            actuator_control_valid INTEGER,
            actuator_control_fresh INTEGER,
            actuator_desired_on INTEGER,
            actuator_actual_on INTEGER,
            actuator_would_write INTEGER,
            actuator_reason TEXT,
            detector_valid INTEGER,
            detector_switch_on INTEGER,
            detector_active INTEGER,
            detector_status TEXT,
            detector_power_w REAL,
            detector_reason TEXT,
            detector_last_heating_at TEXT,
            detector_last_heating_power_w REAL,
            physical_write_performed INTEGER,
            raw_json TEXT NOT NULL,
            collected_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.commit()
    con.close()


def main():
    module = load_module()
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "history.sqlite"

        first = module.archive_quooker_evidence(shadow_payload(), db_path=db)
        assert first["inserted"] is True

        second_payload = shadow_payload()
        second_payload["generatedAt"] = now_text()
        second_payload["control"]["p1"]["avgGridW"] = -2600
        second_payload["detector"]["powerW"] = 25
        second = module.archive_quooker_evidence(second_payload, db_path=db)
        assert second["inserted"] is False
        assert second["dedupe"] == "LATEST_NORMALIZED_EVIDENCE"

        third_payload = shadow_payload()
        third_payload["generatedAt"] = now_text()
        third_payload["control"]["target_on"] = False
        third_payload["control"]["reason"] = "OPPORTUNITY_STOP_IMPORT_LIMIT"
        third = module.archive_quooker_evidence(third_payload, db_path=db)
        assert third["inserted"] is True

        fourth = module.archive_quooker_evidence(live_payload(), db_path=db)
        assert fourth["inserted"] is True

        con = sqlite3.connect(db)
        rows = con.execute(
            """
            SELECT control_mode,control_target_on,control_reason,avg_grid_w,p1_fresh,
                   actuator_schema,actuator_mode,actuator_desired_on,
                   actuator_actual_on,actuator_actual_on_before,
                   actuator_actual_on_after,actuator_would_write,
                   actuator_write_error,detector_active,detector_status,
                   detector_power_w,physical_write_performed
            FROM quooker_control_events
            ORDER BY id
            """
        ).fetchall()
        con.close()

        assert len(rows) == 3
        assert rows[0][5:13] == (
            "EM2_QUOOKER_ACTUATOR_STATUS_V0.1",
            "SHADOW",
            1,
            1,
            None,
            None,
            0,
            None,
        )
        assert rows[2][5:13] == (
            "EM2_QUOOKER_ACTUATOR_STATUS_V0.2",
            "LIVE",
            1,
            None,
            0,
            1,
            None,
            None,
        )
        assert rows[2][-1] == 1

    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "legacy.sqlite"
        create_legacy_table(db)
        result = module.archive_quooker_evidence(live_payload(), db_path=db)
        assert result["inserted"] is True

        con = sqlite3.connect(db)
        columns = {
            row[1] for row in con.execute(
                "PRAGMA table_info(quooker_control_events)"
            )
        }
        row = con.execute(
            """
            SELECT actuator_schema,actuator_mode,
                   actuator_actual_on_before,actuator_actual_on_after,
                   actuator_write_error,physical_write_performed
            FROM quooker_control_events
            """
        ).fetchone()
        con.close()

        assert {
            "actuator_schema",
            "actuator_mode",
            "actuator_actual_on_before",
            "actuator_actual_on_after",
            "actuator_write_error",
        }.issubset(columns)
        assert row == (
            "EM2_QUOOKER_ACTUATOR_STATUS_V0.2",
            "LIVE",
            0,
            1,
            None,
            1,
        )

    print("PASS: Quooker evidence archive contract")


if __name__ == "__main__":
    main()

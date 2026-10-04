#!/usr/bin/env python3
import importlib.util
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "services/pi/api/status/history_archive.py"
EV_INGEST = ROOT / "services/pi/integrations/homey/ingress/ev_control_ingest.py"
HEALTH_SCRIPT = ROOT / "src/homey/observability/ev/ev-device-health-v0.4.observability-only.js"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_db(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_device_id TEXT NOT NULL UNIQUE,
        device_key TEXT NOT NULL UNIQUE,
        name TEXT,
        device_type TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_key TEXT NOT NULL UNIQUE,
        unit TEXT,
        value_type TEXT NOT NULL DEFAULT 'number',
        description TEXT
    );
    CREATE TABLE measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_utc TEXT NOT NULL,
        device_id INTEGER NOT NULL,
        metric_id INTEGER NOT NULL,
        value_real REAL,
        value_text TEXT,
        quality TEXT NOT NULL DEFAULT 'ok',
        source_resolution_seconds INTEGER,
        collected_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ts_utc, device_id, metric_id)
    );
    INSERT INTO metrics(metric_key, unit, value_type, description)
    VALUES ('electrical_power_w', 'W', 'number', 'power');
    """)
    con.commit()
    con.close()


def main():
    archive = load_module("history_archive_ev_contract", ARCHIVE)
    ev_ingest = load_module("ev_control_ingest_contract", EV_INGEST)

    health_text = HEALTH_SCRIPT.read_text(encoding="utf-8")
    assert "EM2_EV_DEVICE_HEALTH_V0.4" in health_text
    assert "EQUALIZER_ID='7dd35f8f-1dca-42f5-9b41-9b69bd14c611'" in health_text
    assert "target_circuit_current" in health_text
    assert "phaseCurrentsA:{l1:easeeL1A,l2:easeeL2A,l3:easeeL3A}" in health_text
    assert "equalizer:{deviceAvailable:equalizerAvailable" in health_text

    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "history.sqlite"
        create_db(db)

        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        state = {
            "meta": {"source_sample_at": ts, "min_publish_interval_sec": 300},
            "grid": {"power_w": -1200},
            "pv": {"solaredge_w": 2000, "goodwe_4200_w": 800, "goodwe_2000_w": 300},
            "hot_water": {"boiler_power_w": 0},
            "quatt": {"power_w": 100},
            "tesla": {
                "power_w": 1600,
                "connected": True,
                "charging": True,
                "requested_a": 8,
                "offered_a": 8,
                "l1_a": 7.9,
                "l2_a": 0,
                "l3_a": 0,
                "deadline_active": False,
                "deadline_max_a": 11,
                "remaining_kwh": 3.2,
                "charge_state": "plugged_in_charging",
                "need": "TESLA_BUFFER_EXPORT",
            },
            "manager": {
                "decision": "TESLA_BUFFER_EXPORT",
                "reason": "EV beschikbaar budget 1800 W",
                "priority": "MAY",
            },
            "balance": {
                "control_gate": {"grid_measurement_valid": True},
                "source_timing": {
                    "p1Fresh": True,
                    "freshness": {
                        "solarEdge": {"fresh": True},
                        "goodWe4200": {"fresh": True},
                        "goodWe2000": {"fresh": True},
                    },
                },
            },
            "loads": {},
        }
        result = archive.archive_state_history(state, db)
        assert result["archived"] is True

        con = sqlite3.connect(db)
        rows = dict(con.execute("""
            SELECT x.metric_key, COALESCE(m.value_text, CAST(m.value_real AS TEXT))
            FROM measurements m
            JOIN metrics x ON x.id=m.metric_id
            WHERE x.metric_key IN (
                'ev_connected','ev_charging','ev_requested_a','ev_offered_a',
                'ev_charge_state','ev_need','manager_decision','manager_reason'
            )
        """).fetchall())
        con.close()

        assert rows["ev_connected"] == "1.0"
        assert rows["ev_charging"] == "1.0"
        assert rows["ev_requested_a"] == "8.0"
        assert rows["ev_offered_a"] == "8.0"
        assert rows["ev_charge_state"] == "plugged_in_charging"
        assert rows["ev_need"] == "TESLA_BUFFER_EXPORT"
        assert rows["manager_decision"] == "TESLA_BUFFER_EXPORT"
        assert "beschikbaar budget" in rows["manager_reason"]

        event = {
            "schema": "EMS_HOMEY_EV_CONTROL_EVIDENCE_V0.1",
            "generatedAt": ts,
            "readOnly": True,
            "observabilityOnly": True,
            "controlImpact": "NONE",
            "intent": {
                "sourceRevision": 123,
                "controlRevision": "rev-123",
                "targets": {"ev": {"target_W": 1840}},
            },
            "adapter": {
                "sourceRevision": 123,
                "controlRevision": "rev-123",
                "command": {"mode": "1P", "requested_A": 8, "requested_W": 1840},
            },
            "gate": {
                "finalStatus": "PASS",
                "errors": [],
                "controlRevision": "rev-123",
            },
            "actuator": {
                "status": "STABLE",
                "reason": "SAME_PHASE_CURRENT_APPLIED",
                "targetA": 8,
                "phaseMode": "1P",
                "confirmedMode": "1P",
                "physicalWritePerformed": True,
                "transition": {"stage": "STABLE", "failure": None},
                "observed": {"chargeState": "plugged_in_charging"},
            },
            "deviceHealth": {
                "schema": "EM2_EV_DEVICE_HEALTH_V0.4",
                "status": "OK",
                "reason": "FRESH_TELEMETRY",
                "easee": {
                    "chargeState": "plugged_in_charging",
                    "requestedA": 10,
                    "offeredA": 8,
                    "targetCircuitA": 20,
                    "measureW": 5647,
                    "phaseCurrentsA": {"l1": 8.06, "l2": 8.11, "l3": 8.09},
                    "telemetryAgeSec": 1,
                },
                "equalizer": {
                    "deviceAvailable": True,
                    "measureW": 7868,
                    "phaseCurrentsA": {"l1": 16, "l2": 9, "l3": 8},
                    "telemetryAgeSec": 1,
                },
                "p1": {
                    "gridW": 7867,
                    "l1A": 15.89,
                    "l2A": 9.41,
                    "l3A": 8.39,
                },
            },
        }
        stored = ev_ingest.archive_ev_control(event, db)
        assert stored["archived"] is True
        assert stored["inserted"] is True

        # Simulate an already-commissioned row whose hash came from an older
        # algorithm. Transition-safe dedupe must still compare normalized fields
        # and suppress an identical new snapshot.
        con = sqlite3.connect(db)
        con.execute(
            "UPDATE ev_control_events SET event_hash=? WHERE id=(SELECT MIN(id) FROM ev_control_events)",
            ("legacy-hash-v1",),
        )
        con.commit()
        con.close()

        duplicate = dict(event)
        duplicate["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        duplicate["intent"] = dict(event["intent"])
        duplicate["intent"]["generatedAt"] = duplicate["generatedAt"]
        duplicate["adapter"] = dict(event["adapter"])
        duplicate["adapter"]["generatedAt"] = duplicate["generatedAt"]
        duplicate["gate"] = dict(event["gate"])
        duplicate["gate"]["updatedAt"] = duplicate["generatedAt"]
        duplicate["actuator"] = dict(event["actuator"])
        duplicate["actuator"]["at"] = duplicate["generatedAt"]
        duplicate["deviceHealth"] = dict(event["deviceHealth"])
        duplicate["deviceHealth"]["sampledAt"] = duplicate["generatedAt"]
        duplicate_stored = ev_ingest.archive_ev_control(duplicate, db)
        assert duplicate_stored["archived"] is True
        assert duplicate_stored["inserted"] is False

        downstream_changed = dict(event)
        downstream_changed["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        downstream_changed["deviceHealth"] = dict(event["deviceHealth"])
        downstream_changed["deviceHealth"]["easee"] = dict(event["deviceHealth"]["easee"])
        downstream_changed["deviceHealth"]["easee"]["offeredA"] = 10
        downstream_changed["deviceHealth"]["equalizer"] = dict(event["deviceHealth"]["equalizer"])
        downstream_changed["deviceHealth"]["equalizer"]["phaseCurrentsA"] = {
            "l1": 18,
            "l2": 11,
            "l3": 10,
        }
        downstream_stored = ev_ingest.archive_ev_control(downstream_changed, db)
        assert downstream_stored["inserted"] is True

        changed = dict(downstream_changed)
        changed["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        changed["actuator"] = dict(event["actuator"])
        changed["actuator"]["reason"] = "SAME_PHASE_CURRENT_CONFIRMED"
        changed_stored = ev_ingest.archive_ev_control(changed, db)
        assert changed_stored["inserted"] is True

        con = sqlite3.connect(db)
        rows = con.execute("""
            SELECT phase_mode, gate_status, actuator_status, actuator_reason,
                   actuator_confirmed_mode, device_health_status, downstream_json
            FROM ev_control_events
            ORDER BY id
        """).fetchall()
        con.close()
        assert len(rows) == 3
        assert rows[0][:6] == (
            "1P", "PASS", "STABLE", "SAME_PHASE_CURRENT_APPLIED", "1P", "OK"
        )
        first_downstream = __import__("json").loads(rows[0][6])
        assert first_downstream["easee"]["requestedA"] == 10.0
        assert first_downstream["easee"]["offeredA"] == 8.0
        assert first_downstream["equalizer"]["phaseCurrentsA"]["l1"] == 16

        second_downstream = __import__("json").loads(rows[1][6])
        assert second_downstream["easee"]["offeredA"] == 10.0
        assert second_downstream["equalizer"]["phaseCurrentsA"]["l1"] == 18

        assert rows[2][:6] == (
            "1P", "PASS", "STABLE", "SAME_PHASE_CURRENT_CONFIRMED", "1P", "OK"
        )

    print("PASS: AI V0.2 EV evidence archive contract")


if __name__ == "__main__":
    main()

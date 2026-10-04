#!/usr/bin/env python3
import importlib.util
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_ai_semantic_event_contract", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_history(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE semantic_event_meta (
            key TEXT PRIMARY KEY,
            value_text TEXT NOT NULL
        );
        CREATE TABLE semantic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_hash TEXT NOT NULL UNIQUE,
            ts_utc TEXT NOT NULL,
            event_type TEXT NOT NULL,
            domain TEXT NOT NULL,
            subject TEXT NOT NULL,
            state_key TEXT NOT NULL,
            provenance_class TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_at_utc TEXT,
            observed_at_utc TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO semantic_event_meta(key,value_text) VALUES (?,?)",
        ("schema", "EMS_PI_SEMANTIC_EVENT_ARCHIVE_V0.1"),
    )
    con.execute(
        "INSERT INTO semantic_event_meta(key,value_text) VALUES (?,?)",
        ("commissioned_at_utc", "2026-10-04T11:00:00Z"),
    )
    con.execute(
        """
        INSERT INTO semantic_events(
            event_hash,ts_utc,event_type,domain,subject,state_key,
            provenance_class,source_name,source_at_utc,observed_at_utc,
            before_json,after_json,details_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "event-1",
            "2026-10-04T12:00:00Z",
            "EV_DEADLINE_SET",
            "EV",
            "ev_deadline",
            "ev.deadline.command",
            "USER_INTENT_COMMAND",
            "tesla-deadline-command.json",
            "2026-10-04T12:00:00Z",
            "2026-10-04T12:00:50Z",
            json.dumps({"requestId": "old", "active": False}),
            json.dumps({
                "requestId": "new",
                "active": True,
                "deadline": "2026-10-04T18:00:00+02:00",
                "goalKWh": 12.4,
            }),
            json.dumps({
                "schema": "EMS_PI_SEMANTIC_EVENT_ARCHIVE_V0.1",
                "historicalBackfill": False,
                "baselineWasObserved": True,
            }),
        ),
    )
    con.commit()
    con.close()


def main():
    ai = load_module()

    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "history.sqlite"
        create_history(db)
        ai.HISTORY_DB = str(db)

        events, coverage = ai._semantic_events(date(2026, 10, 4))
        assert coverage["available"] is True
        assert coverage["schema"] == "EMS_PI_SEMANTIC_EVENT_ARCHIVE_V0.1"
        assert coverage["commissionedAt"].startswith("2026-10-04T13:00:00+02:00")
        assert coverage["eventCount"] == 1

        assert len(events) == 1
        event = events[0]
        assert event["atLocal"].startswith("2026-10-04T14:00:00+02:00")
        assert event["eventType"] == "EV_DEADLINE_SET"
        assert event["provenanceClass"] == "USER_INTENT_COMMAND"
        assert event["after"]["requestId"] == "new"
        assert event["details"]["historicalBackfill"] is False

        ai._load_performance = lambda _day: {
            "schema": "EMS_PI_DAY_PERFORMANCE_V0.1",
            "surplusWindowsForReplay": [],
        }
        ai._ev_control_events = lambda _day: []
        ai._ev_telemetry = lambda _day: []
        ai._quooker_events = lambda _day: []
        ai._timeline = lambda _day: []
        ai._load_health = lambda: {
            "schema": "EMS_PI_HEALTH_V0.1",
            "status": "HEALTHY",
        }
        ai._planner_decision_window = lambda _day, _anchors: []
        ai._flex_context_window = lambda _day, _anchors: []
        ai._forecast_vs_actual_15m = lambda _day, _anchors: {
            "available": True,
            "summary": {},
            "slots": [],
        }
        ai._apply_model_input_budget = lambda evidence, *_args: evidence

        evidence = ai.build_evidence(
            date(2026, 10, 4),
            "Wat veranderde er rond 14:00 met de EV-deadline?",
        )
        assert len(evidence["semanticEvents"]) == 1
        assert evidence["semanticEvents"][0]["eventType"] == "EV_DEADLINE_SET"
        assert evidence["semanticEventCoverage"]["available"] is True
        assert "semanticEvents" in evidence["sourceAuthority"]
        assert "semanticEvents" in evidence["evidenceSelection"]["scopedFields"]

    instructions = ai.SYSTEM_INSTRUCTIONS
    assert "Use semanticEvents as durable historical state-change evidence" in instructions
    assert "USER_INTENT_COMMAND proves" in instructions
    assert "OBSERVED_STATE proves an observed state transition" in instructions
    assert "SHADOW_DECISION is never proof of a physical write" in instructions
    assert "initial baseline creates no synthetic event" in instructions

    print("PASS: AI semantic event evidence contract")


if __name__ == "__main__":
    main()

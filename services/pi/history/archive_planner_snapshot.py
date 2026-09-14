#!/usr/bin/env python3

"""Archive each hardened Pi planner run for retrospective EMS validation.

This is observability-only history. It must never block planner/control output.
The current hardened plan and the decision context that cannot be reconstructed
later are stored as a compressed snapshot in a local SQLite database.

Runtime target:
  /home/jeroen/ems/runtime/history/archive_planner_snapshot.py

Data target:
  /home/jeroen/ems/data/planner-history.sqlite
"""

import json
import sqlite3
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path("/home/jeroen/ems/data")
PLAN_FILE = DATA / "dynamic-shadow-plan.json"
STATE_FILE = DATA / "energy-state-v2.json"
WW_FILE = DATA / "ww-input.json"
DB_FILE = DATA / "planner-history.sqlite"
STATUS_FILE = DATA / "planner-history-status.json"
RETENTION_DAYS = 120


def load(path):
    return json.loads(path.read_text())


def utc_now():
    return datetime.now(timezone.utc)


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path, payload):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    tmp.replace(path)


def ensure_schema(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS planner_snapshots (
            id INTEGER PRIMARY KEY,
            generated_at_utc TEXT NOT NULL UNIQUE,
            captured_at_utc TEXT NOT NULL,
            plan_schema TEXT,
            valid_until_utc TEXT,
            state_revision INTEGER,
            source_sample_at_utc TEXT,
            tesla_connected INTEGER,
            tesla_deadline_active INTEGER,
            ww_goal_reached INTEGER,
            snapshot_zlib BLOB NOT NULL
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_planner_snapshots_generated "
        "ON planner_snapshots(generated_at_utc)"
    )


def compact_context(state, ww):
    meta = state.get("meta") or {}
    tesla = state.get("tesla") or {}
    grid = state.get("grid") or {}
    hot_water = state.get("hot_water") or {}
    warm_water = ww.get("warmWater") or {}

    return {
        "state": {
            "meta": {
                "state_revision": meta.get("state_revision"),
                "source_sample_at": meta.get("source_sample_at"),
                "heartbeat_at": meta.get("heartbeat_at"),
                "publisher_version": meta.get("publisher_version"),
            },
            "grid": {
                "power_w": grid.get("power_w"),
                "import_w": grid.get("import_w"),
                "export_w": grid.get("export_w"),
            },
            "tesla": {
                "connected": tesla.get("connected"),
                "charging": tesla.get("charging"),
                "power_w": tesla.get("power_w"),
                "soc_pct": tesla.get("soc_pct"),
                "deadline_active": tesla.get("deadline_active"),
                "deadline_at": tesla.get("deadline_at"),
                "latest_start_at": tesla.get("latest_start_at"),
                "remaining_kwh": tesla.get("remaining_kwh"),
                "deadline_max_a": tesla.get("deadline_max_a"),
            },
            "hot_water": {
                "boiler_power_w": hot_water.get("boiler_power_w"),
            },
        },
        "warmWater": warm_water,
    }


def archive():
    captured = utc_now()
    plan = load(PLAN_FILE)
    state = load(STATE_FILE)
    ww = load(WW_FILE)

    generated = plan.get("generated_at") or plan.get("generatedAt")
    if not generated:
        raise RuntimeError("planner snapshot missing generated_at")

    context = compact_context(state, ww)
    snapshot = {
        "schema": "EMS_PI_PLANNER_DECISION_SNAPSHOT_V0.1",
        "capturedAt": iso_z(captured),
        "objective": plan.get("objective"),
        "plan": plan,
        "context": context,
    }
    blob = zlib.compress(
        json.dumps(snapshot, separators=(",", ":")).encode("utf-8"),
        level=6,
    )

    meta = context["state"]["meta"]
    tesla = context["state"]["tesla"]
    warm_water = context["warmWater"]

    con = sqlite3.connect(DB_FILE, timeout=5)
    try:
        con.execute("PRAGMA busy_timeout=5000")
        ensure_schema(con)
        cur = con.execute(
            """
            INSERT OR IGNORE INTO planner_snapshots (
                generated_at_utc, captured_at_utc, plan_schema, valid_until_utc,
                state_revision, source_sample_at_utc, tesla_connected,
                tesla_deadline_active, ww_goal_reached, snapshot_zlib
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generated,
                iso_z(captured),
                plan.get("schema"),
                plan.get("validUntil"),
                meta.get("state_revision"),
                meta.get("source_sample_at"),
                1 if tesla.get("connected") is True else 0,
                1 if tesla.get("deadline_active") is True else 0,
                1 if (
                    warm_water.get("goalReachedToday") is True
                    or warm_water.get("goalReached") is True
                ) else 0,
                sqlite3.Binary(blob),
            ),
        )
        inserted = cur.rowcount == 1

        cutoff = iso_z(captured - timedelta(days=RETENTION_DAYS))
        con.execute(
            "DELETE FROM planner_snapshots WHERE generated_at_utc < ?",
            (cutoff,),
        )
        con.commit()

        row = con.execute(
            "SELECT COUNT(*), MIN(generated_at_utc), MAX(generated_at_utc) "
            "FROM planner_snapshots"
        ).fetchone()
    finally:
        con.close()

    status = {
        "schema": "EMS_PI_PLANNER_HISTORY_STATUS_V0.1",
        "updatedAt": iso_z(captured),
        "status": "OK",
        "inserted": inserted,
        "latestPlanGeneratedAt": generated,
        "stateRevision": meta.get("state_revision"),
        "sourceSampleAt": meta.get("source_sample_at"),
        "retentionDays": RETENTION_DAYS,
        "snapshotCount": row[0],
        "oldestSnapshot": row[1],
        "newestSnapshot": row[2],
    }
    atomic_json(STATUS_FILE, status)
    return status


def main():
    try:
        result = archive()
        print("PASS: planner decision snapshot archived")
        print("inserted           :", result["inserted"])
        print("latest plan        :", result["latestPlanGeneratedAt"])
        print("state revision     :", result["stateRevision"])
        print("snapshot count     :", result["snapshotCount"])
    except Exception as exc:
        # Historical observability must never take down the forecast/control chain.
        print(f"WARN: planner decision history archive failed: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

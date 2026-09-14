#!/usr/bin/env python3

"""Archive hardened Pi planner runs for retrospective EMS validation.

Observability only: archive failure must never block planner/control output.
The hardened plan itself is the atomic decision record. Context is therefore
extracted from fields embedded in that plan; this script deliberately does not
re-read mutable live Homey state after the planner has completed.

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


def planner_context(plan):
    """Return only context that is already frozen inside the planner output.

    Re-reading energy-state-v2.json or ww-input.json here would introduce a race:
    Homey can publish a newer state between plan generation and archive capture.
    For replay, a slightly smaller but internally consistent decision record is
    preferable to attaching a newer state that the planner never saw.
    """
    tesla = plan.get("tesla") or {}
    deadline = tesla.get("deadlinePlan") or plan.get("teslaDeadline") or {}
    realtime = plan.get("realtime") or {}
    daily = plan.get("dailyPlans") or []

    current_day = None
    for item in daily:
        if item.get("goalReached") is not None:
            current_day = item
            break

    return {
        "contextSource": "PLAN_EMBEDDED_DECISION_OUTPUT",
        "realtime": {
            "actualP1ExportW": realtime.get("actualP1ExportW"),
            "recentLocalAccuracy": realtime.get("recentLocalAccuracy"),
            "recentP1ExportSamples": realtime.get("recentP1ExportSamples"),
            "p1CorrectionPolicy": realtime.get("p1CorrectionPolicy"),
        },
        "tesla": {
            "connected": tesla.get("connectedNow"),
            "charging": tesla.get("chargingNow"),
            "availabilityPolicy": tesla.get("availabilityPolicy"),
            "deadline": deadline,
            "qualifiedWindows": tesla.get("qualifiedWindows"),
        },
        "warmWater": current_day,
        "guardrails": plan.get("guardrails"),
        "contract": plan.get("contract"),
        "inputFreshness": plan.get("inputFreshness"),
    }


def archive():
    captured = utc_now()
    plan = load(PLAN_FILE)

    generated = plan.get("generated_at") or plan.get("generatedAt")
    if not generated:
        raise RuntimeError("planner snapshot missing generated_at")

    context = planner_context(plan)
    tesla = context["tesla"]
    deadline = tesla.get("deadline") or {}
    warm_water = context.get("warmWater") or {}

    # The current plan schema does not yet embed Homey state_revision or
    # source_sample_at. Do not fabricate them by reading mutable live state here.
    # Exact measured actuals remain available in ems-history.sqlite and are joined
    # by time during retrospective replay.
    state_revision = None
    source_sample_at = None

    snapshot = {
        "schema": "EMS_PI_PLANNER_DECISION_SNAPSHOT_V0.2",
        "capturedAt": iso_z(captured),
        "objective": plan.get("objective"),
        "plan": plan,
        "context": context,
    }
    blob = zlib.compress(
        json.dumps(snapshot, separators=(",", ":")).encode("utf-8"),
        level=6,
    )

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
                state_revision,
                source_sample_at,
                1 if tesla.get("connected") is True else 0,
                1 if deadline.get("active") is True else 0,
                1 if warm_water.get("goalReached") is True else 0,
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
        "schema": "EMS_PI_PLANNER_HISTORY_STATUS_V0.2",
        "updatedAt": iso_z(captured),
        "status": "OK",
        "inserted": inserted,
        "latestPlanGeneratedAt": generated,
        "contextSource": context["contextSource"],
        "stateRevision": state_revision,
        "sourceSampleAt": source_sample_at,
        "actualP1ExportW": context["realtime"].get("actualP1ExportW"),
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
        print("context source     :", result["contextSource"])
        print("snapshot count     :", result["snapshotCount"])
    except Exception as exc:
        print(f"WARN: planner decision history archive failed: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

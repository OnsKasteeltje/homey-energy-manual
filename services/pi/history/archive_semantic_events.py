#!/usr/bin/env python3
"""Archive sparse semantic EMS events for retrospective AI analysis.

This observer is deliberately outside the realtime control path. It reads only
already-derived local Pi artifacts and converts *changes* in a bounded set of
high-value states into durable semantic events.

The first observation of each state key establishes a baseline and is never
invented as a historical event. No pre-commissioning events are backfilled.

No Homey calls, network calls, planner decisions, Logic writes or device writes
exist in this module.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DATA = Path("/home/jeroen/ems/data")
DB_FILE = DATA / "ems-history.sqlite"

ENERGY_STATE_FILE = DATA / "energy-state-v2.json"
EV_DEADLINE_COMMAND_FILE = DATA / "tesla-deadline-command.json"
EV_DEADLINE_STATE_FILE = DATA / "ev-deadline-shadow-state.json"
FLEX_PRIORITY_FILE = DATA / "flex-priority-shadow-v0.1.json"
HEATING_PROGRESSION_FILE = DATA / "heating-preheat-progression-shadow-v0.4.json"

SCHEMA = "EMS_PI_SEMANTIC_EVENT_ARCHIVE_V0.1"
RETENTION_DAYS = 730

FLEX_PRIORITY_SCHEMA = "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"
HEATING_PROGRESSION_SCHEMA = "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4"
EV_DEADLINE_STATE_SCHEMA = "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _mtime(path: Path) -> str | None:
    try:
        return _iso(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))
    except OSError:
        return None


def _source_at(payload: dict[str, Any], candidates: tuple[tuple[str, ...], ...], path: Path) -> str:
    for candidate in candidates:
        value: Any = payload
        for key in candidate:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        parsed = _parse_ts(value)
        if parsed is not None:
            return _iso(parsed)
    return _mtime(path) or _iso(_now())


def _observation(
    *,
    state_key: str,
    domain: str,
    subject: str,
    value: Any,
    source_name: str,
    source_at: str,
    provenance_class: str,
) -> dict[str, Any]:
    return {
        "stateKey": state_key,
        "domain": domain,
        "subject": subject,
        "value": value,
        "sourceName": source_name,
        "sourceAt": source_at,
        "provenanceClass": provenance_class,
    }


def build_observations(now: datetime | None = None) -> list[dict[str, Any]]:
    """Build the current semantic-state projection from local artifacts only."""
    now = now or _now()
    observations: list[dict[str, Any]] = []

    energy = _load(ENERGY_STATE_FILE)
    if energy is not None:
        at = _source_at(
            energy,
            (("meta", "source_sample_at"), ("meta", "generated_at")),
            ENERGY_STATE_FILE,
        )
        tesla = energy.get("tesla") if isinstance(energy.get("tesla"), dict) else {}
        hot_water = (
            energy.get("hot_water")
            if isinstance(energy.get("hot_water"), dict)
            else {}
        )

        if isinstance(tesla.get("connected"), bool):
            observations.append(_observation(
                state_key="ev.connected",
                domain="EV",
                subject="tesla",
                value=tesla["connected"],
                source_name="energy-state-v2.json",
                source_at=at,
                provenance_class="OBSERVED_STATE",
            ))
        if isinstance(tesla.get("charging"), bool):
            observations.append(_observation(
                state_key="ev.charging",
                domain="EV",
                subject="tesla",
                value=tesla["charging"],
                source_name="energy-state-v2.json",
                source_at=at,
                provenance_class="OBSERVED_STATE",
            ))
        raw_ww_mode = hot_water.get("mode")
        if raw_ww_mode is not None:
            if raw_ww_mode is True:
                ww_mode = "BOILER"
            elif raw_ww_mode is False:
                ww_mode = "CV"
            else:
                ww_mode = str(raw_ww_mode)
            observations.append(_observation(
                state_key="warm_water.source_mode",
                domain="WARM_WATER",
                subject="warm_water",
                value=ww_mode,
                source_name="energy-state-v2.json",
                source_at=at,
                provenance_class="OBSERVED_STATE",
            ))

    command = _load(EV_DEADLINE_COMMAND_FILE)
    if command is not None and command.get("requestId"):
        at = _source_at(
            command,
            (("updatedAt",), ("requestedAt",)),
            EV_DEADLINE_COMMAND_FILE,
        )
        value = {
            "requestId": command.get("requestId"),
            "active": command.get("active") is True,
            "deadline": command.get("deadline"),
            "currentSoc": command.get("currentSoc"),
            "targetSoc": command.get("targetSoc"),
            "goalKWh": command.get("goalKWh"),
            "maxA": command.get("maxA"),
            "requestedAt": command.get("requestedAt"),
        }
        observations.append(_observation(
            state_key="ev.deadline.command",
            domain="EV",
            subject="ev_deadline",
            value=value,
            source_name="tesla-deadline-command.json",
            source_at=at,
            provenance_class="USER_INTENT_COMMAND",
        ))

    deadline_state = _load(EV_DEADLINE_STATE_FILE)
    if (
        deadline_state is not None
        and deadline_state.get("schema") == EV_DEADLINE_STATE_SCHEMA
    ):
        at = _source_at(
            deadline_state,
            (("generatedAt",),),
            EV_DEADLINE_STATE_FILE,
        )
        value = {
            "requestId": deadline_state.get("requestId"),
            "active": deadline_state.get("active") is True,
            "status": deadline_state.get("status"),
            "remainingKWh": deadline_state.get("remainingKWh"),
            "deadlineAt": deadline_state.get("deadlineAt"),
        }
        observations.append(_observation(
            state_key="ev.deadline.status",
            domain="EV",
            subject="ev_deadline",
            value=value,
            source_name="ev-deadline-shadow-state.json",
            source_at=at,
            provenance_class="DERIVED_STATE",
        ))

    priority = _load(FLEX_PRIORITY_FILE)
    if (
        priority is not None
        and priority.get("schema") == FLEX_PRIORITY_SCHEMA
    ):
        decision = (
            priority.get("decision")
            if isinstance(priority.get("decision"), dict)
            else {}
        )
        if decision:
            at = _source_at(
                priority,
                (("generatedAt",),),
                FLEX_PRIORITY_FILE,
            )
            value = {
                "priorityOwner": decision.get("priorityOwner"),
                "heatingShadowGrant": decision.get("heatingShadowGrant"),
                "evRole": decision.get("evRole"),
                "reason": decision.get("reason"),
                "physicalWriteAllowed": decision.get("physicalWriteAllowed"),
            }
            observations.append(_observation(
                state_key="flex.priority",
                domain="FLEX",
                subject="cross_domain_priority",
                value=value,
                source_name="flex-priority-shadow-v0.1.json",
                source_at=at,
                provenance_class="SHADOW_DECISION",
            ))

    progression = _load(HEATING_PROGRESSION_FILE)
    if (
        progression is not None
        and progression.get("schema") == HEATING_PROGRESSION_SCHEMA
    ):
        at = _source_at(
            progression,
            (("generatedAt",),),
            HEATING_PROGRESSION_FILE,
        )
        for room in progression.get("rooms") or []:
            if not isinstance(room, dict):
                continue
            key = room.get("key")
            if not isinstance(key, str) or not key:
                continue
            eligibility = (
                room.get("heatingEligibility")
                if isinstance(room.get("heatingEligibility"), dict)
                else {}
            )
            planner = (
                room.get("planner")
                if isinstance(room.get("planner"), dict)
                else {}
            )
            step = (
                room.get("progression")
                if isinstance(room.get("progression"), dict)
                else {}
            )
            value = {
                "eligibilityState": eligibility.get("state"),
                "eligibilityReason": eligibility.get("reason"),
                "domainGrant": planner.get("domainGrant"),
                "priorityReason": planner.get("priorityReason"),
                "progressionState": step.get("state"),
                "progressionReason": step.get("reason"),
                "activeStepTargetC": step.get("activeStepTarget_C"),
                "activeStepReached": step.get("activeStepReached"),
                "physicalWritePerformed": step.get("physicalWritePerformed"),
            }
            observations.append(_observation(
                state_key=f"heating.room.{key}",
                domain="HEATING",
                subject=key,
                value=value,
                source_name="heating-preheat-progression-shadow-v0.4.json",
                source_at=at,
                provenance_class="SHADOW_DECISION",
            ))

    return sorted(observations, key=lambda item: item["stateKey"])


def _ensure_schema(con: sqlite3.Connection, now: datetime) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS semantic_event_meta (
            key TEXT PRIMARY KEY,
            value_text TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS semantic_event_state (
            state_key TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            subject TEXT NOT NULL,
            source_name TEXT NOT NULL,
            provenance_class TEXT NOT NULL,
            value_json TEXT NOT NULL,
            source_at_utc TEXT,
            first_observed_at_utc TEXT NOT NULL,
            last_observed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS semantic_events (
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
            details_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_semantic_events_time
        ON semantic_events(ts_utc);

        CREATE INDEX IF NOT EXISTS idx_semantic_events_domain_time
        ON semantic_events(domain, ts_utc);
        """
    )
    con.execute(
        """
        INSERT OR IGNORE INTO semantic_event_meta(key,value_text)
        VALUES ('commissioned_at_utc',?)
        """,
        (_iso(now),),
    )
    con.execute(
        """
        INSERT OR IGNORE INTO semantic_event_meta(key,value_text)
        VALUES ('schema',?)
        """,
        (SCHEMA,),
    )


def _event_type(state_key: str, before: Any, after: Any) -> str:
    if state_key == "ev.connected":
        return "EV_CONNECTED" if after is True else "EV_DISCONNECTED"
    if state_key == "ev.charging":
        return "EV_CHARGING_STARTED" if after is True else "EV_CHARGING_STOPPED"
    if state_key == "warm_water.source_mode":
        return "WW_SOURCE_CHANGED"

    if state_key == "ev.deadline.command":
        before = before if isinstance(before, dict) else {}
        after = after if isinstance(after, dict) else {}
        if before.get("active") is True and after.get("active") is not True:
            return "EV_DEADLINE_CANCELLED"
        if (
            after.get("active") is True
            and (
                before.get("active") is not True
                or before.get("requestId") != after.get("requestId")
            )
        ):
            return "EV_DEADLINE_SET"
        return "EV_DEADLINE_UPDATED"

    if state_key == "ev.deadline.status":
        after = after if isinstance(after, dict) else {}
        status = after.get("status")
        if status == "GOAL_COMPLETE":
            return "EV_DEADLINE_GOAL_COMPLETE"
        if status == "EXPIRED":
            return "EV_DEADLINE_EXPIRED"
        if status == "TRACKING":
            return "EV_DEADLINE_TRACKING"
        return "EV_DEADLINE_STATUS_CHANGED"

    if state_key == "flex.priority":
        return "FLEX_PRIORITY_CHANGED"
    if state_key.startswith("heating.room."):
        return "HEATING_SHADOW_STATE_CHANGED"
    return "SEMANTIC_STATE_CHANGED"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _normalize_previous_value(state_key: str, value: Any) -> Any:
    # Pre-normalization V0.1 commissioning could store WW_Boilermodus as a
    # boolean. Canonical contract semantics are false=CV / true=BOILER.
    # Normalize that already-observed baseline in place so a source-code
    # upgrade does not manufacture a WW_SOURCE_CHANGED event.
    if state_key == "warm_water.source_mode":
        if value is True:
            return "BOILER"
        if value is False:
            return "CV"
    return value


def archive(
    observations: list[dict[str, Any]] | None = None,
    *,
    db_path: Path = DB_FILE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Persist semantic state changes; first observations are baseline only."""
    now = now or _now()
    observed_at = _iso(now)
    observations = (
        build_observations(now)
        if observations is None
        else list(observations)
    )

    con = sqlite3.connect(str(db_path), timeout=5.0)
    con.execute("PRAGMA busy_timeout=5000")
    try:
        _ensure_schema(con, now)

        baselines = 0
        inserted = 0
        unchanged = 0
        stale_skipped = 0
        event_types: list[str] = []

        for observation in observations:
            state_key = observation["stateKey"]
            value_json = _canonical(observation.get("value"))
            source_at = observation.get("sourceAt")
            incoming_source = _parse_ts(source_at)

            previous = con.execute(
                """
                SELECT domain,subject,source_name,provenance_class,
                       value_json,source_at_utc,first_observed_at_utc
                FROM semantic_event_state
                WHERE state_key=?
                """,
                (state_key,),
            ).fetchone()

            if previous is None:
                con.execute(
                    """
                    INSERT INTO semantic_event_state(
                        state_key,domain,subject,source_name,provenance_class,
                        value_json,source_at_utc,
                        first_observed_at_utc,last_observed_at_utc
                    )
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        state_key,
                        observation["domain"],
                        observation["subject"],
                        observation["sourceName"],
                        observation["provenanceClass"],
                        value_json,
                        source_at,
                        observed_at,
                        observed_at,
                    ),
                )
                baselines += 1
                continue

            (
                _previous_domain,
                _previous_subject,
                _previous_source_name,
                _previous_provenance,
                previous_json,
                previous_source_at,
                first_observed_at,
            ) = previous

            previous_source = _parse_ts(previous_source_at)
            if (
                incoming_source is not None
                and previous_source is not None
                and incoming_source < previous_source
            ):
                stale_skipped += 1
                continue

            try:
                before = json.loads(previous_json)
            except json.JSONDecodeError:
                before = None
            before = _normalize_previous_value(state_key, before)
            normalized_previous_json = _canonical(before)

            if normalized_previous_json == value_json:
                con.execute(
                    """
                    UPDATE semantic_event_state
                    SET value_json=?,source_at_utc=?,last_observed_at_utc=?
                    WHERE state_key=?
                    """,
                    (value_json, source_at, observed_at, state_key),
                )
                unchanged += 1
                continue

            after = observation.get("value")
            event_type = _event_type(state_key, before, after)
            event_at = source_at if _parse_ts(source_at) is not None else observed_at
            details = {
                "schema": SCHEMA,
                "historicalBackfill": False,
                "firstObservedAt": first_observed_at,
                "baselineWasObserved": True,
            }
            hash_payload = _canonical({
                "stateKey": state_key,
                "eventType": event_type,
                "before": before,
                "after": after,
                "eventAt": event_at,
            })
            event_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

            cur = con.execute(
                """
                INSERT OR IGNORE INTO semantic_events(
                    event_hash,ts_utc,event_type,domain,subject,state_key,
                    provenance_class,source_name,source_at_utc,observed_at_utc,
                    before_json,after_json,details_json
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event_hash,
                    event_at,
                    event_type,
                    observation["domain"],
                    observation["subject"],
                    state_key,
                    observation["provenanceClass"],
                    observation["sourceName"],
                    source_at,
                    observed_at,
                    previous_json,
                    value_json,
                    _canonical(details),
                ),
            )
            inserted += cur.rowcount
            if cur.rowcount:
                event_types.append(event_type)

            con.execute(
                """
                UPDATE semantic_event_state
                SET domain=?,subject=?,source_name=?,provenance_class=?,
                    value_json=?,source_at_utc=?,last_observed_at_utc=?
                WHERE state_key=?
                """,
                (
                    observation["domain"],
                    observation["subject"],
                    observation["sourceName"],
                    observation["provenanceClass"],
                    value_json,
                    source_at,
                    observed_at,
                    state_key,
                ),
            )

        cutoff = _iso(now - timedelta(days=RETENTION_DAYS))
        con.execute(
            "DELETE FROM semantic_events WHERE ts_utc < ?",
            (cutoff,),
        )

        commissioned = con.execute(
            """
            SELECT value_text
            FROM semantic_event_meta
            WHERE key='commissioned_at_utc'
            """
        ).fetchone()[0]
        state_count = con.execute(
            "SELECT COUNT(*) FROM semantic_event_state"
        ).fetchone()[0]
        event_count = con.execute(
            "SELECT COUNT(*) FROM semantic_events"
        ).fetchone()[0]
        con.commit()
    finally:
        con.close()

    return {
        "schema": SCHEMA,
        "readOnly": True,
        "controlWrites": False,
        "historicalBackfill": False,
        "commissionedAt": commissioned,
        "retentionDays": RETENTION_DAYS,
        "observationCount": len(observations),
        "baselineCount": baselines,
        "insertedEventCount": inserted,
        "unchangedCount": unchanged,
        "staleSkippedCount": stale_skipped,
        "stateCount": state_count,
        "eventCount": event_count,
        "insertedEventTypes": event_types,
    }


def main() -> int:
    result = archive()
    print("PASS: semantic event archive")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

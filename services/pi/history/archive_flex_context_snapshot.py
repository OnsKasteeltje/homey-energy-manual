#!/usr/bin/env python3
"""Archive read-only flex context for retrospective EMS analysis.

The archive is observability-only. It reads already-derived Pi artifacts for
Heating Preheat, cross-domain flex priority, Heating progression, WW input and
WW seasonal advice, and stores a compact semantic snapshot in planner-history.

It performs no Homey calls, no network calls, no planner decisions and no
physical/control writes.
"""

import hashlib
import json
import sqlite3
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path("/home/jeroen/ems/data")
DB_FILE = DATA / "planner-history.sqlite"

HEATING_FILE = DATA / "heating-preheat-shadow-v0.3.json"
PRIORITY_FILE = DATA / "flex-priority-shadow-v0.1.json"
PROGRESSION_FILE = DATA / "heating-preheat-progression-shadow-v0.4.json"
WW_INPUT_FILE = DATA / "ww-input.json"
WW_SEASONAL_FILE = DATA / "ww-seasonal-advisor.json"
ENERGY_STATE_FILE = DATA / "energy-state-v2.json"

SCHEMA = "EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1"
RETENTION_DAYS = 120
HEARTBEAT_MINUTES = 15

HEATING_SCHEMA = "EMS_HEATING_PREHEAT_SHADOW_V0.3"
PRIORITY_SCHEMA = "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1"
PROGRESSION_SCHEMA = "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4"
WW_INPUT_SCHEMA = "EMS_PI_WW_INPUT_V0.1"
WW_SEASONAL_SCHEMA = "EMS_WW_SEASONAL_SOURCE_V0.4_PI"


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _load(path, *, required=True):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        if required:
            raise RuntimeError(f"required flex-context source unavailable: {path}")
        return None


def _validate_shadow(payload, schema, label):
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise RuntimeError(f"{label} schema invalid")
    if payload.get("mode") != "READ_ONLY" or payload.get("controlMode") != "SHADOW":
        raise RuntimeError(f"{label} must remain READ_ONLY/SHADOW")
    if payload.get("controlWrites") is not False:
        raise RuntimeError(f"{label} controlWrites boundary invalid")
    if _parse_ts(payload.get("generatedAt")) is None:
        raise RuntimeError(f"{label} generatedAt invalid")


def _project_heating(payload):
    rooms = []
    for room in payload.get("rooms") or []:
        if not isinstance(room, dict):
            continue
        rooms.append({
            "key": room.get("key"),
            "displayName": room.get("displayName"),
            "preheatScope": room.get("preheatScope"),
            "group": room.get("group"),
            "current": room.get("current"),
            "baseline": room.get("baseline"),
            "candidate": room.get("candidate"),
            "shadow": room.get("shadow"),
        })
    return {
        "generatedAt": payload.get("generatedAt"),
        "baselineAuthority": payload.get("baselineAuthority"),
        "house": payload.get("house"),
        "cvGuard": payload.get("cvGuard"),
        "rooms": rooms,
    }


def _project_priority(payload):
    return {
        "generatedAt": payload.get("generatedAt"),
        "authority": payload.get("authority"),
        "heating": payload.get("heating"),
        "ev": payload.get("ev"),
        "decision": payload.get("decision"),
    }


def _project_progression(payload):
    rooms = []
    for room in payload.get("rooms") or []:
        if not isinstance(room, dict):
            continue
        rooms.append({
            "key": room.get("key"),
            "displayName": room.get("displayName"),
            "preheatScope": room.get("preheatScope"),
            "group": room.get("group"),
            "opportunityId": room.get("opportunityId"),
            "currentTemperature_C": room.get("currentTemperature_C"),
            "futureHoneywellTarget_C": room.get("futureHoneywellTarget_C"),
            "opportunityClosesAt": room.get("opportunityClosesAt"),
            "heatingEligibility": room.get("heatingEligibility"),
            "planner": room.get("planner"),
            "progression": room.get("progression"),
        })
    return {
        "generatedAt": payload.get("generatedAt"),
        "physicalWriteAllowed": payload.get("physicalWriteAllowed"),
        "baselineAuthority": payload.get("baselineAuthority"),
        "sourceFreshness": payload.get("sourceFreshness"),
        "rooms": rooms,
    }


def _project_ww_input(payload, path):
    if not isinstance(payload, dict) or payload.get("schema") != WW_INPUT_SCHEMA:
        return None
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        mtime = None
    return {
        "fileMtimeAt": _iso(mtime) if mtime else None,
        "mode": payload.get("mode"),
        "controlWrites": payload.get("control_writes"),
        "source": payload.get("source"),
        "warmWater": payload.get("warmWater"),
    }


def _project_ww_seasonal(payload):
    if not isinstance(payload, dict) or payload.get("schema") != WW_SEASONAL_SCHEMA:
        return None
    return {
        "generatedAt": payload.get("generatedAt"),
        "status": payload.get("status"),
        "currentMode": payload.get("currentMode"),
        "advice": payload.get("advice"),
        "candidate": payload.get("candidate"),
        "reason": payload.get("reason"),
        "confirmation": payload.get("confirmation"),
        "analysis": payload.get("analysis"),
        "manualSwitchOnly": payload.get("manualSwitchOnly"),
    }


def _project_energy_state(payload):
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    hot_water = payload.get("hot_water") if isinstance(payload.get("hot_water"), dict) else {}
    return {
        "sourceSampleAt": meta.get("source_sample_at"),
        "generatedAt": meta.get("generated_at"),
        "hotWater": {
            "mode": hot_water.get("mode"),
            "boilerOn": hot_water.get("boiler_on"),
            "boilerPowerW": hot_water.get("boiler_power_w"),
        },
    }


def build_snapshot(now=None):
    now = now or _now()
    heating = _load(HEATING_FILE)
    priority = _load(PRIORITY_FILE)
    progression = _load(PROGRESSION_FILE)

    _validate_shadow(heating, HEATING_SCHEMA, "heating")
    _validate_shadow(priority, PRIORITY_SCHEMA, "priority")
    _validate_shadow(progression, PROGRESSION_SCHEMA, "progression")

    ww_input = _load(WW_INPUT_FILE, required=False)
    ww_seasonal = _load(WW_SEASONAL_FILE, required=False)
    energy_state = _load(ENERGY_STATE_FILE, required=False)

    return {
        "schema": SCHEMA,
        "capturedAt": _iso(now),
        "readOnly": True,
        "controlWrites": False,
        "historicalBackfill": False,
        "heating": _project_heating(heating),
        "priority": _project_priority(priority),
        "progression": _project_progression(progression),
        "warmWaterInput": _project_ww_input(ww_input, WW_INPUT_FILE),
        "warmWaterSeasonal": _project_ww_seasonal(ww_seasonal),
        "energyState": _project_energy_state(energy_state),
    }


def _semantic_payload(snapshot):
    # Source timestamps prove freshness but should not create one row per minute
    # when the actual decision/eligibility state is unchanged.
    clone = json.loads(json.dumps(snapshot))
    clone.pop("capturedAt", None)

    for section in ("heating", "priority", "progression", "warmWaterSeasonal"):
        value = clone.get(section)
        if isinstance(value, dict):
            value.pop("generatedAt", None)
    ww = clone.get("warmWaterInput")
    if isinstance(ww, dict):
        ww.pop("fileMtimeAt", None)
    energy = clone.get("energyState")
    if isinstance(energy, dict):
        energy.pop("sourceSampleAt", None)
        energy.pop("generatedAt", None)

    progression = clone.get("progression")
    if isinstance(progression, dict):
        freshness = progression.get("sourceFreshness")
        if isinstance(freshness, dict):
            for source in freshness.values():
                if isinstance(source, dict):
                    source.pop("ageSeconds", None)
    return clone


def _ensure_schema(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS flex_context_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at_utc TEXT NOT NULL UNIQUE,
            semantic_hash TEXT NOT NULL,
            snapshot_zlib BLOB NOT NULL,
            created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_flex_context_snapshots_time
        ON flex_context_snapshots(captured_at_utc)
        """
    )


def archive(snapshot=None, db_path=DB_FILE, now=None):
    now = now or _now()
    snapshot = snapshot or build_snapshot(now)
    semantic = json.dumps(
        _semantic_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    semantic_hash = hashlib.sha256(semantic.encode("utf-8")).hexdigest()
    blob = zlib.compress(
        json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        level=6,
    )

    con = sqlite3.connect(str(db_path), timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    try:
        _ensure_schema(con)
        latest = con.execute(
            """
            SELECT captured_at_utc,semantic_hash
            FROM flex_context_snapshots
            ORDER BY captured_at_utc DESC
            LIMIT 1
            """
        ).fetchone()

        inserted = True
        dedupe = None
        if latest:
            latest_at = _parse_ts(latest[0])
            age_minutes = (
                (now - latest_at).total_seconds() / 60.0
                if latest_at is not None else HEARTBEAT_MINUTES
            )
            if latest[1] == semantic_hash and age_minutes < HEARTBEAT_MINUTES:
                inserted = False
                dedupe = "UNCHANGED_WITHIN_HEARTBEAT"

        if inserted:
            con.execute(
                """
                INSERT OR IGNORE INTO flex_context_snapshots
                (captured_at_utc,semantic_hash,snapshot_zlib)
                VALUES (?,?,?)
                """,
                (_iso(now), semantic_hash, sqlite3.Binary(blob)),
            )

        cutoff = _iso(now - timedelta(days=RETENTION_DAYS))
        con.execute(
            "DELETE FROM flex_context_snapshots WHERE captured_at_utc < ?",
            (cutoff,),
        )
        con.commit()

        count, oldest, newest = con.execute(
            """
            SELECT COUNT(*),MIN(captured_at_utc),MAX(captured_at_utc)
            FROM flex_context_snapshots
            """
        ).fetchone()
    finally:
        con.close()

    return {
        "schema": SCHEMA,
        "capturedAt": snapshot.get("capturedAt"),
        "inserted": inserted,
        "dedupe": dedupe,
        "semanticHash": semantic_hash,
        "retentionDays": RETENTION_DAYS,
        "snapshotCount": count,
        "oldestSnapshot": oldest,
        "newestSnapshot": newest,
    }


def main():
    result = archive()
    print("PASS: flex context snapshot archive")
    print("inserted      :", result["inserted"])
    print("dedupe        :", result["dedupe"])
    print("capturedAt    :", result["capturedAt"])
    print("snapshot count:", result["snapshotCount"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

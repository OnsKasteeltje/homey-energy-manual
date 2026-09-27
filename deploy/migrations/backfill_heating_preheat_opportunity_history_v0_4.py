#!/usr/bin/env python3
"""One-time/idempotent backfill for Heating Preheat V0.4 opportunity history.

The normal V0.4 minute loop persists opportunity windows prospectively. This
migration seeds the bounded historical window at first deployment from the
canonical Honeywell weekly schedule so an already-passed UP transition remains
visible immediately in Frontend V2.

It only rewrites the local READ_ONLY/SHADOW V0.4 derived artifact. It performs
no Honeywell, Homey, Quatt or other physical/control write.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HONEYWELL_SCHEDULE = Path(
    "/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-schedule.json"
)
PROGRESSION = Path(
    "/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json"
)

SCHEDULE_SCHEMA = "EMS_HONEYWELL_SCHEDULE_V0.2"
PROGRESSION_SCHEMA = "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4"
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
MAX_ADVANCE = timedelta(hours=3)
RETENTION = timedelta(hours=48)
MAX_ITEMS = 64


class BackfillError(ValueError):
    pass


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BackfillError(f"{label} missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackfillError(f"{label} invalid timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise BackfillError(f"{label} must be offset-aware")
    return dt


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BackfillError(f"{label} must be numeric")
    return float(value)


def _clock(value: Any) -> time:
    if not isinstance(value, str) or not value:
        raise BackfillError("switchpoint time_of_day missing")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise BackfillError("switchpoint time_of_day invalid") from exc


def _weekday_name(day: date) -> str:
    return day.strftime("%A").lower()


def _zone_map(schedule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if schedule.get("schema") != SCHEDULE_SCHEMA or schedule.get("mode") != "READ_ONLY":
        raise BackfillError("canonical Honeywell schedule source invalid")
    zones = schedule.get("zones")
    if not isinstance(zones, list):
        raise BackfillError("Honeywell zones missing")
    out: dict[str, dict[str, Any]] = {}
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        key = zone.get("key")
        if isinstance(key, str) and key:
            out[key] = zone
    return out


def _events(zone: dict[str, Any], start_day: date, end_day: date) -> list[tuple[datetime, float]]:
    weekly = zone.get("weeklySchedule")
    if zone.get("scheduleStatus") != "OK" or not isinstance(weekly, list):
        raise BackfillError(f"Honeywell weekly schedule unavailable for {zone.get('key')}")

    by_day: dict[str, list[dict[str, Any]]] = {}
    for item in weekly:
        if not isinstance(item, dict):
            continue
        name = str(item.get("day_of_week") or "").lower()
        points = item.get("switchpoints")
        if name and isinstance(points, list):
            by_day[name] = points

    out: list[tuple[datetime, float]] = []
    day = start_day
    while day <= end_day:
        points = by_day.get(_weekday_name(day))
        if points is None:
            raise BackfillError(f"weekday missing in Honeywell schedule: {_weekday_name(day)}")
        for point in points:
            if not isinstance(point, dict):
                raise BackfillError("Honeywell switchpoint invalid")
            local_at = datetime.combine(day, _clock(point.get("time_of_day")), tzinfo=LOCAL_TZ)
            target = _number(point.get("heat_setpoint"), "switchpoint heat_setpoint")
            out.append((local_at, target))
        day += timedelta(days=1)

    out.sort(key=lambda item: item[0])
    return out


def _normalize_existing(values: Any, cutoff: datetime) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    out: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        opportunity_id = item.get("opportunityId")
        target = item.get("target_C")
        try:
            opens = _aware(item.get("opensAt"), "opportunity opensAt")
            closes = _aware(item.get("closesAt"), "opportunity closesAt")
            target_n = _number(target, "opportunity target_C")
        except BackfillError:
            continue
        if not isinstance(opportunity_id, str) or not opportunity_id:
            continue
        if closes < opens or closes.astimezone(timezone.utc) < cutoff:
            continue
        out.append({
            "opportunityId": opportunity_id,
            "opensAt": opens.isoformat(),
            "closesAt": closes.isoformat(),
            "target_C": target_n,
        })
    return out


def backfill(
    schedule: dict[str, Any],
    progression: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int]:
    if progression.get("schema") != PROGRESSION_SCHEMA:
        raise BackfillError("V0.4 progression source invalid")
    if progression.get("mode") != "READ_ONLY" or progression.get("controlMode") != "SHADOW":
        raise BackfillError("V0.4 progression must be READ_ONLY / SHADOW")
    if progression.get("controlWrites") is not False or progression.get("physicalWriteAllowed") is not False:
        raise BackfillError("V0.4 progression write boundary invalid")
    if progression.get("baselineAuthority") != "HONEYWELL":
        raise BackfillError("Honeywell baseline authority required")
    policy = progression.get("policy")
    if not isinstance(policy, dict) or policy.get("opportunityHistoryRetentionHours") != 48:
        raise BackfillError("opportunity-history policy missing")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise BackfillError("now must be offset-aware")
    current = current.astimezone(timezone.utc)
    cutoff = current - RETENTION
    local_now = current.astimezone(LOCAL_TZ)
    start_day = cutoff.astimezone(LOCAL_TZ).date() - timedelta(days=8)
    end_day = local_now.date()

    zones = _zone_map(schedule)
    output = copy.deepcopy(progression)
    added = 0

    rooms = output.get("rooms")
    if not isinstance(rooms, list):
        raise BackfillError("V0.4 rooms missing")

    for room in rooms:
        if not isinstance(room, dict) or room.get("preheatScope") is not True:
            continue
        key = room.get("key")
        zone = zones.get(key)
        if not isinstance(key, str) or zone is None:
            raise BackfillError(f"Honeywell schedule zone missing for {key}")

        history = _normalize_existing(room.get("opportunityHistory"), cutoff)
        known = {
            (
                round(_aware(item["closesAt"], "existing closesAt").timestamp()),
                round(float(item["target_C"]), 3),
            )
            for item in history
        }

        previous_target: float | None = None
        for change_at, target in _events(zone, start_day, end_day):
            change_utc = change_at.astimezone(timezone.utc)
            if previous_target is not None and target > previous_target + 1e-9:
                if cutoff <= change_utc <= current:
                    identity = (round(change_at.timestamp()), round(target, 3))
                    if identity not in known:
                        closes = change_at.isoformat()
                        history.append({
                            "opportunityId": f"{key}|{closes}|{target:.3f}",
                            "opensAt": (change_at - MAX_ADVANCE).isoformat(),
                            "closesAt": closes,
                            "target_C": target,
                        })
                        known.add(identity)
                        added += 1
            previous_target = target

        history.sort(key=lambda item: _aware(item["opensAt"], "history opensAt"))
        room["opportunityHistory"] = history[-MAX_ITEMS:]

    return output, added


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        mode = path.stat().st_mode & 0o777
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main() -> int:
    output, added = backfill(_load(HONEYWELL_SCHEDULE), _load(PROGRESSION))
    _atomic_write(PROGRESSION, output)
    print(
        "PASS: backfilled Heating Preheat V0.4 opportunityHistory "
        f"from canonical Honeywell schedule; added={added}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

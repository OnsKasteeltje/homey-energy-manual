#!/usr/bin/env python3
"""
Build read-only thermal-learning episodes from canonical 15-minute history.

The output is evidence for future heating optimisation only.
It never writes Honeywell/Homey/Quatt and never creates a control command.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA = "EMS_HEATING_THERMAL_LEARNING_EPISODES_V0.1"
HOME_TZ_NAME = "Europe/Amsterdam"
HOME_TZ = ZoneInfo(HOME_TZ_NAME)

SCOPED_ROOMS = {"woonkamer", "eetkamer", "keuken", "serre"}
ROOM_GROUPS = {"living_area": ["woonkamer", "eetkamer"]}

PRE_WINDOW = timedelta(hours=3)
POST_WINDOW = timedelta(hours=3)


class EpisodeError(ValueError):
    pass


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise EpisodeError(f"timestamp must be offset-aware: {ts}")
    return dt


def _metric_id(con: sqlite3.Connection, metric_key: str) -> int | None:
    row = con.execute(
        "SELECT id FROM metrics WHERE metric_key=?",
        (metric_key,),
    ).fetchone()
    return int(row[0]) if row else None


def _device_id(con: sqlite3.Connection, device_key: str) -> int | None:
    row = con.execute(
        "SELECT id FROM devices WHERE device_key=?",
        (device_key,),
    ).fetchone()
    return int(row[0]) if row else None


def _series(
    con: sqlite3.Connection,
    device_key: str,
    metric_key: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    did = _device_id(con, device_key)
    mid = _metric_id(con, metric_key)
    if did is None or mid is None:
        return []

    rows = con.execute(
        """
        SELECT slot_start_utc, value_avg, value_min, value_max,
               sample_count, energy_wh, quality
        FROM measurements_15m
        WHERE device_id=?
          AND metric_id=?
          AND slot_start_utc>=?
          AND slot_start_utc<=?
        ORDER BY slot_start_utc
        """,
        (did, mid, _iso(start), _iso(end)),
    ).fetchall()

    return [
        {
            "slotStart": row[0],
            "avg": row[1],
            "min": row[2],
            "max": row[3],
            "sampleCount": row[4],
            "energyWh": row[5],
            "quality": row[6],
        }
        for row in rows
    ]


def _counter_delta(series: list[dict[str, Any]]) -> float | None:
    vals = [x["avg"] for x in series if x["avg"] is not None]
    if len(vals) < 2:
        return None
    delta = float(vals[-1]) - float(vals[0])
    if delta < -1e-9:
        return None
    return round(delta, 6)


def _energy_sum(series: list[dict[str, Any]]) -> float | None:
    vals = [x["energyWh"] for x in series if x["energyWh"] is not None]
    if not vals:
        return None
    return round(sum(float(v) for v in vals), 3)


def _room_key(device_key: str) -> str | None:
    prefix = "honeywell_"
    if not device_key.startswith(prefix):
        return None
    key = device_key[len(prefix):]
    return key if key in SCOPED_ROOMS else None


def _group_for(room: str) -> str | None:
    return next(
        (name for name, members in ROOM_GROUPS.items() if room in members),
        None,
    )


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _scheduled_up_transitions(
    schedule: dict[str, Any],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Resolve planned Honeywell UP transitions from the weekly schedule.

    Honeywell weeklySchedule is the baseline authority. Historical
    room_setpoint_c remains episode evidence only and must not create
    baseline transitions.
    """
    if schedule.get("schema") != "EMS_HONEYWELL_SCHEDULE_V0.2":
        raise EpisodeError(
            f"unexpected Honeywell schedule schema: {schedule.get('schema')}"
        )

    zones = schedule.get("zones")
    if not isinstance(zones, list):
        raise EpisodeError("Honeywell schedule zones must be an array")

    if start is None or end is None:
        raise EpisodeError(
            "start and end are required for weekly schedule episode resolution"
        )

    start_local = start.astimezone(HOME_TZ)
    end_local = end.astimezone(HOME_TZ)

    # Include the previous day so the baseline before the first switchpoint
    # in the requested window can be resolved across midnight/week boundary.
    first_date = start_local.date() - timedelta(days=1)
    last_date = end_local.date()

    transitions: list[dict[str, Any]] = []

    for zone in zones:
        room = zone.get("key")
        if room not in SCOPED_ROOMS:
            continue

        if zone.get("scheduleStatus") != "OK":
            raise EpisodeError(
                f"Honeywell schedule not OK for {room}: "
                f"{zone.get('scheduleStatus')}"
            )

        weekly = zone.get("weeklySchedule")
        if not isinstance(weekly, list) or not weekly:
            raise EpisodeError(
                f"{room}.weeklySchedule must be a non-empty array"
            )

        by_weekday: dict[int, list[tuple[str, float]]] = {}

        for day in weekly:
            if not isinstance(day, dict):
                raise EpisodeError(
                    f"{room}.weeklySchedule day must be an object"
                )

            day_name = day.get("day_of_week")
            if day_name not in _WEEKDAYS:
                raise EpisodeError(
                    f"{room}.weeklySchedule invalid day_of_week: {day_name}"
                )

            switchpoints = day.get("switchpoints")
            if not isinstance(switchpoints, list):
                raise EpisodeError(
                    f"{room}.{day_name}.switchpoints must be an array"
                )

            parsed: list[tuple[str, float]] = []

            for index, sp in enumerate(switchpoints):
                if not isinstance(sp, dict):
                    raise EpisodeError(
                        f"{room}.{day_name}.switchpoints[{index}] "
                        "must be an object"
                    )

                tod = sp.get("time_of_day")
                target = sp.get("heat_setpoint")

                if not isinstance(tod, str):
                    raise EpisodeError(
                        f"{room}.{day_name}.switchpoints[{index}] "
                        "time_of_day missing"
                    )

                try:
                    datetime.strptime(tod, "%H:%M:%S")
                except ValueError as exc:
                    raise EpisodeError(
                        f"{room}.{day_name} invalid time_of_day: {tod}"
                    ) from exc

                if isinstance(target, bool) or not isinstance(
                    target, (int, float)
                ):
                    raise EpisodeError(
                        f"{room}.{day_name}.switchpoints[{index}] "
                        "heat_setpoint must be numeric"
                    )

                parsed.append((tod, float(target)))

            parsed.sort(key=lambda item: item[0])
            by_weekday[_WEEKDAYS[day_name]] = parsed

        # Build an absolute local-time sequence from one day before the
        # requested window through its end.
        points: list[tuple[datetime, float]] = []

        day = first_date
        while day <= last_date:
            weekday = day.weekday()

            for tod, target in by_weekday.get(weekday, []):
                local_time = datetime.strptime(tod, "%H:%M:%S").time()
                points.append(
                    (
                        datetime.combine(day, local_time, tzinfo=HOME_TZ),
                        target,
                    )
                )

            day += timedelta(days=1)

        points.sort(key=lambda item: item[0])

        previous_target: float | None = None

        # If the first generated day has no switchpoint before the requested
        # range, resolve the preceding weekly target explicitly.
        search_date = first_date - timedelta(days=1)

        for _ in range(7):
            prior = by_weekday.get(search_date.weekday(), [])
            if prior:
                previous_target = prior[-1][1]
                break
            search_date -= timedelta(days=1)

        for change_at, target in points:
            before = previous_target
            previous_target = target

            if before is None:
                continue

            if change_at < start_local or change_at > end_local:
                continue

            # Thermal-learning episodes are anchored only on planned
            # increases in the Honeywell baseline.
            if target <= before + 1e-9:
                continue

            transitions.append(
                {
                    "room": room,
                    "deviceKey": f"honeywell_{room}",
                    "changeSlot": _iso(change_at),
                    "baselineBefore_C": round(before, 3),
                    "baselineAfter_C": round(target, 3),
                    "quality": "scheduled",
                }
            )

    transitions.sort(
        key=lambda item: (item["changeSlot"], item["room"])
    )
    return transitions


def _load_honeywell_schedule(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise EpisodeError(f"Honeywell schedule not found: {path}")

    data = json.loads(path.read_text())

    if not isinstance(data, dict):
        raise EpisodeError("Honeywell schedule root must be an object")

    return data


def build_episodes(
    con: sqlite3.Connection,
    *,
    schedule: dict[str, Any],
    start: datetime | None = None,
    end: datetime | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise EpisodeError("generated_at must be offset-aware")

    episodes: list[dict[str, Any]] = []

    for change in _scheduled_up_transitions(
        schedule,
        start=start,
        end=end,
    ):
        t0 = _parse(change["changeSlot"])
        window_start = t0 - PRE_WINDOW
        window_end = t0 + POST_WINDOW

        room = change["room"]
        honeywell_device = change["deviceKey"]

        room_temp = _series(
            con, honeywell_device, "room_temperature_c",
            window_start, window_end,
        )
        room_setpoint = _series(
            con, honeywell_device, "room_setpoint_c",
            window_start, window_end,
        )

        grid_import = _series(
            con, "grid_p1", "energy_import_kwh",
            window_start, window_end,
        )
        grid_export = _series(
            con, "grid_p1", "energy_export_kwh",
            window_start, window_end,
        )

        pv_series = {
            device: _series(
                con, device, "electrical_power_w",
                window_start, window_end,
            )
            for device in ("pv_solaredge", "pv_goodwe4200", "pv_goodwe2000")
        }

        quatt_electrical = _series(
            con, "quatt_cic", "electrical_power_w",
            window_start, window_end,
        )
        outside_temp = _series(
            con, "quatt_cic", "outside_temperature_c",
            window_start, window_end,
        )
        heating_on = _series(
            con, "quatt_cic", "heating_on",
            window_start, window_end,
        )

        pv_wh = sum(
            value or 0.0
            for value in (_energy_sum(series) for series in pv_series.values())
        )

        complete_room_slots = sum(
            1 for x in room_temp if x["quality"] == "complete"
        )

        episodes.append(
            {
                "room": room,
                "group": _group_for(room),
                "transition": {
                    "changeAt": change["changeSlot"],
                    "baselineBefore_C": change["baselineBefore_C"],
                    "baselineAfter_C": change["baselineAfter_C"],
                    "direction": "UP",
                    "sourceQuality": change["quality"],
                },
                "window": {
                    "start": _iso(window_start),
                    "end": _iso(window_end),
                    "preMinutes": int(PRE_WINDOW.total_seconds() / 60),
                    "postMinutes": int(POST_WINDOW.total_seconds() / 60),
                },
                "evidence": {
                    "roomTemperature": room_temp,
                    "roomSetpoint": room_setpoint,
                    "grid": {
                        "importDelta_kWh": _counter_delta(grid_import),
                        "exportDelta_kWh": _counter_delta(grid_export),
                    },
                    "pv": {
                        "productionEnergy_Wh": round(pv_wh, 3),
                        "devices": pv_series,
                    },
                    "quatt": {
                        "electricalPower": quatt_electrical,
                        "outsideTemperature": outside_temp,
                        "heatingOn": heating_on,
                    },
                },
                "quality": {
                    "roomTemperatureCompleteSlots": complete_room_slots,
                    "hasGridImportCounter": len(grid_import) >= 2,
                    "hasGridExportCounter": len(grid_export) >= 2,
                    "hasPvEvidence": any(bool(v) for v in pv_series.values()),
                    "hasQuattEvidence": bool(
                        quatt_electrical or outside_temp or heating_on
                    ),
                },
                "assessment": {
                    "status": "UNASSESSED",
                    "reason": "RAW_EPISODE_EVIDENCE_ONLY",
                    "usefulThermalBuffering": None,
                    "avoidedLaterHeating": None,
                    "incrementalGridImport_kWh": None,
                },
            }
        )

    return {
        "schema": SCHEMA,
        "mode": "READ_ONLY",
        "controlMode": "SHADOW",
        "generatedAt": _iso(now),
        "timezone": HOME_TZ_NAME,
        "baselineAuthority": "HONEYWELL",
        "policy": {
            "scopedRooms": sorted(SCOPED_ROOMS),
            "roomGroups": ROOM_GROUPS,
            "episodePreMinutes": 180,
            "episodePostMinutes": 180,
            "intentionalGridImportAllowed": False,
            "physicalWritesAllowed": False,
            "assessmentMode": "EVIDENCE_ONLY",
        },
        "episodeCount": len(episodes),
        "episodes": episodes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("/home/jeroen/ems/data/ems-history.sqlite"),
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path(
            "/home/jeroen/ems/runtime/tools/honeywell/output/"
            "honeywell-schedule.json"
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()

    start = _parse(args.start) if args.start else None
    end = _parse(args.end) if args.end else None

    if start is None or end is None:
        raise EpisodeError(
            "--start and --end are required when resolving "
            "Honeywell weekly schedule episodes"
        )

    schedule = _load_honeywell_schedule(args.schedule)

    con = sqlite3.connect(args.db)
    try:
        payload = build_episodes(
            con,
            schedule=schedule,
            start=start,
            end=end,
        )
    finally:
        con.close()

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(
            f"OK: {args.output} "
            f"({payload['episodeCount']} episodes, {SCHEMA})"
        )
    else:
        print(text, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

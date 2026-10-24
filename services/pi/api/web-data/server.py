"""Read-only operational data API for EMS Frontend V2.

This service is presentation transport only. It contains no EMS policy and no
control/device write path.
"""

import json
import logging
import math
import os
import sqlite3
import zlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HOST = os.environ.get("EMS_WEB_DATA_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMS_WEB_DATA_PORT", "3200"))
WW_SEASONAL_FILE = os.environ.get(
    "EMS_WW_SEASONAL_FILE",
    "/home/jeroen/ems/data/ww-seasonal-advisor.json",
)
EV_DEADLINE_FILE = os.environ.get(
    "EMS_EV_DEADLINE_FILE",
    "/home/jeroen/ems/data/ev-deadline-shadow-state.json",
)
DYNAMIC_PLAN_FILE = os.environ.get(
    "EMS_DYNAMIC_PLAN_FILE",
    "/home/jeroen/ems/data/dynamic-shadow-plan.json",
)
ENERGY_STATE_FILE = os.environ.get(
    "EMS_ENERGY_STATE_FILE",
    "/home/jeroen/ems/data/energy-state-v2.json",
)
TESLA_COMMAND_FILE = os.environ.get(
    "EMS_TESLA_COMMAND_FILE",
    "/home/jeroen/ems/data/tesla-deadline-command.json",
)
EMS_SETTINGS_COMMAND_FILE = os.environ.get(
    "EMS_SETTINGS_COMMAND_FILE",
    "/home/jeroen/ems/repo/homey-energy-manual/docs/data/ems-settings-command.json",
)
HISTORY_DB = os.environ.get("EMS_HISTORY_DB", "/home/jeroen/ems/data/ems-history.sqlite")
PLANNER_HISTORY_DB = os.environ.get("EMS_PLANNER_HISTORY_DB", "/home/jeroen/ems/data/planner-history.sqlite")
DAILY_PERFORMANCE_ARCHIVE_FILE = os.environ.get("EMS_DAILY_PERFORMANCE_ARCHIVE_FILE", "/home/jeroen/ems/data/daily-performance-archive.json")
HEATING_DAILY_ARCHIVE_FILE = os.environ.get("EMS_HEATING_DAILY_ARCHIVE_FILE", "/home/jeroen/ems/data/heating-daily-archive.json")
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

API_SCHEMA = "EMS_WEB_WW_SEASONAL_ADVICE_V1"
STATE_API_SCHEMA = "EMS_WEB_STATE_CURRENT_V1"
LIVE_QUOOKER_API_SCHEMA = "EMS_WEB_LIVE_QUOOKER_V1"
COMMANDS_API_SCHEMA = "EMS_WEB_COMMANDS_CURRENT_V1"
HISTORY_API_SCHEMA = "EMS_WEB_HISTORY_V1"
PV_FLEX_API_SCHEMA = "EMS_WEB_PV_FLEX_ANALYSIS_V1"
DAILY_PERFORMANCE_API_SCHEMA = "EMS_WEB_DAILY_PERFORMANCE_V1"
HEATING_DAILY_API_SCHEMA = "EMS_WEB_HEATING_DAILY_V1"
PLANNER_EVALUATION_API_SCHEMA = "EMS_WEB_PLANNER_EVALUATION_V2"
PV_FORECAST_API_SCHEMA = "EMS_WEB_PV_FORECAST_V2"
DYNAMIC_PLAN_API_SCHEMA = "EMS_WEB_DYNAMIC_PLAN_V1"
EV_REQUIREMENT_API_SCHEMA = "EMS_WEB_EV_REQUIREMENT_V1"
HEATING_SCHEDULE_API_SCHEMA = "EMS_WEB_HEATING_SCHEDULE_V1"
HEATING_TEMPERATURE_HISTORY_API_SCHEMA = "EMS_WEB_HEATING_TEMPERATURE_HISTORY_V1"
HEATING_PREHEAT_SHADOW_API_SCHEMA = "EMS_WEB_HEATING_PREHEAT_SHADOW_V1"
HEATING_PREHEAT_PROGRESSION_API_SCHEMA = "EMS_WEB_HEATING_PREHEAT_PROGRESSION_V1"
FLEX_PRIORITY_SHADOW_API_SCHEMA = "EMS_WEB_FLEX_PRIORITY_SHADOW_V1"
HEATING_TARGET_HISTORY_DAYS = 7
HONEYWELL_SCHEDULE_FILE = os.environ.get("EMS_HONEYWELL_SCHEDULE_FILE", "/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-schedule.json")
HEATING_ROOM_MODEL_FILE = os.environ.get(
    "EMS_HEATING_ROOM_MODEL_FILE",
    "/home/jeroen/ems/data/heating-room-model.json",
)
HEATING_PREHEAT_SHADOW_FILE = os.environ.get(
    "EMS_HEATING_PREHEAT_SHADOW_FILE",
    "/home/jeroen/ems/data/heating-preheat-shadow-v0.3.json",
)
HEATING_PREHEAT_PROGRESSION_FILE = os.environ.get(
    "EMS_HEATING_PREHEAT_PROGRESSION_FILE",
    "/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json",
)
FLEX_PRIORITY_SHADOW_FILE = os.environ.get(
    "EMS_FLEX_PRIORITY_SHADOW_FILE",
    "/home/jeroen/ems/data/flex-priority-shadow-v0.1.json",
)
ALLOWED_ADVICE = {
    "KEEP_CURRENT",
    "ADVISE_SWITCH_TO_CV",
    "ADVISE_SWITCH_TO_BOILER",
}
ALLOWED_MODES = {"CV", "BOILER"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def seasonal_advice_resource():
    """Return an allowlisted projection of the canonical advisor output."""
    source = load_json(WW_SEASONAL_FILE)

    generated_at = source.get("generatedAt")
    status = source.get("status")
    advice = source.get("advice")
    current_mode = source.get("currentMode")

    if parse_timestamp(generated_at) is None:
        raise ValueError("SOURCE_GENERATED_AT_INVALID")
    if not isinstance(status, str) or not status:
        raise ValueError("SOURCE_STATUS_INVALID")
    if advice not in ALLOWED_ADVICE:
        raise ValueError("SOURCE_ADVICE_INVALID")
    if current_mode not in ALLOWED_MODES:
        raise ValueError("SOURCE_CURRENT_MODE_INVALID")

    confirmation = source.get("confirmation")
    confirmed = None
    if isinstance(confirmation, dict):
        value = confirmation.get("confirmed")
        if isinstance(value, bool):
            confirmed = value

    return {
        "schema": API_SCHEMA,
        "generatedAt": generated_at,
        "status": status,
        "advice": advice,
        "currentMode": current_mode,
        "confirmation": {"confirmed": confirmed},
    }



def _live_l1_history():
    """Bounded P1-L1 net power history, independent of every PV inverter.

    Use only observed canonical P1 phase readings. Tesla measurements are
    optional interference context, never required for a valid P1 sample.
    Missing SQLite or a not-yet-populated P1 metric safely returns [].
    """
    after = (datetime.now(timezone.utc) - timedelta(minutes=110)).isoformat()
    try:
        with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True, timeout=1.0) as db:
            rows = db.execute(
                """
                SELECT x.ts_utc, d.device_key, m.metric_key, x.value_real
                FROM measurements x
                JOIN devices d ON d.id = x.device_id
                JOIN metrics m ON m.id = x.metric_id
                WHERE x.ts_utc >= ?
                  AND x.quality = 'observed'
                  AND (
                    (d.device_key='grid_p1' AND m.metric_key='grid_l1_power_w')
                    OR (d.device_key='tesla'
                        AND m.metric_key='electrical_power_w')
                  )
                ORDER BY x.ts_utc ASC
                """,
                (after,),
            ).fetchall()
    except (OSError, sqlite3.Error):
        return []

    grouped = {}
    for stamp, device, metric, value in rows:
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        item = grouped.setdefault(stamp, {"at": stamp})
        if device == "grid_p1" and metric == "grid_l1_power_w":
            item["l1_net_w"] = value
        elif device == "tesla":
            item["tesla_w"] = value
    # No cross-source completeness gate: the P1 observation stands alone.
    return [item for item in grouped.values() if "l1_net_w" in item][-30:]



def daily_performance_resource(value):
    """Read one completed date from the fixed Pi-local daily report archive.

    No subprocess, dynamic filesystem path, model call or policy calculation.
    """
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("DAILY_PERFORMANCE_DAY_INVALID")
    if day.isoformat() != value or day >= datetime.now(LOCAL_TZ).date():
        raise ValueError("DAILY_PERFORMANCE_DAY_NOT_COMPLETE")

    archive = load_json(DAILY_PERFORMANCE_ARCHIVE_FILE)
    if (not isinstance(archive, dict)
            or archive.get("schema") != "EMS_PI_DAILY_PERFORMANCE_ARCHIVE_V0.1"
            or not isinstance(archive.get("days"), dict)):
        raise RuntimeError("DAILY_PERFORMANCE_ARCHIVE_INVALID")
    item = archive["days"].get(value)
    if item is None:
        return None
    if (not isinstance(item, dict)
            or item.get("schema") != "EMS_PI_DAILY_PERFORMANCE_EVALUATION_V0.1"
            or item.get("dateLocal") != value
            or item.get("readOnly") is not True
            or item.get("controlWrites") is not False
            or item.get("status") not in {"READY", "PARTIAL", "INSUFFICIENT_EVIDENCE"}):
        raise RuntimeError("DAILY_PERFORMANCE_REPORT_INVALID")

    account = item.get("accounting")
    ev = item.get("evReplay")
    quality = item.get("quality")
    lines = item.get("lines")
    if not all(isinstance(value, dict) for value in (account, ev, quality)):
        raise RuntimeError("DAILY_PERFORMANCE_REPORT_INVALID")
    if (account.get("authority") != "P1_CUMULATIVE_ENERGY_COUNTERS"
            or ev.get("energyAuthority") != "SAMPLED_POWER_ESTIMATE_NOT_P1_COUNTER"
            or not isinstance(lines, list) or len(lines) > 8
            or any(not isinstance(line, str) or len(line) > 350 for line in lines)):
        raise RuntimeError("DAILY_PERFORMANCE_REPORT_INVALID")

    return {
        "schema": DAILY_PERFORMANCE_API_SCHEMA,
        "dateLocal": value,
        "status": item["status"],
        "readOnly": True,
        "controlWrites": False,
        "accounting": {
            key: account.get(key) for key in (
                "gridImportKWh", "gridExportKWh", "pvProducedKWh",
                "pvSelfConsumedKWh", "pvSelfConsumptionRate",
                "p1Coverage", "pairedCoverage",
            )
        },
        "evReplay": {
            "available": ev.get("available") is True,
            "estimatedAdditionalFeasibleCaptureKWh": ev.get("estimatedAdditionalFeasibleCaptureKWh"),
            "scope": "EV_EXPORT_ONLY",
            "energyAuthority": "SAMPLED_POWER_ESTIMATE_NOT_P1_COUNTER",
        },
        "quality": {
            "issues": [issue for issue in (quality.get("issues") or []) if isinstance(issue, str)][:12],
        },
        "lines": lines,
    }



def heating_daily_resource(value):
    """Allowlisted historical heating report; no runtime commands or unbounded file access."""
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("HEATING_DAY_INVALID")
    if day.isoformat() != value or day >= datetime.now(LOCAL_TZ).date():
        raise ValueError("HEATING_DAY_NOT_COMPLETE")

    archive = load_json(HEATING_DAILY_ARCHIVE_FILE)
    if (not isinstance(archive, dict)
            or archive.get("schema") != "EMS_HEATING_DAILY_ARCHIVE_V0.1"
            or not isinstance(archive.get("days"), dict)):
        raise RuntimeError("HEATING_ARCHIVE_INVALID")
    item = archive["days"].get(value)
    if item is None:
        return None
    if (not isinstance(item, dict)
            or item.get("schema") != "EMS_HEATING_DAILY_EVALUATION_V0.1"
            or item.get("dateLocal") != value
            or item.get("mode") != "READ_ONLY"
            or item.get("controlMode") != "SHADOW"
            or item.get("controlWrites") is not False):
        raise RuntimeError("HEATING_REPORT_INVALID")

    quality = item.get("quality")
    energy = item.get("energy")
    quatt = item.get("quattAndRooms")
    periods = item.get("periods")
    if not all(isinstance(x, dict) for x in (quality, energy, quatt, periods)):
        raise RuntimeError("HEATING_REPORT_INVALID")
    if quality.get("status") not in {"GOOD", "PARTIAL", "INSUFFICIENT"}:
        raise RuntimeError("HEATING_REPORT_INVALID")
    issues = quality.get("issues")
    if (not isinstance(issues, list) or len(issues) > 30
            or any(not isinstance(s, str) or len(s) > 120 for s in issues)):
        raise RuntimeError("HEATING_REPORT_INVALID")

    def numeric(value, *, lo=None, hi=None):
        if value is None:
            return None
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value)
                or (lo is not None and value < lo)
                or (hi is not None and value > hi)):
            raise RuntimeError("HEATING_REPORT_INVALID")
        return value

    def quatt_view(source):
        if not isinstance(source, dict):
            raise RuntimeError("HEATING_REPORT_INVALID")
        return {
            "electricKWh": numeric(source.get("quattElectricKWh"), lo=0),
            "hp1HeatSensorKWh": numeric(source.get("quattHeatHP1SensorKWh"), lo=0),
            "hp2HeatSensorKWh": numeric(source.get("quattHeatHP2SensorKWh"), lo=0),
            "hp1HeatToElectricRatio": numeric(source.get("pairedHP1HeatToElectricRatio"), lo=0),
            "completeSlots": numeric(source.get("quattElectricCompleteSlots"), lo=0),
            "expectedSlots": numeric(source.get("expectedSlots"), lo=0),
            "heatingSignalMean": numeric(source.get("heatingSignalMean"), lo=0, hi=1),
            "outsideTempMeanC": numeric(source.get("outsideTempMeanC"), lo=-80, hi=80),
        }

    def energy_view(source):
        if not isinstance(source, dict):
            raise RuntimeError("HEATING_REPORT_INVALID")
        good = source.get("balanceQuality") == "GOOD"
        return {
            "quality": "GOOD" if good else "INSUFFICIENT",
            "pairedCoverage": numeric(source.get("pairedCoverage"), lo=0, hi=1),
            "heldPvHours": numeric(source.get("heldPvHours"), lo=0),
            "estimatedPvHours": numeric(source.get("estimatedPvHours"), lo=0),
            "importKWh": numeric(source.get("importKWh"), lo=0) if good else None,
            "exportKWh": numeric(source.get("exportKWh"), lo=0) if good else None,
            "pvProducedKWh": numeric(source.get("pvProducedKWh"), lo=0) if good else None,
            "houseKWh": numeric(source.get("houseKWh"), lo=0) if good else None,
        }

    room_names = (
        ("woonkamer", "Woonkamer"),
        ("eetkamer", "Eetkamer"),
        ("keuken", "Keuken"),
        ("serre", "Serre"),
        ("douwe_slaapkamer", "Douwe slaapkamer"),
        ("erker_douwe", "Erker Douwe"),
        ("krijn_slaapkamer", "Krijn slaapkamer"),
        ("master_bedroom", "Master bedroom"),
    )
    raw_rooms = quatt.get("rooms")
    if not isinstance(raw_rooms, dict):
        raise RuntimeError("HEATING_REPORT_INVALID")
    rooms = []
    for key, label in room_names:
        room = raw_rooms.get(key)
        if not isinstance(room, dict):
            raise RuntimeError("HEATING_REPORT_INVALID")
        rooms.append({
            "name": label,
            "coverage": numeric(room.get("coverage"), lo=0, hi=1),
            "firstTemperatureC": numeric(room.get("firstTemperatureC"), lo=-40, hi=80),
            "lastTemperatureC": numeric(room.get("lastTemperatureC"), lo=-40, hi=80),
            "lastSetpointC": numeric(room.get("lastSetpointC"), lo=-40, hi=80),
            "belowSetpointBy02CSlots": numeric(room.get("belowSetpointBy02CSlots"), lo=0),
            "completePairedSlots": numeric(room.get("completePairedSlots"), lo=0),
        })
    period_views = []
    for key, title in (
        ("00-09", "00:00–09:00"), ("09-12", "09:00–12:00"),
        ("12-17", "12:00–17:00"), ("17-24", "17:00–24:00")
    ):
        block = periods.get(key)
        if not isinstance(block, dict):
            raise RuntimeError("HEATING_REPORT_INVALID")
        period_views.append({
            "label": title,
            "quatt": quatt_view(block.get("quattAndRooms")),
            "energy": energy_view(block.get("energy")),
        })

    cic = item.get("cicAndGas")
    if not isinstance(cic, dict):
        raise RuntimeError("HEATING_REPORT_INVALID")
    return {
        "schema": HEATING_DAILY_API_SCHEMA,
        "dateLocal": value,
        "readOnly": True, "controlWrites": False, "controlMode": "SHADOW",
        "quality": {"status": quality["status"], "issues": issues},
        "quatt": quatt_view(quatt),
        "energy": energy_view(energy),
        "rooms": rooms,
        "periods": period_views,
        "cic": {
            "boilerSelectedSamples": numeric(cic.get("cicBoilerSelectedSamples"), lo=0),
            "gasObservedSpanDeltaM3": numeric(cic.get("gasObservedSpanDeltaM3"), lo=0),
            "gasMeterObservedSamples": numeric(cic.get("gasMeterObservedSamples"), lo=0),
        },
    }


def heating_daily_temperature_resource(value):
    """Bounded 15m observational overlay for one archived, completed local day.

    Historic sampled targets may include manual overrides. They are NOT
    a replay of a versioned Honeywell weekly schedule.
    """
    archived = heating_daily_resource(value)  # also enforces completed date / archive gate
    if archived is None:
        return None
    day = datetime.strptime(value, "%Y-%m-%d").date()
    start = datetime.combine(day, datetime.min.time(), LOCAL_TZ).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), LOCAL_TZ).astimezone(timezone.utc)
    quarters = int((end - start).total_seconds() / 900)
    room_labels = {
        "woonkamer": "Woonkamer", "eetkamer": "Eetkamer", "keuken": "Keuken",
        "serre": "Serre", "douwe_slaapkamer": "Douwe slaapkamer",
        "erker_douwe": "Erker Douwe", "krijn_slaapkamer": "Krijn slaapkamer",
        "master_bedroom": "Master bedroom",
    }
    allowed = {
        **{f"honeywell_{key}": {"room_temperature_c", "room_setpoint_c"}
           for key in room_labels},
        "quatt_cic": {"heating_on", "outside_temperature_c"},
    }
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True, timeout=3.0) as con:
        con.execute("PRAGMA query_only=ON")
        rows = con.execute(
            """
            SELECT x.slot_start_utc, d.device_key, m.metric_key,
                   x.value_avg, x.quality
            FROM measurements_15m x
            JOIN devices d ON d.id=x.device_id
            JOIN metrics m ON m.id=x.metric_id
            WHERE julianday(x.slot_start_utc)>=julianday(?)
              AND julianday(x.slot_start_utc)<julianday(?)
              AND (d.device_key LIKE 'honeywell_%' OR d.device_key='quatt_cic')
              AND m.metric_key IN ('room_temperature_c','room_setpoint_c',
                                   'heating_on','outside_temperature_c')
            ORDER BY julianday(x.slot_start_utc)
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()

    slots = [start + timedelta(minutes=15 * i) for i in range(quarters)]
    names = [_utc_text(t) for t in slots]
    by_time = {name: i for i, name in enumerate(names)}
    observed = {}
    for stamp, device, metric, val, quality in rows:
        if metric not in allowed.get(device, ()):
            continue
        stamp_dt = parse_timestamp(stamp)
        if stamp_dt is None:
            continue
        i = by_time.get(_utc_text(stamp_dt))
        if i is None:
            continue
        if (quality != "complete" or not isinstance(val, (int, float))
                or isinstance(val, bool) or not math.isfinite(val)):
            continue
        if metric == "heating_on":
            if not 0 <= val <= 1:
                continue
        elif metric == "outside_temperature_c":
            if not -80 <= val <= 80:
                continue
        elif not -40 <= val <= 80:
            continue
        observed[(i, device, metric)] = round(float(val), 3)

    def series(device, metric):
        return [observed.get((i, device, metric)) for i in range(quarters)]

    heating = series("quatt_cic", "heating_on")
    outside = series("quatt_cic", "outside_temperature_c")

    def reaction_events(temperatures, targets):
        events = []
        for i in range(1, quarters - 2):
            previous, current = targets[i-1], targets[i]
            if previous is None or current is None:
                continue
            # Quarter means may smear a transition. Classify only distinct
            # steps, stable immediately before/after; otherwise unknown.
            if current - previous < 0.4:
                continue
            if (i < 2 or targets[i-2] is None
                    or abs(targets[i-2]-previous) > 0.15
                    or targets[i+1] is None
                    or abs(targets[i+1]-current) > 0.15):
                continue
            episode = {
                "at": names[i], "fromTargetC": previous,
                "toTargetC": current, "status": "UNKNOWN",
                "minutesToTarget": None,
            }
            if temperatures[i] is None:
                episode["status"] = "INSUFFICIENT_DATA"
            elif temperatures[i] >= current - 0.2:
                episode["status"] = "ALREADY_AT_TARGET"
            else:
                status = "NOT_REACHED_IN_WINDOW"
                # Four-hour observation window; stop if target changes or
                # continuity is broken. Missing data is never a 0-minute result.
                for j in range(i + 1, min(i + 17, quarters)):
                    if targets[j] is None or temperatures[j] is None:
                        status = "INSUFFICIENT_DATA"
                        break
                    if abs(targets[j] - current) > 0.15:
                        status = "TARGET_CHANGED"
                        break
                    if temperatures[j] >= current - 0.2:
                        status = "REACHED"
                        episode["minutesToTarget"] = (j-i)*15
                        break
                episode["status"] = status
            events.append(episode)
        return events[:16]

    def cooling_episode(temperatures, targets, period):
        """Most defensible continuous falling interval, *not* a heat-loss constant."""
        candidates = []
        run = []
        def evaluate(values):
            if len(values) < 5:
                return
            first, last = values[0], values[-1]
            drop = temperatures[first] - temperatures[last]
            duration = (last-first)*0.25
            if drop < 0.2 or duration < 1:
                return
            if any(temperatures[j] > temperatures[j-1] + 0.15
                   for j in values[1:]):
                return
            candidates.append((duration, drop, first, last))

        for i, stamp in enumerate(slots):
            hour = stamp.astimezone(LOCAL_TZ).hour
            matching = (18 <= hour < 24) if period == "evening" else (0 <= hour < 6)
            valid = (matching and temperatures[i] is not None
                     and targets[i] is not None
                     and heating[i] is not None and heating[i] <= 0.1)
            if valid and run:
                prev = run[-1]
                valid = (i == prev + 1
                         and abs(targets[i]-targets[prev]) <= 0.15
                         and temperatures[i] <= temperatures[prev] + 0.15)
            if not valid:
                evaluate(run)
                run = []
            if matching and temperatures[i] is not None and targets[i] is not None and heating[i] is not None and heating[i] <= 0.1:
                run = run + [i] if not run or valid else [i]
        evaluate(run)
        if not candidates:
            return {"status": "INSUFFICIENT_EVIDENCE",
                    "coolingCPerHour": None, "durationMinutes": None,
                    "fromAt": None, "toAt": None}
        duration, drop, first, last = max(candidates, key=lambda c: (c[0], c[1]))
        return {
            "status": "OBSERVED_WITH_QUATT_SIGNAL_OFF",
            "coolingCPerHour": round(drop/duration, 3),
            "temperatureDropC": round(drop, 3),
            "durationMinutes": int(duration*60),
            "fromAt": names[first], "toAt": names[last],
        }

    room_views = []
    for key, label in room_labels.items():
        actual = series(f"honeywell_{key}", "room_temperature_c")
        target = series(f"honeywell_{key}", "room_setpoint_c")
        room_views.append({
            "key": key, "name": label,
            "series": [{"at": names[i], "temperatureC": actual[i],
                        "observedTargetC": target[i]}
                       for i in range(quarters)],
            "responseEvents": reaction_events(actual, target),
            "cooling": {
                "evening": cooling_episode(actual, target, "evening"),
                "night": cooling_episode(actual, target, "night"),
            },
            "completePairedSlots": sum(a is not None and b is not None
                                       for a, b in zip(actual, target)),
        })

    return {
        "schema": "EMS_WEB_HEATING_DAILY_TEMPERATURE_V1",
        "dateLocal": value, "timezone": "Europe/Amsterdam",
        "mode": "READ_ONLY", "controlMode": "SHADOW",
        "controlWrites": False, "presentationOnly": True,
        "expectedSlots": quarters, "sampleMinutes": 15,
        "source": "CANONICAL_MEASUREMENTS_15M",
        "setpointProvenance": "OBSERVED_HONEYWELL_SETPOINT_INCLUDING_OVERRIDES_NOT_VERSIONED_WEEKLY_SCHEDULE",
        "quatt": [{"at": names[i], "heatingOnFraction": heating[i],
                   "outsideTemperatureC": outside[i]}
                  for i in range(quarters)],
        "rooms": room_views,
        "interpretation": {
            "reaction": "OBSERVED_TIME_TO_RECORDED_TARGET_NOT_PHYSICAL_ROOM_HEATUP_CAUSALITY",
            "cooling": "FALLING_ROOM_TEMPERATURE_WHILE_WHOLE_QUATT_HEATING_SIGNAL_OFF",
        },
    }


def state_current_resource():
    """Return the allowlisted Live V2 projection of canonical Pi energy state."""
    source = load_json(ENERGY_STATE_FILE)
    meta = source.get("meta")
    if not isinstance(meta, dict) or parse_timestamp(meta.get("generated_at")) is None:
        raise ValueError("SOURCE_GENERATED_AT_INVALID")

    allowed_top = {
        "meta": ("generated_at", "source_sample_at", "state_age_sec"),
        "grid": ("power_w", "l1_w", "l2_w", "l3_w"),
        "pv": ("total_w", "solaredge_w", "goodwe_4200_w", "goodwe_2000_w"),
        "quatt": ("power_w", "thermostat_heating_on"),
        "energy_budget": ("other_house_load_w",),
        "tesla": (
            "connected", "charging", "power_w", "requested_a", "deadline_at",
            "deadline_active", "need", "remaining_kwh",
        ),
        "hot_water": ("boiler_on", "boiler_power_w", "mode"),
        "manager": ("decision", "reason", "priority"),
    }

    result = {"schema": STATE_API_SCHEMA}
    for section, fields in allowed_top.items():
        value = source.get(section)
        if not isinstance(value, dict):
            value = {}
        result[section] = {name: value.get(name) for name in fields}

    balance = source.get("balance")
    gate = balance.get("control_gate") if isinstance(balance, dict) else None
    source_timing = balance.get("source_timing") if isinstance(balance, dict) else None
    freshness = source_timing.get("freshness") if isinstance(source_timing, dict) else None
    result["balance"] = {
        "control_gate": {
            "grid_measurement_valid": gate.get("grid_measurement_valid")
            if isinstance(gate, dict) else None
        }
    }
    result["pv"]["sources"] = {}
    for api_name, source_name in (
        ("solarEdge", "solarEdge"),
        ("goodWe4200", "goodWe4200"),
        ("goodWe2000", "goodWe2000"),
    ):
        quality = freshness.get(source_name) if isinstance(freshness, dict) else None
        result["pv"]["sources"][api_name] = {
            "fresh": quality.get("fresh") if isinstance(quality, dict) else None,
            "age_sec": quality.get("ageSec") if isinstance(quality, dict) else None,
            "max_age_sec": quality.get("maxAgeSec") if isinstance(quality, dict) else None,
        }

    hot_water = source.get("hot_water")
    control = hot_water.get("control") if isinstance(hot_water, dict) else None
    result["hot_water"]["control"] = {
        "action": control.get("action") if isinstance(control, dict) else None
    }
    # Only the minimal Homey status/phase evidence needed for Live diagnostics.
    # No per-appliance power is synthesized from P1 phase load.
    loads = source.get("loads")
    loads = loads if isinstance(loads, dict) else {}
    result["loads"] = {}
    for key in ("washer", "dryer"):
        item = loads.get(key)
        item = item if isinstance(item, dict) else {}
        detail = item.get("state")
        detail = detail if isinstance(detail, dict) else {}
        active = item.get("active")
        result["loads"][key] = {
            "active": active if isinstance(active, bool) else None,
            "appliance_state": detail.get("applianceState")
            if isinstance(detail.get("applianceState"), str) else None,
            "cycle_phase": detail.get("cyclePhase")
            if isinstance(detail.get("cyclePhase"), str) else None,
        }

    quooker = loads.get("quooker")
    quooker = quooker if isinstance(quooker, dict) else {}
    quooker_fresh = quooker.get("fresh") is True
    quooker_active = quooker.get("active")
    quooker_power = quooker.get("power_w")
    result["loads"]["quooker"] = {
        "fresh": quooker_fresh,
        "active": quooker_active
        if quooker_fresh and isinstance(quooker_active, bool) else None,
        "estimated_power_w": quooker_power
        if quooker_fresh and isinstance(quooker_power, (int, float))
        and not isinstance(quooker_power, bool) else None,
    }
    result["diagnostics"] = {"dishwasher_l1_history": _live_l1_history()}
    return result



def live_quooker_resource():
    """Present recent switch evidence and the last archived Quooker heat pulse.

    This independent, read-only projection does not change /web/state/current,
    Core ingestion, the planner or device ownership. SQLite rows are events,
    not a guaranteed heartbeat; use the more recent fresh Core snapshot for
    the switch when archived event evidence is older.
    """
    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True, timeout=2.0) as db:
        row = db.execute("""
            SELECT ts_utc, control_mode, detector_switch_on,
                   actuator_actual_on_after, detector_last_heating_at
            FROM quooker_control_events
            ORDER BY id DESC LIMIT 1
        """).fetchone()

    event_at = row[0] if row else None
    event_time = parse_timestamp(event_at)
    event_mode = row[1] if row and row[1] in ("OPPORTUNITY", "FORCED_ON", "OFF") else None
    event_switch = None
    if row:
        raw_switch = row[2] if row[2] in (0, 1) else row[3]
        if raw_switch in (0, 1):
            event_switch = bool(raw_switch)

    now = datetime.now(timezone.utc)
    last_heated_at = row[4] if row and parse_timestamp(row[4]) else None
    if last_heated_at and (parse_timestamp(last_heated_at) - now).total_seconds() > 60:
        last_heated_at = None

    core_time = None
    core_switch = None
    try:
        state = load_json(ENERGY_STATE_FILE)
        meta = state.get("meta") or {}
        core_time = parse_timestamp(meta.get("source_sample_at"))
        quooker = (state.get("loads") or {}).get("quooker") or {}
        if quooker.get("fresh") is True and isinstance(quooker.get("switch_on"), bool):
            core_switch = quooker["switch_on"]
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        pass

    # Only fresh evidence may assert the current switch position. The last
    # heating timestamp is historical and deliberately has no short TTL.
    def is_recent(timestamp):
        return timestamp is not None and -60 <= (now - timestamp).total_seconds() <= 180

    switch_on = None
    switch_sample_at = None
    if core_switch is not None and is_recent(core_time):
        switch_on = core_switch
        switch_sample_at = core_time
    if event_switch is not None and is_recent(event_time) and (
        switch_sample_at is None or event_time >= switch_sample_at
    ):
        switch_on = event_switch
        switch_sample_at = event_time

    return {
        "schema": LIVE_QUOOKER_API_SCHEMA,
        "mode": event_mode,
        "mode_event_at": event_at if event_time else None,
        "switch_on": switch_on,
        "switch_sample_at": switch_sample_at.isoformat().replace("+00:00", "Z")
        if switch_sample_at else None,
        "last_heated_at": last_heated_at,
    }


def commands_current_resource():
    """Return the allowlisted last-accepted command state required by Invoer V2."""
    tesla = load_json(TESLA_COMMAND_FILE)
    settings = load_json(EMS_SETTINGS_COMMAND_FILE)

    current_soc = tesla.get("currentSoc")
    target_soc = tesla.get("targetSoc")
    max_a = tesla.get("maxA")
    deadline = tesla.get("deadline")
    request_id = tesla.get("requestId")
    active = tesla.get("active")

    if not isinstance(active, bool):
        raise ValueError("TESLA_ACTIVE_INVALID")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("TESLA_REQUEST_ID_INVALID")
    if active:
        if not isinstance(current_soc, (int, float)) or isinstance(current_soc, bool) or not 0 <= current_soc <= 99:
            raise ValueError("TESLA_CURRENT_SOC_INVALID")
        if not isinstance(target_soc, (int, float)) or isinstance(target_soc, bool) or not 1 <= target_soc <= 100 or target_soc <= current_soc:
            raise ValueError("TESLA_TARGET_SOC_INVALID")
        if not isinstance(max_a, (int, float)) or isinstance(max_a, bool) or not 6 <= max_a <= 16:
            raise ValueError("TESLA_MAX_A_INVALID")
        if not isinstance(deadline, str) or not deadline:
            raise ValueError("TESLA_DEADLINE_INVALID")
    else:
        current_soc = None
        target_soc = None
        deadline = ""
        max_a = None

    contract_type = settings.get("contractType")
    hot_water_source = settings.get("hotWaterSource")
    settings_request_id = settings.get("requestId")
    if contract_type not in {"FIXED", "DYNAMIC"}:
        raise ValueError("SETTINGS_CONTRACT_TYPE_INVALID")
    if hot_water_source not in {"CV", "BOILER"}:
        raise ValueError("SETTINGS_HOT_WATER_SOURCE_INVALID")
    if not isinstance(settings_request_id, str) or not settings_request_id:
        raise ValueError("SETTINGS_REQUEST_ID_INVALID")

    return {
        "schema": COMMANDS_API_SCHEMA,
        "tesla": {
            "active": active,
            "currentSoc": current_soc,
            "targetSoc": target_soc,
            "deadline": deadline,
            "maxA": max_a,
            "requestId": request_id,
        },
        "settings": {
            "contractType": contract_type,
            "hotWaterSource": hot_water_source,
            "requestId": settings_request_id,
        },
    }



def _history_period(kind, value):
    """Resolve a strict path period to Europe/Amsterdam calendar boundaries."""
    try:
        if kind == "day":
            if len(value) != 10:
                raise ValueError
            start = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
            end = start + timedelta(days=1)
            bucket = "hour"
        elif kind == "week":
            if len(value) != 10:
                raise ValueError
            anchor = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=7)
            bucket = "day"
        elif kind == "month":
            if len(value) != 7:
                raise ValueError
            start = datetime.strptime(value, "%Y-%m").replace(tzinfo=LOCAL_TZ)
            end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            bucket = "day"
        elif kind == "year":
            if len(value) != 4:
                raise ValueError
            start = datetime.strptime(value, "%Y").replace(tzinfo=LOCAL_TZ)
            end = start.replace(year=start.year + 1)
            bucket = "month"
        else:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("HISTORY_PERIOD_INVALID")
    return start, end, bucket


def _utc_text(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _bucket_start(local_dt, bucket):
    if bucket == "hour":
        return local_dt.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_dt.replace(month=local_dt.month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_bucket(local_dt, bucket):
    if bucket == "hour":
        return local_dt + timedelta(hours=1)
    if bucket == "day":
        return local_dt + timedelta(days=1)
    if local_dt.month == 12:
        return local_dt.replace(year=local_dt.year + 1, month=1)
    return local_dt.replace(month=local_dt.month + 1)


def history_resource(kind, value):
    """Return bounded, read-only household energy history for Frontend V2."""
    start_local, end_local, bucket_kind = _history_period(kind, value)
    start_utc, end_utc = _utc_text(start_local), _utc_text(end_local)

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        rows = db.execute(
            """
            SELECT start_ts_utc,end_ts_utc,duration_seconds,import_kwh,export_kwh,
                   pv_solaredge_kwh,pv_goodwe4200_kwh,pv_goodwe2000_kwh,
                   pv_total_kwh,house_kwh,quality,discontinuity_reason
            FROM house_energy_intervals
            WHERE end_ts_utc > ? AND start_ts_utc < ?
            ORDER BY end_ts_utc
            """,
            (start_utc, end_utc),
        ).fetchall()

    fields = (
        "importKWh", "exportKWh", "pvSolarEdgeKWh", "pvGoodWe4200KWh",
        "pvGoodWe2000KWh", "pvKWh", "houseKWh",
    )
    buckets = {}
    if bucket_kind == "hour":
        cursor_utc = start_local.astimezone(timezone.utc)
        end_cursor_utc = end_local.astimezone(timezone.utc)
        while cursor_utc < end_cursor_utc:
            nxt_utc = min(cursor_utc + timedelta(hours=1), end_cursor_utc)
            cursor = cursor_utc.astimezone(LOCAL_TZ)
            nxt = nxt_utc.astimezone(LOCAL_TZ)
            buckets[_utc_text(cursor)] = {
                "start": cursor.isoformat(), "end": nxt.isoformat(),
                **{name: 0.0 for name in fields},
                "coveredSeconds": 0, "gapCount": 0, "discontinuityCount": 0,
            }
            cursor_utc = nxt_utc
    else:
        cursor = _bucket_start(start_local, bucket_kind)
        while cursor < end_local:
            nxt = _next_bucket(cursor, bucket_kind)
            buckets[_utc_text(cursor)] = {
                "start": cursor.isoformat(), "end": nxt.isoformat(),
                **{name: 0.0 for name in fields},
                "coveredSeconds": 0, "gapCount": 0, "discontinuityCount": 0,
            }
            cursor = nxt

    valid_seconds = 0
    gaps = 0
    discontinuities = 0
    first_data = None
    last_data = None
    totals = {name: 0.0 for name in fields}
    column_map = {
        "importKWh": 3, "exportKWh": 4, "pvSolarEdgeKWh": 5,
        "pvGoodWe4200KWh": 6, "pvGoodWe2000KWh": 7,
        "pvKWh": 8, "houseKWh": 9,
    }

    for row in rows:
        row_start = parse_timestamp(row[0])
        row_end = parse_timestamp(row[1])
        if row_start is None or row_end is None:
            continue
        clipped_start = max(row_start, start_local.astimezone(timezone.utc))
        clipped_end = min(row_end, end_local.astimezone(timezone.utc))
        overlap = max(0.0, (clipped_end - clipped_start).total_seconds())
        if overlap <= 0:
            continue
        quality = row[10]
        if quality == "discontinuity":
            discontinuities += 1
        else:
            valid_seconds += overlap
            first_data = min(first_data, clipped_start) if first_data else clipped_start
            last_data = max(last_data, clipped_end) if last_data else clipped_end
        if quality == "gap":
            gaps += 1

        row_seconds = max(1.0, (row_end - row_start).total_seconds())
        segment_start = clipped_start
        while segment_start < clipped_end:
            local_segment = segment_start.astimezone(LOCAL_TZ)
            bucket_local = _bucket_start(local_segment, bucket_kind)
            bucket_end_utc = _next_bucket(bucket_local, bucket_kind).astimezone(timezone.utc)
            segment_end = min(clipped_end, bucket_end_utc)
            segment_seconds = max(0.0, (segment_end - segment_start).total_seconds())
            key = _utc_text(bucket_local)
            bucket = buckets.get(key)
            if bucket is not None:
                if quality == "gap":
                    bucket["gapCount"] += 1
                if quality == "discontinuity":
                    bucket["discontinuityCount"] += 1
                else:
                    bucket["coveredSeconds"] += segment_seconds
                    fraction = segment_seconds / row_seconds
                    for name, index in column_map.items():
                        value_num = row[index]
                        if value_num is not None:
                            amount = float(value_num) * fraction
                            bucket[name] += amount
                            totals[name] += amount
            segment_start = segment_end

    requested_seconds = (end_local.astimezone(timezone.utc) - start_local.astimezone(timezone.utc)).total_seconds()
    series = []
    for bucket in buckets.values():
        item = dict(bucket)
        for name in fields:
            item[name] = round(item[name], 6)
        bucket_start = datetime.fromisoformat(item["start"])
        bucket_end = datetime.fromisoformat(item["end"])
        bucket_seconds = (bucket_end.astimezone(timezone.utc) - bucket_start.astimezone(timezone.utc)).total_seconds()
        item["coverage"] = round(min(1.0, item.pop("coveredSeconds") / bucket_seconds), 6)
        series.append(item)

    return {
        "schema": HISTORY_API_SCHEMA,
        "period": {
            "kind": kind, "requested": value, "timezone": "Europe/Amsterdam",
            "start": start_local.isoformat(), "end": end_local.isoformat(),
            "bucket": bucket_kind,
        },
        "summary": {name: round(value_num, 6) for name, value_num in totals.items()},
        "series": series,
        "quality": {
            "coverage": round(min(1.0, valid_seconds / requested_seconds), 6),
            "gapCount": gaps,
            "discontinuityCount": discontinuities,
            "firstDataAt": _utc_text(first_data) if first_data else None,
            "lastDataAt": _utc_text(last_data) if last_data else None,
        },
    }




def planner_evaluation_resource(value):
    """Replay only evidence frozen into the last valid decision before each slot.

    Forecast, EV/WW/Quooker planning and net consequences always come from the
    SAME archived Pi plan. No fixed-lead weather score or reconstructed actions.
    Actual P1/PV/device observations are served by pv_flex_analysis_resource.
    """
    start_local, end_local, _ = _history_period("day", value)
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)
    slots = {}
    cursor = start
    while cursor < end:
        slots[_utc_text(cursor)] = {
            "start": cursor.astimezone(LOCAL_TZ).isoformat(),
            "forecast": None,
            "plan": None,
            "displayForecast": None,
        }
        cursor += timedelta(minutes=15)

    with sqlite3.connect(f"file:{PLANNER_HISTORY_DB}?mode=ro", uri=True) as db:
        snapshots = db.execute(
            """SELECT generated_at_utc, valid_until_utc, snapshot_zlib
               FROM planner_snapshots
               WHERE julianday(generated_at_utc) >= julianday(?)
                 AND julianday(generated_at_utc) < julianday(?)
               ORDER BY julianday(generated_at_utc) DESC
               LIMIT 1000""",
            (_utc_text(start - timedelta(hours=36)), _utc_text(end)),
        ).fetchall()

    def watts(item, key, *, optional=False):
        value = item.get(key)
        if optional and value is None:
            return None
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not 0 <= value <= 50000):
            raise ValueError("PLANNER_EVALUATION_POWER_INVALID")
        return value

    for generated_value, valid_until_value, payload in snapshots:
        generated = parse_timestamp(generated_value)
        valid_until = parse_timestamp(valid_until_value)
        if generated is None or valid_until is None or valid_until <= generated:
            continue
        try:
            document = json.loads(zlib.decompress(payload))
            plan = document.get("plan") or {}
        except (zlib.error, ValueError, TypeError, AttributeError):
            continue
        if (plan.get("schema") != "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3"
                or plan.get("mode") != "PURE_SHADOW"
                or plan.get("readOnly") is not True
                or plan.get("control_writes") is not False
                or parse_timestamp(plan.get("generated_at")) != generated):
            continue
        guardrails = plan.get("guardrails") or {}
        ww_mode = guardrails.get("wwSourceMode")
        if ww_mode not in {"CV", "BOILER", "UNKNOWN"}:
            ww_mode = None
        for item in plan.get("slots") or []:
            if not isinstance(item, dict):
                continue
            when = parse_timestamp(item.get("slot_start_utc"))
            if when is None or when < generated:
                continue
            slot = slots.get(_utc_text(when))
            if slot is None or slot["plan"] is not None:
                continue
            if when > valid_until:
                # Archive PV values can be displayed, never reused as
                # valid planner decisions or comparable evaluation evidence.
                age_seconds = (when - generated).total_seconds()
                if age_seconds > 45 * 60 or slot["displayForecast"] is not None:
                    continue
                try:
                    display_w = watts(item, "pvForecastW")
                except ValueError:
                    continue
                slot["displayForecast"] = {
                    "pvForecastW": display_w,
                    "generatedAt": generated_value,
                    "ageMinutes": round(age_seconds / 60, 1),
                    "source": "ARCHIVED_EXPIRED_PLAN_DISPLAY_ONLY",
                }
                continue
            try:
                values = {key: watts(item, key) for key in (
                    "pvForecastW", "evPlanW", "wwPlanW",
                    "gridImportAfterFlexW", "gridExportAfterFlexW",
                )}
                quooker_w = watts(item, "quookerPlanW", optional=True)
            except ValueError:
                continue
            confidence = item.get("confidence")
            if (not isinstance(confidence, (int, float))
                    or isinstance(confidence, bool)
                    or not 0 <= confidence <= 1):
                confidence = None
            ev_reason = item.get("evAllocationReason")
            ww_reason = item.get("wwAllocationReason")
            quooker_mode = item.get("quookerMode")
            if quooker_mode not in {"OPPORTUNITY", "FORCED_ON", "OFF"}:
                quooker_mode = None
            quooker_allowed = item.get("quookerOpportunityAllowed")
            if not isinstance(quooker_allowed, bool):
                quooker_allowed = None
            # The forecast is the value the SAME selected decision used.
            slot["displayForecast"] = None
            slot["forecast"] = {
                "pvForecastW": values["pvForecastW"],
                "confidence": confidence,
                "generatedAt": generated_value,
            }
            slot["plan"] = {
                "evPlanW": values["evPlanW"],
                "wwPlanW": values["wwPlanW"],
                "quookerPlanW": quooker_w,
                "quookerMode": quooker_mode,
                "quookerOpportunityAllowed": quooker_allowed,
                "wwSourceMode": ww_mode,
                "teslaAvailableForecast": item.get("teslaAvailableForecast")
                    if isinstance(item.get("teslaAvailableForecast"), bool) else None,
                "gridImportAfterFlexW": values["gridImportAfterFlexW"],
                "gridExportAfterFlexW": values["gridExportAfterFlexW"],
                "evReason": ev_reason if isinstance(ev_reason, str) and len(ev_reason) <= 120 else None,
                "wwReason": ww_reason if isinstance(ww_reason, str) and len(ww_reason) <= 120 else None,
                "generatedAt": generated_value,
                "validUntil": valid_until_value,
            }

    series = list(slots.values())
    planned = [slot["plan"] for slot in series if slot["plan"] is not None]
    quooker_known = [item["quookerPlanW"] for item in planned if item["quookerPlanW"] is not None]
    return {
        "schema": PLANNER_EVALUATION_API_SCHEMA,
        "mode": "READ_ONLY",
        "controlWrites": False,
        "forecastSource": "ARCHIVED_CANONICAL_V1_DYNAMIC_PLAN",
        "forecastSelection": {"kind": "SAME_AS_VALID_PLAN_DECISION"},
        "displayForecastSelection": {
            "kind": "LATEST_ARCHIVED_FORECAST_DISPLAY_ONLY",
            "maxAgeMinutes": 45,
            "doesNotCreatePlanEvidence": True,
        },
        "planSelection": {"kind": "LATEST_VALID_BEFORE_SLOT_START"},
        "summary": {
            "forecastSlots": len(planned),
            "forecastKWh": round(sum(slot["forecast"]["pvForecastW"] for slot in series
                                     if slot["forecast"] is not None)/4000, 6) if planned else None,
            "planSlots": len(planned),
            "plannedEvKWh": round(sum(item["evPlanW"] for item in planned)/4000, 6) if planned else None,
            "plannedWwKWh": round(sum(item["wwPlanW"] for item in planned)/4000, 6) if planned else None,
            "quookerPlanSlots": len(quooker_known),
            "plannedQuookerKWh": round(sum(quooker_known)/4000, 6) if quooker_known else None,
        },
        "series": series,
    }



def daily_pv_self_use_accounting(pv_kwh, export_kwh, paired_seconds, expected_seconds, day_complete):
    """Only validated historical PV/P1 energy deltas may produce a daily ratio.

    Completed day: >=95% paired energy coverage; in-progress day: >=95% of
    elapsed time, explicitly provisional. Never turn gaps into zero PV or
    clamp a negative energy balance into a plausible percentage.
    """
    coverage = (
        min(1.0, paired_seconds / expected_seconds)
        if expected_seconds > 0 else 0.0
    )
    status = "INSUFFICIENT_COVERAGE"
    rate = None
    used = None
    if (expected_seconds >= 1800 and coverage >= 0.95
            and isinstance(pv_kwh, (int, float))
            and isinstance(export_kwh, (int, float))
            and math.isfinite(pv_kwh) and math.isfinite(export_kwh)):
        if pv_kwh <= 0:
            status = "NO_PV_PRODUCTION"
        elif export_kwh < 0 or export_kwh > pv_kwh + 1e-6:
            status = "INVALID_ENERGY_BALANCE"
        else:
            used = round(max(0.0, pv_kwh - export_kwh), 6)
            rate = round(used / pv_kwh, 4)
            status = "COMPLETE" if day_complete else "PROVISIONAL"
    return {
        "status": status,
        "pairedCoverage": round(coverage, 6),
        "selfConsumedKWh": used,
        "rate": rate,
        "source": "house_energy_intervals:PV_cumulative_minus_P1_export",
        "readOnly": True,
    }


def provisional_daily_report_resource(value, series, paired_seconds_by_slot, now_utc=None):
    """Read-only cumulative accounting through the last closed, paired 15m slot.

    An open quarter, unpaired P1/PV interval or a gap in today's historical
    evidence cannot silently contribute to the subtotal. Missing coverage is
    reported rather than extrapolated. Completed-day archive is unchanged.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    if value != now_utc.astimezone(LOCAL_TZ).date().isoformat():
        return None

    local_start = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
    day_start = local_start.astimezone(timezone.utc)
    valid_slots = []
    for slot in series:
        start = parse_timestamp(slot.get("start"))
        end = parse_timestamp(slot.get("end"))
        if start is None or end is None or end <= start or end > now_utc:
            continue
        seconds = (end - start).total_seconds()
        actual = slot.get("actual") or {}
        values = (actual.get("pvKWh"), actual.get("importKWh"),
                  actual.get("exportKWh"))
        if not all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0
                   for x in values):
            continue
        p1 = actual.get("p1Coverage")
        pv = actual.get("pvCoverage")
        paired = max(0.0, min(seconds,
                     paired_seconds_by_slot.get(_utc_text(start), 0.0)))
        if (isinstance(p1, (int, float)) and p1 >= 0.95
                and isinstance(pv, (int, float)) and pv >= 0.95
                and paired >= seconds * 0.95):
            valid_slots.append((slot, end, paired))

    through = max((end for _, end, _ in valid_slots), default=None)
    selected = [entry for entry in valid_slots if entry[1] <= through] if through else []
    window_seconds = (through - day_start).total_seconds() if through else 0.0
    paired_seconds = sum(entry[2] for entry in selected)
    coverage = (min(1.0, paired_seconds / window_seconds)
                if window_seconds > 0 else 0.0)
    trustworthy = window_seconds >= 1800 and coverage >= 0.95
    accounting = {
        "gridImportKWh": None, "gridExportKWh": None,
        "pvProducedKWh": None, "pvSelfConsumedKWh": None,
        "pvSelfConsumptionRate": None, "pairedCoverage": round(coverage, 6),
    }
    notes = []
    if trustworthy:
        pv_kwh = round(sum(item["actual"]["pvKWh"] for item, _, _ in selected), 6)
        import_kwh = round(sum(item["actual"]["importKWh"] for item, _, _ in selected), 6)
        export_kwh = round(sum(item["actual"]["exportKWh"] for item, _, _ in selected), 6)
        own_use = daily_pv_self_use_accounting(
            pv_kwh, export_kwh, paired_seconds, window_seconds, False,
        )
        accounting.update({
            "gridImportKWh": import_kwh,
            "gridExportKWh": export_kwh,
            "pvProducedKWh": pv_kwh,
            "pvSelfConsumedKWh": own_use["selfConsumedKWh"],
            "pvSelfConsumptionRate": own_use["rate"],
        })
        notes.append("Voorlopig subtotaal uit afgesloten kwartieren; geen schatting of prognose.")
        if coverage < 1.0:
            notes.append(f"Niet alle metingen volledig: {coverage:.1%} gekoppelde P1/PV-dekking.")
        if own_use["status"] == "INVALID_ENERGY_BALANCE":
            notes.append("PV-export overschrijdt de gemeten PV-productie; zelfverbruik niet berekend.")
        elif own_use["status"] == "NO_PV_PRODUCTION":
            notes.append("Nog geen aantoonbare PV-productie; zelfverbruikpercentage niet beschikbaar.")
    else:
        notes.append(
            "Onvoldoende aaneengesloten P1/PV-meetbewijs tot het laatste berekende kwartier; "
            "subtotaal verborgen om een onvolledig dagbeeld te voorkomen."
            if through else "Nog geen afgesloten kwartier met voldoende P1- en PV-meetbewijs."
        )

    return {
        "schema": DAILY_PERFORMANCE_API_SCHEMA,
        "dateLocal": value,
        "status": "PROVISIONAL" if trustworthy else "INSUFFICIENT_EVIDENCE",
        "readOnly": True, "controlWrites": False,
        "throughLocal": through.astimezone(LOCAL_TZ).isoformat() if through else None,
        "accounting": accounting,
        "quality": {"pairedCoverage": round(coverage, 6)},
        "lines": notes,
    }




def goodwe_daily_counter_resource(value):
    """Durable SEMS+ reported day counters, not 15m household accounting.

    The two inverters are combined by pseudonymous identity, so a physical
    4200/2000 mapping is not required for an aggregate daily counter reading.
    """
    start_local, end_local, _ = _history_period("day", value)
    start = start_local.astimezone(timezone.utc).isoformat(timespec="microseconds")
    end = end_local.astimezone(timezone.utc).isoformat(timespec="microseconds")
    source_path = os.environ.get(
        "EMS_GOODWE_COUNTER_ARCHIVE_DB",
        "/home/jeroen/ems/runtime/state/goodwe-sems-counters.sqlite",
    )
    result = {
        "schema": "EMS_WEB_GOODWE_DAILY_COUNTERS_V1",
        "dateLocal": value,
        "source": "GOODWE_SEMS_PLUS",
        "authoritativeFor": "SEPARATE_GOODWE_REPORTED_DAY_COUNTERS_ONLY",
        "controlWrites": False,
        "eligibleForControl": False,
        "eligibleForHouseBalance": False,
        "timeBasis": "PI_FETCH_TIME_SOURCE_TIME_UNKNOWN",
        "counterResolutionKWh": 0.1,
        "status": "NO_ARCHIVE",
        "samplePairs": 0,
        "lastFetchedAt": None,
        "reportedDayKWh": None,
        "windowCounterGrowthKWh": None,
        "devices": [],
    }
    if not os.path.isfile(source_path):
        return result

    with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True, timeout=5) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute("""
            SELECT fetched_at_utc,device_key,serial_suffix,today_kwh,
                   lifetime_kwh,power_w,source_status
            FROM goodwe_counter_observations
            WHERE fetched_at_utc >= ? AND fetched_at_utc < ?
            ORDER BY fetched_at_utc,device_key
        """, (start, end)).fetchall()
    if not rows:
        result["status"] = "NO_SAMPLES"
        return result

    pairs = {}
    for when, key, suffix, day, lifetime, power, status in rows:
        pairs.setdefault(when, []).append((key, suffix, day, lifetime, power))
    valid = [(at, readings) for at, readings in sorted(pairs.items())
             if len(readings) == 2 and len({item[0] for item in readings}) == 2
             and len({item[1] for item in readings}) == 2]
    if not valid:
        result["status"] = "INCOMPLETE"
        return result

    # Fail closed on identities changing during the day, any reset/decrease,
    # missing meter updates, or contradictory samples. Never mix two sources.
    keys = {entry[0] for entry in valid[0][1]}
    if any({entry[0] for entry in pair} != keys for _, pair in valid):
        result["status"] = "IDENTITY_CHANGED"
        return result

    by_key = {key: [] for key in keys}
    for at, items in valid:
        for key, suffix, today, lifetime, power in items:
            if (not all(isinstance(v, (int, float)) and
                        not isinstance(v, bool) and math.isfinite(v) and v >= 0
                        for v in (today, lifetime))):
                result["status"] = "INVALID_COUNTER"
                return result
            by_key[key].append((at, suffix, today, lifetime, power))
    for values in by_key.values():
        if any(current[2] < previous[2] - 1e-6 or
               current[3] < previous[3] - 1e-6 or
               current[1] != previous[1]
               for previous, current in zip(values, values[1:])):
            result["status"] = "COUNTER_DISCONTINUITY"
            return result
    latest_at, _ = valid[-1]
    latest_local = parse_timestamp(latest_at).astimezone(LOCAL_TZ)
    devices = [{
        "deviceKey": key,
        "serialSuffix": by_key[key][-1][1],
        "reportedDayKWh": round(by_key[key][-1][2], 3),
        "windowCounterGrowthKWh": round(
            by_key[key][-1][3] - by_key[key][0][3], 3),
        "lastPowerW": by_key[key][-1][4],
    } for key in sorted(keys)]
    result.update({
        # A late-day SEMS+ counter is evidence of a near-final day value;
        # it is still not guaranteed complete without source timestamps.
        "status": "LATE_DAY_COUNTER_OBSERVED"
                  if latest_local.hour >= 23 else "PARTIAL_DAY_COUNTER_OBSERVED",
        "samplePairs": len(valid),
        "lastFetchedAt": latest_at,
        "reportedDayKWh": round(sum(item["reportedDayKWh"] for item in devices), 3),
        "windowCounterGrowthKWh": round(
            sum(item["windowCounterGrowthKWh"] for item in devices), 3),
        "devices": devices,
    })
    return result


def goodwe_cloud_evidence_resource(value):
    """Project SEMS+ meter growth by fetch window; never canonical PV energy.

    Pi fetch time is not an inverter sample timestamp. Quantized counter growth
    cannot be assigned to individual 15-minute energy slots.
    """
    start_local, end_local, _ = _history_period("day", value)
    path = os.environ.get(
        "EMS_PV_CLOUD_HISTORY_FILE",
        "/home/jeroen/ems/runtime/state/pv-cloud-shadow-history-v0.1.json",
    )
    with open(path, encoding="utf-8") as handle:
        history = json.load(handle)
    if (not isinstance(history, dict)
            or history.get("schema") != "EMS_PV_CLOUD_SHADOW_HISTORY_V0.1"
            or not isinstance(history.get("samples"), list)):
        raise RuntimeError("PV_CLOUD_HISTORY_INVALID")

    def valid_number(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0)

    grouped = {}
    first_sample = last_sample = None
    latest_goodwe_quality = None
    count = 0
    for sample in history["samples"]:
        if not isinstance(sample, dict):
            continue
        gw = sample.get("goodwe")
        if (not isinstance(gw, dict)
                or gw.get("status") not in {
                    "RECEIVED_SOURCE_TIME_UNKNOWN",
                    "COUNTER_ONLY_SOURCE_TIME_UNKNOWN",
                }):
            continue
        when = parse_timestamp(gw.get("fetchedAt"))
        if when is None or not start_local <= when.astimezone(LOCAL_TZ) < end_local:
            continue
        inverters = gw.get("inverters")
        if not isinstance(inverters, list):
            continue
        found = {}
        for inverter in inverters:
            if not isinstance(inverter, dict):
                continue
            key = inverter.get("deviceKey")
            suffix = inverter.get("serialSuffix")
            if (not isinstance(key, str) or len(key) != 16
                    or not all(ch in "0123456789abcdef" for ch in key)
                    or not isinstance(suffix, str) or len(suffix) != 4
                    or key in found):
                continue
            found[key] = (suffix, inverter)
        if len(found) != 2:
            continue
        # Counter-only evidence must provide both cumulative measures
        # for both identified inverters, never a fabricated zero watt.
        if gw["status"] == "COUNTER_ONLY_SOURCE_TIME_UNKNOWN" and any(
            not valid_number(inv.get("todayKWh")) or
            not valid_number(inv.get("lifetimeKWh"))
            for _, inv in found.values()
        ):
            continue
        count += 1
        first_sample = min(first_sample, when) if first_sample else when
        if last_sample is None or when >= last_sample:
            last_sample = when
            latest_goodwe_quality = gw["status"]
        for key, (suffix, inverter) in found.items():
            lifetime = inverter.get("lifetimeKWh")
            power = inverter.get("powerW")
            if not valid_number(lifetime):
                continue
            grouped.setdefault(key, []).append({
                "when": when,
                "serialSuffix": suffix,
                "lifetime": float(lifetime),
                "power": float(power) if valid_number(power) else None,
            })

    devices = []
    for key, observations in sorted(grouped.items()):
        observations.sort(key=lambda entry: entry["when"])
        first, last = observations[0], observations[-1]
        monotonic = all(
            b["lifetime"] + 1e-6 >= a["lifetime"]
            for a, b in zip(observations, observations[1:])
        )
        delta = (round(last["lifetime"] - first["lifetime"], 3)
                 if monotonic and len(observations) >= 2 else None)
        devices.append({
            "deviceKey": key,
            "serialSuffix": last["serialSuffix"],
            "firstFetchedAt": first["when"].isoformat(),
            "lastFetchedAt": last["when"].isoformat(),
            "observations": len(observations),
            "lastPowerW": last["power"],
            "lifetimeCounterDeltaKWh": delta,
            "counterEvidence": ("NON_MONOTONIC" if not monotonic else
                                "COUNTER_WINDOW_SOURCE_TIME_UNKNOWN"
                                if delta is not None else "INSUFFICIENT_SAMPLES"),
        })

    age = (max(0, round((datetime.now(timezone.utc) - last_sample).total_seconds() / 60, 1))
           if last_sample else None)
    return {
        "schema": "EMS_WEB_GOODWE_CLOUD_EVIDENCE_V1",
        "dateLocal": value,
        "mode": "READ_ONLY_SHADOW",
        "readOnly": True,
        "controlWrites": False,
        "eligibleForControl": False,
        "eligibleForHouseBalance": False,
        "source": "SEMS_PLUS_WEB_API",
        "timeBasis": "PI_FETCH_TIME_SOURCE_TIME_UNKNOWN",
        "counterResolutionKWh": 0.1,
        "status": (
            "NO_SAMPLES" if not devices else
            "OBSERVED_COUNTER_ONLY_UNVERIFIED_FRESHNESS"
            if latest_goodwe_quality == "COUNTER_ONLY_SOURCE_TIME_UNKNOWN" else
            "OBSERVED_UNVERIFIED_FRESHNESS"
        ),
        "sampleCount": count,
        "firstFetchedAt": first_sample.isoformat() if first_sample else None,
        "lastFetchedAt": last_sample.isoformat() if last_sample else None,
        "ageMinutes": age,
        "devices": devices,
    }


def pv_flex_analysis_resource(value):
    """Return read-only 15-minute PV/flex evidence for one Amsterdam calendar day.

    This is an observability projection only. It does not make planner decisions
    and does not participate in realtime control.
    """
    start_local, end_local, _ = _history_period("day", value)
    start_utc_dt = start_local.astimezone(timezone.utc)
    end_utc_dt = end_local.astimezone(timezone.utc)
    start_utc, end_utc = _utc_text(start_local), _utc_text(end_local)

    slots = {}
    cursor = start_utc_dt
    while cursor < end_utc_dt:
        nxt = min(cursor + timedelta(minutes=15), end_utc_dt)
        slots[_utc_text(cursor)] = {
            "start": cursor.astimezone(LOCAL_TZ).isoformat(),
            "end": nxt.astimezone(LOCAL_TZ).isoformat(),
            "actual": {
                "pvKWh": 0.0, "houseKWh": 0.0, "importKWh": 0.0,
                "exportKWh": 0.0, "pvSelfConsumedKWh": 0.0,
                "coverage": 0.0, "p1Coverage": 0.0, "pvCoverage": 0.0,
            },
            "devices": {"evPowerW": None, "boilerPowerW": None},
            "heatingFlex": {
                "opportunity": False,
                "intent": False,
                "opportunityRooms": [],
                "intentRooms": [],
            },
            "forecast": None,
        }
        cursor = nxt

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        actual_rows = db.execute(
            """
            SELECT start_ts_utc,end_ts_utc,duration_seconds,import_kwh,export_kwh,
                   pv_total_kwh,house_kwh,quality,p1_quality,pv_quality
            FROM house_energy_intervals
            WHERE end_ts_utc > ? AND start_ts_utc < ?
            ORDER BY end_ts_utc
            """,
            (start_utc, end_utc),
        ).fetchall()

        device_rows = db.execute(
            """
            SELECT m.slot_start_utc,d.device_key,k.metric_key,m.value_avg,m.energy_wh,m.quality
            FROM measurements_15m m
            JOIN devices d ON d.id=m.device_id
            JOIN metrics k ON k.id=m.metric_id
            WHERE m.slot_start_utc >= ? AND m.slot_start_utc < ?
              AND (
                (d.device_key='tesla' AND k.metric_key='electrical_power_w') OR
                (d.device_key='boiler' AND k.metric_key='electrical_power_w')
              )
            ORDER BY m.slot_start_utc
            """,
            (start_utc, end_utc),
        ).fetchall()

        # Validation evidence uses a fixed 12-hour lead per target slot.
        # For each slot select the newest archived forecast generated no later
        # than slot_start - 12h. This prevents hindsight and makes forecast
        # errors comparable across the whole day.
        forecast_rows = db.execute(
            """
            SELECT f.slot_start_utc,f.forecast_w,f.confidence,f.model_basis,f.generated_at
            FROM pv_forecast_v2_archive f
            WHERE f.slot_start_utc >= ? AND f.slot_start_utc < ?
              AND f.generated_at = (
                SELECT MAX(f2.generated_at)
                FROM pv_forecast_v2_archive f2
                WHERE f2.slot_start_utc=f.slot_start_utc
                  AND julianday(f2.generated_at) <= julianday(f.slot_start_utc) - (12.0/24.0)
              )
            ORDER BY f.slot_start_utc
            """,
            (start_utc, end_utc),
        ).fetchall()

    p1_covered_seconds = {key: 0.0 for key in slots}
    pv_covered_seconds = {key: 0.0 for key in slots}
    paired_covered_seconds = {key: 0.0 for key in slots}
    gap_count = 0
    discontinuity_count = 0
    for row in actual_rows:
        row_start, row_end = parse_timestamp(row[0]), parse_timestamp(row[1])
        if row_start is None or row_end is None:
            continue
        quality, p1_quality, pv_quality = row[7:10]
        if p1_quality == "gap" or pv_quality == "gap":
            gap_count += 1
        if quality == "discontinuity":
            discontinuity_count += 1
            continue
        p1_valid = p1_quality in {"observed", "held"}
        pv_valid = pv_quality in {"observed", "estimated", "held"}
        if not p1_valid and not pv_valid:
            continue
        row_seconds = max(1.0, (row_end - row_start).total_seconds())
        segment_start = max(row_start, start_utc_dt)
        clipped_end = min(row_end, end_utc_dt)
        while segment_start < clipped_end:
            slot_minute = (segment_start.minute // 15) * 15
            slot_start = segment_start.replace(minute=slot_minute, second=0, microsecond=0)
            slot_end = slot_start + timedelta(minutes=15)
            segment_end = min(clipped_end, slot_end)
            seconds = max(0.0, (segment_end - segment_start).total_seconds())
            key = _utc_text(slot_start)
            item = slots.get(key)
            if item is not None and seconds > 0:
                fraction = seconds / row_seconds
                if p1_valid:
                    for name, index in (("importKWh", 3), ("exportKWh", 4)):
                        if row[index] is not None:
                            item["actual"][name] += float(row[index]) * fraction
                    p1_covered_seconds[key] += seconds
                if pv_valid and row[5] is not None:
                    item["actual"]["pvKWh"] += float(row[5]) * fraction
                    pv_covered_seconds[key] += seconds
                if p1_valid and pv_valid:
                    paired_covered_seconds[key] += seconds
                    if row[6] is not None:
                        item["actual"]["houseKWh"] += float(row[6]) * fraction
            segment_start = segment_end

    for key, item in slots.items():
        actual = item["actual"]
        # Energy-balance definition: PV production not exported in this slot.
        # Keep the signed balance here; clamp only the reported daily direct-use
        # KPI after aggregation so interval-level metering noise cannot inflate it.
        actual["pvSelfConsumedKWh"] = actual["pvKWh"] - actual["exportKWh"] if pv_covered_seconds[key] >= 899.0 and p1_covered_seconds[key] >= 899.0 else None
        actual["p1Coverage"] = min(1.0, p1_covered_seconds[key] / 900.0)
        actual["pvCoverage"] = min(1.0, pv_covered_seconds[key] / 900.0)
        actual["coverage"] = min(actual["p1Coverage"], actual["pvCoverage"])
        for name in ("pvKWh", "houseKWh", "importKWh", "exportKWh", "pvSelfConsumedKWh", "coverage", "p1Coverage", "pvCoverage"):
            if actual[name] is not None:
                actual[name] = round(actual[name], 6)

    for slot_start, device_key, metric_key, value_avg, energy_wh, quality in device_rows:
        dt = parse_timestamp(slot_start)
        if dt is None:
            continue
        key = _utc_text(dt.replace(second=0, microsecond=0))
        item = slots.get(key)
        if item is None or quality not in {"complete", "partial"}:
            continue
        if device_key == "tesla":
            item["devices"]["evPowerW"] = value_avg
        elif device_key == "boiler":
            item["devices"]["boilerPowerW"] = value_avg

    for slot_start, forecast_w, confidence, model_basis, generated_at in forecast_rows:
        dt = parse_timestamp(slot_start)
        if dt is None:
            continue
        key = _utc_text(dt)
        item = slots.get(key)
        if item is not None:
            item["forecast"] = {
                "pvForecastW": round(float(forecast_w), 3),
                "confidence": confidence,
                "modelBasis": model_basis,
                "generatedAt": generated_at,
                "leadMinutes": round((dt - parse_timestamp(generated_at)).total_seconds() / 60.0, 1)
                if parse_timestamp(generated_at) else None,
            }

    # Project the already persisted Heating V0.4 opportunity/step history
    # onto the same 15-minute observability timeline. This is presentation
    # only: no opportunity or intent is reconstructed from current state.
    heating_history_status = "UNAVAILABLE"
    try:
        heating_history = heating_preheat_progression_resource()
    except (OSError, json.JSONDecodeError, ValueError):
        heating_history = None

    def mark_heating_interval(
        room,
        start_value,
        end_value,
        *,
        kind,
        target_c,
        outcome=None,
        reason=None,
    ):
        interval_start = parse_timestamp(start_value)
        interval_end = parse_timestamp(end_value)
        if (
            interval_start is None
            or interval_end is None
            or interval_end <= interval_start
        ):
            return

        for item in slots.values():
            slot_start = parse_timestamp(item["start"])
            slot_end = parse_timestamp(item["end"])
            if slot_start is None or slot_end is None:
                continue
            if max(interval_start, slot_start) >= min(interval_end, slot_end):
                continue

            entry = {
                "key": room.get("key"),
                "displayName": room.get("displayName") or room.get("key"),
                "target_C": target_c,
                "start": start_value,
                "end": end_value,
            }

            if kind == "intent":
                entry["outcome"] = outcome
                entry["reason"] = reason
                field = "intentRooms"
                flag = "intent"
            else:
                field = "opportunityRooms"
                flag = "opportunity"

            bucket = item["heatingFlex"]
            bucket[flag] = True
            if entry not in bucket[field]:
                bucket[field].append(entry)

    if heating_history is not None:
        heating_history_status = "INTEGRATED"

        for room in heating_history.get("rooms") or []:
            for interval in room.get("opportunityHistory") or []:
                mark_heating_interval(
                    room,
                    interval.get("opensAt"),
                    interval.get("closesAt"),
                    kind="opportunity",
                    target_c=interval.get("target_C"),
                )

            for interval in room.get("stepHistory") or []:
                mark_heating_interval(
                    room,
                    interval.get("startedAt"),
                    interval.get("endedAt"),
                    kind="intent",
                    target_c=interval.get("target_C"),
                    outcome=interval.get("outcome"),
                    reason=interval.get("reason"),
                )

            progression = room.get("progression") or {}
            active_target = progression.get("activeStepTarget_C")
            active_started = progression.get("activeStepStartedAt")
            if active_target is not None and active_started:
                mark_heating_interval(
                    room,
                    active_started,
                    heating_history.get("generatedAt"),
                    kind="intent",
                    target_c=active_target,
                    outcome="ACTIVE",
                    reason=progression.get("reason"),
                )

    series = list(slots.values())
    totals = {
        name: round(sum(slot["actual"][name] for slot in series), 6)
        for name in ("pvKWh", "houseKWh", "importKWh", "exportKWh")
    }
    # Daily KPI is independent of historical planner availability and forecast.
    # Reuse the same 95%-paired-coverage and PV-minus-P1-export contract as
    # ems-performance. The API retains its existing day summary keys.
    now_utc = datetime.now(timezone.utc)
    day_complete = now_utc >= end_utc_dt
    required_seconds = max(1.0, (end_utc_dt - start_utc_dt).total_seconds())
    elapsed_seconds = max(
        0.0, (min(now_utc, end_utc_dt) - start_utc_dt).total_seconds()
    )
    paired_seconds = sum(paired_covered_seconds.values())
    accounting = daily_pv_self_use_accounting(
        totals["pvKWh"], totals["exportKWh"], paired_seconds,
        required_seconds if day_complete else elapsed_seconds,
        day_complete,
    )
    self_use_complete = accounting["status"] == "COMPLETE"
    totals["pvSelfConsumedKWh"] = (
        round(max(0.0, totals["pvKWh"] - totals["exportKWh"]), 6)
        if self_use_complete else None
    )
    totals["pvSelfConsumptionRate"] = (
        accounting["rate"] if self_use_complete else None
    )
    # A running day is never represented as a completed daily observation.
    totals["provisionalPvSelfConsumedKWh"] = (
        accounting["selfConsumedKWh"]
        if accounting["status"] == "PROVISIONAL" else None
    )
    totals["provisionalPvSelfConsumptionRate"] = (
        accounting["rate"] if accounting["status"] == "PROVISIONAL" else None
    )
    forecast_energy = sum(
        slot["forecast"]["pvForecastW"] * 0.25 / 1000.0
        for slot in series if slot["forecast"] is not None
    )
    forecast_slots = sum(1 for slot in series if slot["forecast"] is not None)

    return {
        "schema": PV_FLEX_API_SCHEMA,
        "provisionalDailyReport": provisional_daily_report_resource(
            value, series, paired_covered_seconds, now_utc,
        ),
        "mode": "READ_ONLY",
        "controlWrites": False,
        "realtimeAuthority": "P1",
        "period": {
            "kind": "day", "requested": value, "timezone": "Europe/Amsterdam",
            "start": start_local.isoformat(), "end": end_local.isoformat(),
            "slotMinutes": 15,
        },
        "summary": {
            **totals,
            "forecastKWh": round(forecast_energy, 6),
            "forecastSlots": forecast_slots,
        },
        "forecastSelection": {
            "kind": "FIXED_LEAD_12H",
            "targetLeadMinutes": 720,
            "selectionRule": "LATEST_GENERATION_AT_OR_BEFORE_SLOT_MINUS_12H",
            "note": "Per slot selection; no hindsight. Missing slots remain missing rather than being backfilled from a shorter lead.",
        },
        "series": series,
        "resources": {
            "ev": {"actualSource": "measurements_15m:tesla/electrical_power_w"},
            "ww": {"actualSource": "measurements_15m:boiler/electrical_power_w"},
            "heatingFlex": {
                "status": heating_history_status,
                "actualSource": "heating-preheat-progression-shadow-v0.4:opportunityHistory+stepHistory",
                "note": "Persisted V0.4 opportunity/step intervals only; no historical Heating events are inferred.",
            },
        },
        "quality": {
            "pvSelfUseStatus": accounting["status"],
            "pvSelfUsePairedCoverage": accounting["pairedCoverage"],
            "pvSelfUseMethod": accounting["source"],
            "pvSelfUseCompleteDay": day_complete,
            "actualCoverage": round(sum(min(p1_covered_seconds[k], pv_covered_seconds[k]) for k in slots) / max(1.0, (end_utc_dt-start_utc_dt).total_seconds()), 6),
            "p1Coverage": round(sum(p1_covered_seconds.values()) / max(1.0, (end_utc_dt-start_utc_dt).total_seconds()), 6),
            "pvCoverage": round(sum(pv_covered_seconds.values()) / max(1.0, (end_utc_dt-start_utc_dt).total_seconds()), 6),
            "gapCount": gap_count,
            "discontinuityCount": discontinuity_count,
        },
    }


def ev_requirement_resource():
    """Return an allowlisted read-only projection of the Pi EV deadline requirement."""
    source = load_json(EV_DEADLINE_FILE)
    if source.get("schema") != "EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2":
        raise ValueError("EV_REQUIREMENT_SOURCE_INVALID")
    generated_at = source.get("generatedAt")
    if parse_timestamp(generated_at) is None:
        raise ValueError("EV_REQUIREMENT_GENERATED_AT_INVALID")
    deadline_at = source.get("deadlineAt")
    latest_start_at = source.get("latestStartAt")
    for value in (deadline_at, latest_start_at):
        if value is not None and parse_timestamp(value) is None:
            raise ValueError("EV_REQUIREMENT_TIME_INVALID")
    remaining = source.get("remainingKWh")
    max_a = source.get("maxA")
    if remaining is not None and (not isinstance(remaining,(int,float)) or isinstance(remaining,bool) or remaining < 0):
        raise ValueError("EV_REQUIREMENT_REMAINING_INVALID")
    if max_a is not None and (not isinstance(max_a,(int,float)) or isinstance(max_a,bool) or not 6 <= max_a <= 16):
        raise ValueError("EV_REQUIREMENT_MAX_A_INVALID")
    return {
        "schema": EV_REQUIREMENT_API_SCHEMA,
        "generatedAt": generated_at,
        "active": source.get("active") is True,
        "status": source.get("status"),
        "deadlineAt": deadline_at,
        "latestStartAt": latest_start_at,
        "remainingKWh": remaining,
        "maxA": max_a,
        "requestId": source.get("requestId"),
        "presentationOnly": True,
    }


def dynamic_planner_resource():
    """Expose the canonical Dynamic Pi Planner's V1 PV and flex slots, not a second forecast."""
    source = load_json(DYNAMIC_PLAN_FILE)
    if (source.get("schema") != "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3"
            or source.get("mode") != "PURE_SHADOW"
            or source.get("readOnly") is not True
            or source.get("control_writes") is not False):
        raise ValueError("DYNAMIC_PLAN_SOURCE_INVALID")
    generated = parse_timestamp(source.get("generated_at"))
    valid_until = parse_timestamp(source.get("validUntil"))
    now = datetime.now(timezone.utc)
    if (generated is None or valid_until is None
            or generated > now + timedelta(minutes=2)
            or valid_until <= now or valid_until <= generated):
        raise ValueError("DYNAMIC_PLAN_STALE")
    source_slots = source.get("slots")
    if not isinstance(source_slots, list) or len(source_slots) != 96:
        raise ValueError("DYNAMIC_PLAN_SLOT_COUNT_INVALID")
    numeric = ("pvForecastW", "evPlanW", "wwPlanW",
               "gridImportAfterFlexW", "gridExportAfterFlexW")
    exposed = []
    previous = None
    for item in source_slots:
        if not isinstance(item, dict):
            raise ValueError("DYNAMIC_PLAN_SLOT_INVALID")
        start = parse_timestamp(item.get("slot_start_utc"))
        if start is None or (previous is not None and start - previous != timedelta(minutes=15)):
            raise ValueError("DYNAMIC_PLAN_AXIS_INVALID")
        previous = start
        values = {}
        for key in numeric:
            value = item.get(key)
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not 0 <= value <= 50000):
                raise ValueError("DYNAMIC_PLAN_POWER_INVALID")
            values[key] = value
        confidence = item.get("confidence")
        if confidence is not None and (not isinstance(confidence, (int, float))
                                       or isinstance(confidence, bool)
                                       or not 0 <= confidence <= 1):
            raise ValueError("DYNAMIC_PLAN_CONFIDENCE_INVALID")
        ev_reason = item.get("evAllocationReason")
        ww_reason = item.get("wwAllocationReason")
        for reason in (ev_reason, ww_reason):
            if reason is not None and (not isinstance(reason, str) or len(reason) > 120):
                raise ValueError("DYNAMIC_PLAN_REASON_INVALID")
        quooker_w = item.get("quookerPlanW")
        if quooker_w is not None and (not isinstance(quooker_w, (int, float))
                                       or isinstance(quooker_w, bool)
                                       or not 0 <= quooker_w <= 50000):
            raise ValueError("DYNAMIC_PLAN_QUOOKER_INVALID")
        quooker_mode = item.get("quookerMode")
        if quooker_mode not in {"OPPORTUNITY", "FORCED_ON", "OFF"}:
            quooker_mode = None
        quooker_opportunity = item.get("quookerOpportunityAllowed")
        if not isinstance(quooker_opportunity, bool):
            quooker_opportunity = None
        quooker_reason = item.get("quookerAllocationReason")
        if quooker_reason not in (
                None, "PV_FORECAST_OPPORTUNITY",
                "FORCED_WINDOW_FALLBACK", "FORCED_WINDOW_STANDBY"):
            raise ValueError("DYNAMIC_PLAN_QUOOKER_REASON_INVALID")
        exposed.append({
            "quookerPlanW": quooker_w,
            "quookerAllocationReason": quooker_reason,
            "quookerMode": quooker_mode,
            "quookerOpportunityAllowed": quooker_opportunity,
            "start": item["slot_start_utc"],
            **values,
            "confidence": confidence,
            "evReason": ev_reason,
            "wwReason": ww_reason,
        })
    guardrails = source.get("guardrails") or {}
    mode = guardrails.get("wwSourceMode")
    if mode not in {"CV", "BOILER", "UNKNOWN"}:
        mode = None
    return {
        "schema": DYNAMIC_PLAN_API_SCHEMA,
        "generatedAt": source["generated_at"],
        "validUntil": source["validUntil"],
        "status": "SHADOW",
        "controlWrites": False,
        "realtimeAuthority": "P1",
        "forecastSource": "PV_V1_EMBEDDED_IN_DYNAMIC_PLAN",
        "wwSourceMode": mode,
        "slots": exposed,
    }


def pv_forecast_resource():
    """Return allowlisted PV Forecast V2 shadow data for Frontend V2."""
    source = load_json("/home/jeroen/ems/data/pv-forecast-v2.json")
    if source.get("schema") != "EMS_PI_PV_FORECAST_V2" or parse_timestamp(source.get("generatedAt")) is None:
        raise ValueError("PV_FORECAST_SOURCE_INVALID")
    slots=[]
    for item in source.get("slots", []):
        if parse_timestamp(item.get("start")) is None:
            raise ValueError("PV_FORECAST_SLOT_INVALID")
        watts=item.get("pvForecastW")
        if not isinstance(watts,(int,float)) or isinstance(watts,bool) or watts < 0:
            raise ValueError("PV_FORECAST_SLOT_INVALID")
        confidence=item.get("confidence")
        if confidence is not None and (not isinstance(confidence,(int,float)) or isinstance(confidence,bool) or not 0 <= confidence <= 1):
            raise ValueError("PV_FORECAST_CONFIDENCE_INVALID")
        slots.append({"start":item["start"],"pvForecastW":watts,"confidence":confidence})
    if len(slots) != 96:
        raise ValueError("PV_FORECAST_SLOT_COUNT_INVALID")
    return {"schema":PV_FORECAST_API_SCHEMA,"generatedAt":source["generatedAt"],"status":"SHADOW","realtimeAuthority":"P1","slots":slots}


def heating_schedule_resource():
    """Return Honeywell schedule plus canonical effective target semantics."""
    source = load_json(HONEYWELL_SCHEDULE_FILE)
    if source.get("schema") != "EMS_HONEYWELL_SCHEDULE_V0.2":
        raise ValueError("HEATING_SCHEDULE_SOURCE_INVALID")
    schedule_generated_at = source.get("generatedAt")
    if parse_timestamp(schedule_generated_at) is None:
        raise ValueError("HEATING_SCHEDULE_SOURCE_INVALID")

    room_model = load_json(HEATING_ROOM_MODEL_FILE)
    if room_model.get("schema") != "EMS_HEATING_ROOM_MODEL_V0.1":
        raise ValueError("HEATING_ROOM_MODEL_SOURCE_INVALID")
    if room_model.get("mode") != "READ_ONLY" or room_model.get("controlMode") != "SHADOW":
        raise ValueError("HEATING_ROOM_MODEL_MODE_INVALID")
    if room_model.get("baselineAuthority") != "HONEYWELL":
        raise ValueError("HEATING_ROOM_MODEL_AUTHORITY_INVALID")
    model_generated_at = room_model.get("generatedAt")
    if parse_timestamp(model_generated_at) is None:
        raise ValueError("HEATING_ROOM_MODEL_TIME_INVALID")

    model_rooms = {
        room.get("key"): room
        for room in room_model.get("rooms", [])
        if isinstance(room, dict) and isinstance(room.get("key"), str)
    }

    allowed_keys = {"woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe"}
    rooms = []
    for zone in source.get("zones", []):
        key = zone.get("key")
        if key not in allowed_keys:
            continue
        if zone.get("scheduleStatus") != "OK" or not isinstance(zone.get("weeklySchedule"), list):
            continue

        model_room = model_rooms.get(key)
        if not isinstance(model_room, dict) or model_room.get("valid") is not True:
            raise ValueError("HEATING_ROOM_MODEL_ROOMS_INVALID")
        current = model_room.get("current")
        effective = model_room.get("effective")
        if not isinstance(current, dict) or not isinstance(effective, dict):
            raise ValueError("HEATING_ROOM_MODEL_ROOMS_INVALID")

        effective_target = effective.get("currentTarget_C")
        if isinstance(effective_target, bool) or not isinstance(effective_target, (int, float)):
            raise ValueError("HEATING_EFFECTIVE_TARGET_INVALID")
        override_until = effective.get("overrideUntil")
        if override_until is not None and parse_timestamp(override_until) is None:
            raise ValueError("HEATING_OVERRIDE_UNTIL_INVALID")
        if not isinstance(effective.get("preheatAdvanceAllowed"), bool):
            raise ValueError("HEATING_EFFECTIVE_PREHEAT_FLAG_INVALID")

        rooms.append({
            "key": key,
            "displayName": zone.get("displayName") or key,
            "weeklySchedule": zone["weeklySchedule"],
            "effective": {
                "currentTarget_C": float(effective_target),
                "source": effective.get("source"),
                "systemMode": effective.get("systemMode"),
                "setpointMode": effective.get("setpointMode"),
                "overrideUntil": override_until,
                "preheatAdvanceAllowed": effective.get("preheatAdvanceAllowed"),
                "reason": effective.get("reason"),
            },
        })

    if {room["key"] for room in rooms} != allowed_keys:
        raise ValueError("HEATING_SCHEDULE_ROOMS_INVALID")
    return {
        "schema": HEATING_SCHEDULE_API_SCHEMA,
        "generatedAt": model_generated_at,
        "scheduleGeneratedAt": schedule_generated_at,
        "readOnly": True,
        "baselineAuthority": "HONEYWELL",
        "source": "CANONICAL_HONEYWELL_RUNTIME",
        "thermalUnits": {
            "livingArea": ["woonkamer", "eetkamer"],
            "kitchen": ["keuken"],
            "conservatory": ["serre"],
            "douweBedroom": ["douwe_slaapkamer"],
            "douweStudy": ["erker_douwe"],
        },
        "rooms": rooms,
    }

def _heating_target_value(raw):
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None

    target = value.get("targetTemperature_C")
    setpoint_mode = value.get("setpointMode")
    system_mode = value.get("systemMode")
    override_until = value.get("overrideUntil")

    if isinstance(target, bool) or not isinstance(target, (int, float)):
        return None
    if not isinstance(setpoint_mode, str) or not setpoint_mode:
        return None
    if system_mode is not None and not isinstance(system_mode, str):
        return None
    if override_until is not None and parse_timestamp(override_until) is None:
        return None

    return {
        "target_C": float(target),
        "setpointMode": setpoint_mode,
        "overrideUntil": override_until,
        "systemMode": system_mode,
    }


def _heating_target_history(db, allowed_rooms, start, end):
    """Project observed Honeywell target changes without schedule reconstruction."""
    out = {key: [] for key in allowed_rooms}
    start_text = _utc_text(start)
    end_text = _utc_text(end)

    for key in allowed_rooms:
        state_key = f"heating.honeywell_target.{key}"
        prior = db.execute(
            """
            SELECT ts_utc,after_json
            FROM semantic_events
            WHERE state_key=? AND ts_utc <= ?
            ORDER BY ts_utc DESC
            LIMIT 1
            """,
            (state_key, start_text),
        ).fetchone()
        events = db.execute(
            """
            SELECT ts_utc,before_json,after_json,details_json
            FROM semantic_events
            WHERE state_key=? AND ts_utc > ? AND ts_utc <= ?
            ORDER BY ts_utc
            """,
            (state_key, start_text, end_text),
        ).fetchall()

        anchor_at = None
        anchor_value = None

        if prior is not None:
            anchor_value = _heating_target_value(prior[1])
            if anchor_value is not None:
                anchor_at = start
        elif events:
            first_ts, before_json, _after_json, details_json = events[0]
            anchor_value = _heating_target_value(before_json)
            first_observed = None
            try:
                details = json.loads(details_json) if isinstance(details_json, str) else {}
            except json.JSONDecodeError:
                details = {}
            if isinstance(details, dict):
                first_observed = parse_timestamp(details.get("firstObservedAt"))
            first_event = parse_timestamp(first_ts)
            if (
                anchor_value is not None
                and first_observed is not None
                and first_event is not None
                and first_observed <= first_event
            ):
                anchor_at = max(start, first_observed)
        else:
            state = db.execute(
                """
                SELECT value_json,first_observed_at_utc
                FROM semantic_event_state
                WHERE state_key=?
                """,
                (state_key,),
            ).fetchone()
            if state is not None:
                anchor_value = _heating_target_value(state[0])
                first_observed = parse_timestamp(state[1])
                if (
                    anchor_value is not None
                    and first_observed is not None
                    and first_observed <= end
                ):
                    anchor_at = max(start, first_observed)

        if anchor_at is not None and anchor_value is not None:
            out[key].append({
                "at": _utc_text(anchor_at),
                **anchor_value,
            })

        for ts_utc, _before_json, after_json, _details_json in events:
            event_at = parse_timestamp(ts_utc)
            value = _heating_target_value(after_json)
            if event_at is None or value is None:
                continue
            out[key].append({
                "at": _utc_text(event_at),
                **value,
            })

    return out


def heating_temperature_history_resource(*, generated_at=None):
    """Return measured room temperatures plus observed Honeywell target history.

    Room temperature is a six-hour 15-minute measurement projection. Honeywell
    target history is sparse observed semantic evidence for the last seven
    days. No historical target is reconstructed from the weekly schedule.
    """
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("HEATING_TEMPERATURE_HISTORY_TIME_INVALID")
    now = now.astimezone(timezone.utc)
    start = now - timedelta(hours=6)
    target_start = now - timedelta(days=HEATING_TARGET_HISTORY_DAYS)

    allowed_rooms = ("woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe")
    device_keys = tuple(f"honeywell_{key}" for key in allowed_rooms)
    placeholders = ",".join("?" for _ in device_keys)

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True) as db:
        rows = db.execute(
            f"""
            SELECT m.slot_start_utc,d.device_key,m.value_avg,m.value_min,m.value_max,
                   m.sample_count,m.quality
            FROM measurements_15m m
            JOIN devices d ON d.id=m.device_id
            JOIN metrics k ON k.id=m.metric_id
            WHERE m.slot_start_utc >= ? AND m.slot_start_utc <= ?
              AND d.device_key IN ({placeholders})
              AND k.metric_key='room_temperature_c'
              AND m.quality IN ('complete','partial')
            ORDER BY m.slot_start_utc,d.device_key
            """,
            (_utc_text(start), _utc_text(now), *device_keys),
        ).fetchall()
        target_history = _heating_target_history(
            db,
            allowed_rooms,
            target_start,
            now,
        )

    room_map = {
        key: {
            "key": key,
            "displayName": key.replace("_", " ").title(),
            "series": [],
            "targetSeries": target_history[key],
        }
        for key in allowed_rooms
    }

    for slot_start, device_key, avg, minimum, maximum, sample_count, quality in rows:
        key = device_key[len("honeywell_"):] if isinstance(device_key, str) else None
        if key not in room_map or parse_timestamp(slot_start) is None:
            continue
        if avg is None:
            continue
        room_map[key]["series"].append({
            "slotStart": slot_start,
            "avg_C": round(float(avg), 3),
            "min_C": round(float(minimum), 3) if minimum is not None else None,
            "max_C": round(float(maximum), 3) if maximum is not None else None,
            "sampleCount": int(sample_count) if sample_count is not None else None,
            "quality": quality,
        })

    return {
        "schema": HEATING_TEMPERATURE_HISTORY_API_SCHEMA,
        "generatedAt": _utc_text(now),
        "mode": "READ_ONLY",
        "presentationOnly": True,
        "source": "measurements_15m+semantic_events",
        "metric": "room_temperature_c",
        "targetMetric": "observed_honeywell_target_c",
        "period": {
            "timezone": "Europe/Amsterdam",
            "historyMinutes": 360,
            "targetHistoryDays": HEATING_TARGET_HISTORY_DAYS,
            "start": _utc_text(start),
            "targetStart": _utc_text(target_start),
            "end": _utc_text(now),
        },
        "rooms": [room_map[key] for key in allowed_rooms],
    }


def heating_preheat_progression_resource():
    """Return allowlisted read-only Heating Preheat V0.4 progression observability."""
    source = load_json(HEATING_PREHEAT_PROGRESSION_FILE)
    if source.get("schema") != "EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4":
        raise ValueError("HEATING_PREHEAT_PROGRESSION_SOURCE_INVALID")
    if source.get("mode") != "READ_ONLY" or source.get("controlMode") != "SHADOW":
        raise ValueError("HEATING_PREHEAT_PROGRESSION_MODE_INVALID")
    if source.get("controlWrites") is not False or source.get("physicalWriteAllowed") is not False:
        raise ValueError("HEATING_PREHEAT_PROGRESSION_WRITE_BOUNDARY_INVALID")
    if source.get("baselineAuthority") != "HONEYWELL":
        raise ValueError("HEATING_PREHEAT_PROGRESSION_AUTHORITY_INVALID")
    if source.get("eligibilityAuthority") != "EMS_HEATING_PREHEAT_SHADOW_V0.3":
        raise ValueError("HEATING_PREHEAT_PROGRESSION_ELIGIBILITY_INVALID")
    # V0.4 consumes the Production Heating Grant, not Flex Priority directly.
    if source.get("allocationAuthority") != "EMS_PI_DYNAMIC_HEATING_GRANT_V0.1":
        raise ValueError("HEATING_PREHEAT_PROGRESSION_ALLOCATION_INVALID")

    generated_at = source.get("generatedAt")
    if parse_timestamp(generated_at) is None:
        raise ValueError("HEATING_PREHEAT_PROGRESSION_TIME_INVALID")

    freshness = source.get("sourceFreshness")
    policy = source.get("policy")
    if not isinstance(freshness, dict) or not isinstance(policy, dict):
        raise ValueError("HEATING_PREHEAT_PROGRESSION_STRUCTURE_INVALID")
    if policy.get("maxStep_C") != 0.5:
        raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_BOUND_INVALID")
    if policy.get("intentionalGridImportAllowed") is not False:
        raise ValueError("HEATING_PREHEAT_PROGRESSION_GRID_IMPORT_INVALID")
    if policy.get("rollbackBehavior") != "NOT_DEFINED_SHADOW_ONLY":
        raise ValueError("HEATING_PREHEAT_PROGRESSION_ROLLBACK_INVALID")
    if policy.get("opportunityHistoryRetentionHours") != 48:
        raise ValueError("HEATING_PREHEAT_PROGRESSION_OPPORTUNITY_HISTORY_POLICY_INVALID")

    allowed_rooms = {"woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe"}
    allowed_states = {
        "INACTIVE",
        "WAITING_FOR_FRESH_PRIORITY",
        "WAITING_FOR_GRANT",
        "STEP_WAIT",
        "STEP_REACHED",
        "STEP_REACHED_GROUP_WAIT",
        "STEP_HOLD_PRIORITY_UNKNOWN",
        "STEP_HOLD_NO_GRANT",
        "BLOCKED_CV_ASSIST",
        "BLOCKED_CV_STATUS_UNKNOWN",
        "ENDED_BASELINE_HEATING",
        "COMPLETE_TARGET_REACHED",
        "COMPLETE_NO_NEXT_STEP",
    }

    allowed_history_outcomes = {
        "ADVANCED_STEP",
        "TARGET_REACHED",
        "BASELINE_TAKEOVER",
        "ENDED",
        "OPPORTUNITY_CHANGED",
    }

    rooms = []
    for room in source.get("rooms") or []:
        if not isinstance(room, dict) or room.get("preheatScope") is not True:
            continue
        key = room.get("key")
        if key not in allowed_rooms:
            raise ValueError("HEATING_PREHEAT_PROGRESSION_ROOM_INVALID")
        eligibility = room.get("heatingEligibility")
        planner = room.get("planner")
        progression = room.get("progression")
        if not all(isinstance(v, dict) for v in (eligibility, planner, progression)):
            raise ValueError("HEATING_PREHEAT_PROGRESSION_ROOM_INVALID")
        if progression.get("state") not in allowed_states:
            raise ValueError("HEATING_PREHEAT_PROGRESSION_STATE_INVALID")
        if progression.get("physicalWritePerformed") is not False:
            raise ValueError("HEATING_PREHEAT_PROGRESSION_PHYSICAL_WRITE_INVALID")
        for timestamp in (
            room.get("opportunityClosesAt"),
            progression.get("activeStepStartedAt"),
            progression.get("lastTransitionAt"),
        ):
            if timestamp is not None and parse_timestamp(timestamp) is None:
                raise ValueError("HEATING_PREHEAT_PROGRESSION_TIME_INVALID")
        completed = progression.get("completedSteps_C")
        if not isinstance(completed, list):
            raise ValueError("HEATING_PREHEAT_PROGRESSION_COMPLETED_STEPS_INVALID")

        opportunity_history = room.get("opportunityHistory")
        if opportunity_history is None:
            opportunity_history = []
        if not isinstance(opportunity_history, list):
            raise ValueError("HEATING_PREHEAT_PROGRESSION_OPPORTUNITY_HISTORY_INVALID")
        projected_opportunities = []
        for interval in opportunity_history:
            if not isinstance(interval, dict):
                raise ValueError("HEATING_PREHEAT_PROGRESSION_OPPORTUNITY_HISTORY_INVALID")
            opportunity_id = interval.get("opportunityId")
            opens_at = interval.get("opensAt")
            closes_at = interval.get("closesAt")
            target = interval.get("target_C")
            if not isinstance(opportunity_id, str) or not opportunity_id:
                raise ValueError("HEATING_PREHEAT_PROGRESSION_OPPORTUNITY_HISTORY_INVALID")
            if isinstance(target, bool) or not isinstance(target, (int, float)):
                raise ValueError("HEATING_PREHEAT_PROGRESSION_OPPORTUNITY_HISTORY_INVALID")
            opens_dt = parse_timestamp(opens_at)
            closes_dt = parse_timestamp(closes_at)
            if opens_dt is None or closes_dt is None or closes_dt < opens_dt:
                raise ValueError("HEATING_PREHEAT_PROGRESSION_OPPORTUNITY_HISTORY_INVALID")
            projected_opportunities.append({
                "opportunityId": opportunity_id,
                "opensAt": opens_at,
                "closesAt": closes_at,
                "target_C": float(target),
            })

        step_history = room.get("stepHistory")
        if step_history is None:
            step_history = []
        if not isinstance(step_history, list):
            raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
        projected_history = []
        for interval in step_history:
            if not isinstance(interval, dict):
                raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
            opportunity_id = interval.get("opportunityId")
            target = interval.get("target_C")
            started_at = interval.get("startedAt")
            ended_at = interval.get("endedAt")
            outcome = interval.get("outcome")
            reason = interval.get("reason")
            if not isinstance(opportunity_id, str) or not opportunity_id:
                raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
            if isinstance(target, bool) or not isinstance(target, (int, float)):
                raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
            started_dt = parse_timestamp(started_at)
            ended_dt = parse_timestamp(ended_at)
            if started_dt is None or ended_dt is None or ended_dt < started_dt:
                raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
            if outcome not in allowed_history_outcomes:
                raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
            if reason is not None and not isinstance(reason, str):
                raise ValueError("HEATING_PREHEAT_PROGRESSION_STEP_HISTORY_INVALID")
            projected_history.append({
                "opportunityId": opportunity_id,
                "target_C": float(target),
                "startedAt": started_at,
                "endedAt": ended_at,
                "outcome": outcome,
                "reason": reason,
            })

        rooms.append({
            "key": key,
            "displayName": room.get("displayName") or key,
            "group": room.get("group"),
            "opportunityId": room.get("opportunityId"),
            "currentTemperature_C": room.get("currentTemperature_C"),
            "futureHoneywellTarget_C": room.get("futureHoneywellTarget_C"),
            "opportunityClosesAt": room.get("opportunityClosesAt"),
            "heatingEligibility": {
                "state": eligibility.get("state"),
                "reason": eligibility.get("reason"),
            },
            "planner": {
                "domainGrant": planner.get("domainGrant"),
                "priorityReason": planner.get("priorityReason"),
            },
            "opportunityHistory": projected_opportunities,
            "stepHistory": projected_history,
            "progression": {
                "state": progression.get("state"),
                "reason": progression.get("reason"),
                "activeStepTarget_C": progression.get("activeStepTarget_C"),
                "activeStepReached": progression.get("activeStepReached"),
                "activeStepStartedAt": progression.get("activeStepStartedAt"),
                "nextStepTarget_C": progression.get("nextStepTarget_C"),
                "completedSteps_C": list(completed),
                "lastTransition": progression.get("lastTransition"),
                "lastTransitionAt": progression.get("lastTransitionAt"),
                "physicalWritePerformed": False,
            },
        })

    if {room["key"] for room in rooms} != allowed_rooms:
        raise ValueError("HEATING_PREHEAT_PROGRESSION_ROOMS_INCOMPLETE")

    heating_freshness = freshness.get("heating") if isinstance(freshness.get("heating"), dict) else {}
    priority_freshness = freshness.get("priority") if isinstance(freshness.get("priority"), dict) else {}

    return {
        "schema": HEATING_PREHEAT_PROGRESSION_API_SCHEMA,
        "generatedAt": generated_at,
        "mode": "READ_ONLY",
        "controlWrites": False,
        "physicalWriteAllowed": False,
        "sourceFreshness": {
            "heating": {
                "status": heating_freshness.get("status"),
                "ageSeconds": heating_freshness.get("ageSeconds"),
            },
            "priority": {
                "status": priority_freshness.get("status"),
                "ageSeconds": priority_freshness.get("ageSeconds"),
            },
            "priorityConsistentWithHeating": freshness.get("priorityConsistentWithHeating") is True,
        },
        "policy": {
            "maxStep_C": 0.5,
            "stepReachedTolerance_C": policy.get("stepReachedTolerance_C"),
            "advanceOnlyAfterMeasuredStepReached": policy.get("advanceOnlyAfterMeasuredStepReached") is True,
            "groupAdvanceRequiresAllSelectedRoomsReached": policy.get("groupAdvanceRequiresAllSelectedRoomsReached") is True,
            "plannerGrantRequiredForStartAndAdvance": policy.get("plannerGrantRequiredForStartAndAdvance") is True,
            "intentionalGridImportAllowed": False,
            "rollbackBehavior": "NOT_DEFINED_SHADOW_ONLY",
            "stepHistoryRetentionHours": policy.get("stepHistoryRetentionHours"),
            "opportunityHistoryRetentionHours": policy.get("opportunityHistoryRetentionHours"),
        },
        "rooms": rooms,
        "presentationOnly": True,
    }


def flex_priority_shadow_resource():
    """Return allowlisted cross-domain Flex Priority SHADOW observability."""
    source = load_json(FLEX_PRIORITY_SHADOW_FILE)
    if source.get("schema") != "EMS_PI_FLEX_PRIORITY_SHADOW_V0.1":
        raise ValueError("FLEX_PRIORITY_SOURCE_INVALID")
    if source.get("mode") != "READ_ONLY" or source.get("controlMode") != "SHADOW":
        raise ValueError("FLEX_PRIORITY_MODE_INVALID")
    if source.get("controlWrites") is not False:
        raise ValueError("FLEX_PRIORITY_WRITE_BOUNDARY_INVALID")
    generated_at = source.get("generatedAt")
    if parse_timestamp(generated_at) is None:
        raise ValueError("FLEX_PRIORITY_TIME_INVALID")

    policy = source.get("policy")
    heating = source.get("heating")
    ev = source.get("ev")
    decision = source.get("decision")
    if not all(isinstance(v, dict) for v in (policy, heating, ev, decision)):
        raise ValueError("FLEX_PRIORITY_STRUCTURE_INVALID")

    allowed_owner = {"EV", "HEATING", "HOLD_UNKNOWN"}
    allowed_heating = {"SHADOW_GRANT", "HOLD"}
    allowed_ev_role = {"MUST", "PRIMARY_OPPORTUNITY", "RESIDUAL_OPPORTUNITY", "SAFETY_HOLD"}

    if decision.get("priorityOwner") not in allowed_owner:
        raise ValueError("FLEX_PRIORITY_OWNER_INVALID")
    if decision.get("heatingShadowGrant") not in allowed_heating:
        raise ValueError("FLEX_PRIORITY_HEATING_GRANT_INVALID")
    if decision.get("evRole") not in allowed_ev_role:
        raise ValueError("FLEX_PRIORITY_EV_ROLE_INVALID")
    if decision.get("physicalWriteAllowed") is not False:
        raise ValueError("FLEX_PRIORITY_PHYSICAL_WRITE_INVALID")
    if policy.get("powerReservationW") != 0:
        raise ValueError("FLEX_PRIORITY_RESERVATION_INVALID")
    if policy.get("realtimeOpportunityAuthority") != "P1":
        raise ValueError("FLEX_PRIORITY_REALTIME_AUTHORITY_INVALID")

    close_at = heating.get("earliestOpportunityClosesAt")
    latest_start = ev.get("latestSafeStartAt")
    for value in (close_at, latest_start):
        if value is not None and parse_timestamp(value) is None:
            raise ValueError("FLEX_PRIORITY_TIME_INVALID")

    ready_rooms = heating.get("readyRooms")
    if not isinstance(ready_rooms, list):
        raise ValueError("FLEX_PRIORITY_READY_ROOMS_INVALID")

    return {
        "schema": FLEX_PRIORITY_SHADOW_API_SCHEMA,
        "generatedAt": generated_at,
        "mode": "READ_ONLY",
        "controlWrites": False,
        "policy": {
            "strategy": policy.get("strategy"),
            "powerReservationW": 0,
            "realtimeOpportunityAuthority": "P1",
            "evMayUseResidualWhenHeatingFirst": policy.get("evMayUseResidualWhenHeatingFirst") is True,
        },
        "heating": {
            "readyRooms": list(ready_rooms),
            "earliestOpportunityClosesAt": close_at,
        },
        "ev": {
            "deadlineActive": ev.get("deadlineActive") is True,
            "remainingKWh": ev.get("remainingKWh"),
            "urgency": ev.get("urgency"),
            "latestSafeStartAt": latest_start,
        },
        "decision": {
            "priorityOwner": decision.get("priorityOwner"),
            "heatingShadowGrant": decision.get("heatingShadowGrant"),
            "evRole": decision.get("evRole"),
            "reason": decision.get("reason"),
            "appliesOnlyWhenPvOpportunityExists": decision.get("appliesOnlyWhenPvOpportunityExists") is True,
        },
        "presentationOnly": True,
    }


def heating_preheat_shadow_resource():
    """Return an allowlisted read-only Heating Preheat V0.3 shadow projection."""
    source = load_json(HEATING_PREHEAT_SHADOW_FILE)
    if source.get("schema") != "EMS_HEATING_PREHEAT_SHADOW_V0.3":
        raise ValueError("HEATING_PREHEAT_SHADOW_SOURCE_INVALID")
    if source.get("mode") != "READ_ONLY" or source.get("controlMode") != "SHADOW":
        raise ValueError("HEATING_PREHEAT_SHADOW_MODE_INVALID")
    if source.get("controlWrites") is not False:
        raise ValueError("HEATING_PREHEAT_SHADOW_WRITE_BOUNDARY_INVALID")
    generated_at = source.get("generatedAt")
    if parse_timestamp(generated_at) is None:
        raise ValueError("HEATING_PREHEAT_SHADOW_TIME_INVALID")
    if source.get("baselineAuthority") != "HONEYWELL":
        raise ValueError("HEATING_PREHEAT_SHADOW_AUTHORITY_INVALID")

    house = source.get("house")
    cv_guard = source.get("cvGuard")
    policy = source.get("policy")
    if not isinstance(house, dict) or not isinstance(cv_guard, dict) or not isinstance(policy, dict):
        raise ValueError("HEATING_PREHEAT_SHADOW_STRUCTURE_INVALID")

    max_advance_minutes = policy.get("maxAdvanceMinutes")
    if (
        isinstance(max_advance_minutes, bool)
        or not isinstance(max_advance_minutes, (int, float))
        or max_advance_minutes <= 0
    ):
        raise ValueError("HEATING_PREHEAT_SHADOW_MAX_ADVANCE_INVALID")

    rooms = []
    allowed_rooms = {"woonkamer", "eetkamer", "keuken", "serre", "douwe_slaapkamer", "erker_douwe"}
    allowed_states = {
        "NOT_ELIGIBLE",
        "BASELINE_HEATING",
        "PREHEAT_BLOCKED_CV_STATUS_UNKNOWN",
        "PREHEAT_BLOCKED_CV_ASSIST",
        "PREHEAT_READY_FOR_GRANT",
    }
    for room in source.get("rooms") or []:
        if not isinstance(room, dict) or room.get("preheatScope") is not True:
            continue
        key = room.get("key")
        if key not in allowed_rooms:
            raise ValueError("HEATING_PREHEAT_SHADOW_ROOM_INVALID")
        current = room.get("current")
        baseline = room.get("baseline")
        candidate = room.get("candidate")
        shadow = room.get("shadow")
        if not all(isinstance(v, dict) for v in (current, baseline, candidate, shadow)):
            raise ValueError("HEATING_PREHEAT_SHADOW_ROOM_INVALID")
        if shadow.get("state") not in allowed_states:
            raise ValueError("HEATING_PREHEAT_SHADOW_STATE_INVALID")
        for timestamp in (candidate.get("opportunityOpensAt"), candidate.get("opportunityClosesAt")):
            if timestamp is not None and parse_timestamp(timestamp) is None:
                raise ValueError("HEATING_PREHEAT_SHADOW_TIME_INVALID")
        rooms.append({
            "key": key,
            "displayName": room.get("displayName") or key,
            "group": room.get("group"),
            "current": {
                "temperature_C": current.get("temperature_C"),
                "baselineDemand": current.get("baselineDemand") is True,
            },
            "baseline": {
                "currentTargetTemperature_C": baseline.get("currentTargetTemperature_C"),
                "changeAt": baseline.get("changeAt"),
                "targetTemperature_C": baseline.get("targetTemperature_C"),
                "direction": baseline.get("direction"),
            },
            "candidate": {
                "status": candidate.get("status"),
                "reason": candidate.get("reason"),
                "opportunityOpensAt": candidate.get("opportunityOpensAt"),
                "opportunityClosesAt": candidate.get("opportunityClosesAt"),
                "steps_C": candidate.get("steps_C") if isinstance(candidate.get("steps_C"), list) else [],
            },
            "shadow": {
                "state": shadow.get("state"),
                "reason": shadow.get("reason"),
                "plannerGrant": shadow.get("plannerGrant"),
                "activeStepTarget_C": shadow.get("activeStepTarget_C"),
                "activeStepReached": shadow.get("activeStepReached"),
                "nextStepTarget_C": shadow.get("nextStepTarget_C"),
            },
        })

    if {room["key"] for room in rooms} != allowed_rooms:
        raise ValueError("HEATING_PREHEAT_SHADOW_ROOMS_INCOMPLETE")

    return {
        "schema": HEATING_PREHEAT_SHADOW_API_SCHEMA,
        "generatedAt": generated_at,
        "mode": "READ_ONLY",
        "controlWrites": False,
        "baselineAuthority": "HONEYWELL",
        "allocationAuthority": source.get("allocationAuthority"),
        "house": {
            "baselineHeatingDemandPresent": house.get("baselineHeatingDemandPresent") is True,
            "baselineDemandRooms": house.get("baselineDemandRooms")
            if isinstance(house.get("baselineDemandRooms"), list) else [],
        },
        "cvGuard": {
            "status": cv_guard.get("status"),
            "reason": cv_guard.get("reason"),
            "cvActive": cv_guard.get("cvActive")
            if isinstance(cv_guard.get("cvActive"), bool) else None,
            "ageSeconds": cv_guard.get("ageSeconds"),
            "observedAt": cv_guard.get("observedAt"),
            "sourceLastUpdated": cv_guard.get("sourceLastUpdated"),
        },
        "policy": {
            "maxAdvanceMinutes": float(max_advance_minutes),
            "maxStep_C": policy.get("maxStep_C"),
            "cvCheckedEveryIteration": policy.get("cvCheckedEveryIteration") is True,
            "advanceOnlyAfterCurrentStepReached": policy.get("advanceOnlyAfterCurrentStepReached") is True,
            "normalBaselineCvIsNotPreheatFault": policy.get("normalBaselineCvIsNotPreheatFault") is True,
            "purePreheatCvAssistBlocksFurtherSteps": policy.get("purePreheatCvAssistBlocksFurtherSteps") is True,
        },
        "rooms": rooms,
        "presentationOnly": True,
    }


def send_json(handler, status, payload, extra_headers=None):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    if extra_headers:
        for name, value in extra_headers.items():
            handler.send_header(name, value)
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "EMSWebData"
    sys_version = ""

    def do_GET(self):
        path = urlsplit(self.path)
        if path.query:
            send_json(self, 400, {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "QUERY_NOT_ALLOWED"})
            return

        parts = path.path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["web", "history"] and parts[2] in {"day", "week", "month", "year"}:
            try:
                send_json(self, 200, history_resource(parts[2], parts[3]))
            except ValueError:
                send_json(self, 400, {
                    "schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "HISTORY_PERIOD_INVALID",
                })
            except (OSError, sqlite3.Error):
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "RESOURCE_UNAVAILABLE",
                })
            return




        if len(parts) == 5 and parts[:4] == ["web", "analysis", "planner", "day"]:
            try:
                send_json(self, 200, planner_evaluation_resource(parts[4]))
            except ValueError:
                send_json(self, 400, {"schema":"EMS_WEB_ERROR_V1","status":"ERROR","reason":"HISTORY_PERIOD_INVALID"})
            except (OSError, sqlite3.Error):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if len(parts) == 5 and parts[:4] == ["web", "analysis", "performance", "day"]:
            try:
                result = daily_performance_resource(parts[4])
                if result is None:
                    send_json(self, 404, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "DAY_REPORT_NOT_ARCHIVED"})
                else:
                    send_json(self, 200, result)
            except ValueError:
                send_json(self, 400, {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "INVALID_OR_OPEN_DAY"})
            except (OSError, RuntimeError, json.JSONDecodeError):
                send_json(self, 503, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "REPORT_ARCHIVE_UNAVAILABLE"})
            return

        if len(parts) == 6 and parts[:5] == ["web", "analysis", "heating", "temperature", "day"]:
            try:
                result = heating_daily_temperature_resource(parts[5])
                if result is None:
                    send_json(self, 404, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "DAY_REPORT_NOT_ARCHIVED"})
                else:
                    send_json(self, 200, result)
            except ValueError:
                send_json(self, 400, {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "INVALID_OR_OPEN_DAY"})
            except (OSError, RuntimeError, sqlite3.Error, json.JSONDecodeError):
                logging.exception("Heating day timeseries unavailable")
                send_json(self, 503, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "HEATING_SERIES_UNAVAILABLE"})
            return

        if len(parts) == 5 and parts[:4] == ["web", "analysis", "heating", "day"]:
            try:
                result = heating_daily_resource(parts[4])
                if result is None:
                    send_json(self, 404, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "DAY_REPORT_NOT_ARCHIVED"})
                else:
                    send_json(self, 200, result)
            except ValueError:
                send_json(self, 400, {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "INVALID_OR_OPEN_DAY"})
            except (OSError, RuntimeError, json.JSONDecodeError):
                send_json(self, 503, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "REPORT_ARCHIVE_UNAVAILABLE"})
            return

        if len(parts) == 5 and parts[:4] == ["web", "analysis", "goodwe", "day"]:
            try:
                send_json(self, 200, goodwe_daily_counter_resource(parts[4]))
            except ValueError:
                send_json(self, 400, {"schema":"EMS_WEB_ERROR_V1","status":"ERROR","reason":"HISTORY_PERIOD_INVALID"})
            except (sqlite3.Error, OSError):
                logging.exception("GoodWe daily counter resource unavailable")
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if len(parts) == 5 and parts[:4] == ["web", "analysis", "pv-cloud", "day"]:
            try:
                send_json(self, 200, goodwe_cloud_evidence_resource(parts[4]))
            except json.JSONDecodeError:
                send_json(self, 503, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "RESOURCE_UNAVAILABLE"})
            except ValueError:
                send_json(self, 400, {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "HISTORY_PERIOD_INVALID"})
            except (OSError, RuntimeError):
                send_json(self, 503, {"schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "RESOURCE_UNAVAILABLE"})
            return

        if len(parts) == 5 and parts[:4] == ["web", "analysis", "pv-flex", "day"]:
            try:
                send_json(self, 200, pv_flex_analysis_resource(parts[4]))
            except ValueError:
                send_json(self, 400, {
                    "schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "HISTORY_PERIOD_INVALID",
                })
            except (OSError, sqlite3.Error):
                # This endpoint has intermittently returned 503 while its
                # direct read-only projection succeeds. Preserve the public
                # error contract; keep cause/traceback private in journald.
                logging.exception("PV & Flex 503 while reading day %s", parts[4])
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "RESOURCE_UNAVAILABLE",
                })
            return

        if path.path == "/web/planner/heating-preheat-progression-shadow":
            try:
                send_json(self, 200, heating_preheat_progression_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/planner/flex-priority-shadow":
            try:
                send_json(self, 200, flex_priority_shadow_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/planner/heating-preheat-shadow":
            try:
                send_json(self, 200, heating_preheat_shadow_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/heating/temperature-history":
            try:
                send_json(self, 200, heating_temperature_history_resource())
            except (OSError, sqlite3.Error, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/heating/schedule":
            try:
                send_json(self, 200, heating_schedule_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/planner/ev-requirement":
            try:
                send_json(self, 200, ev_requirement_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/planner/current":
            try:
                send_json(self, 200, dynamic_planner_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/planner/pv-forecast":
            try:
                send_json(self, 200, pv_forecast_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
            return

        if path.path == "/web/live/quooker":
            try:
                send_json(self, 200, live_quooker_resource())
            except (OSError, sqlite3.Error):
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1",
                    "status": "UNAVAILABLE",
                    "reason": "RESOURCE_UNAVAILABLE",
                })
            return

        if path.path == "/web/state/current":
            try:
                send_json(self, 200, state_current_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1",
                    "status": "UNAVAILABLE",
                    "reason": "RESOURCE_UNAVAILABLE",
                })
            return

        if path.path == "/web/commands/current":
            try:
                send_json(self, 200, commands_current_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1",
                    "status": "UNAVAILABLE",
                    "reason": "RESOURCE_UNAVAILABLE",
                })
            return

        if path.path == "/web/ww/seasonal-advice":
            try:
                send_json(self, 200, seasonal_advice_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1",
                    "status": "UNAVAILABLE",
                    "reason": "RESOURCE_UNAVAILABLE",
                })
            return

        send_json(self, 404, {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "NOT_FOUND"})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        self.method_not_allowed()

    def do_PUT(self):
        self.method_not_allowed()

    def do_PATCH(self):
        self.method_not_allowed()

    def do_DELETE(self):
        self.method_not_allowed()

    def do_OPTIONS(self):
        self.method_not_allowed()

    def method_not_allowed(self):
        send_json(
            self,
            405,
            {"schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "METHOD_NOT_ALLOWED"},
            {"Allow": "GET, HEAD"},
        )

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

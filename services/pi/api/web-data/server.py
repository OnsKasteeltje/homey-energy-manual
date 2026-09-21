"""Read-only operational data API for EMS Frontend V2.

This service is presentation transport only. It contains no EMS policy and no
control/device write path.
"""

import json
import os
import sqlite3
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
ENERGY_STATE_FILE = os.environ.get(
    "EMS_ENERGY_STATE_FILE",
    "/home/jeroen/ems/data/energy-state-v2.json",
)
TESLA_COMMAND_FILE = os.environ.get(
    "EMS_TESLA_COMMAND_FILE",
    "/home/jeroen/ems/repo/homey-energy-manual/docs/data/tesla-deadline-command.json",
)
EMS_SETTINGS_COMMAND_FILE = os.environ.get(
    "EMS_SETTINGS_COMMAND_FILE",
    "/home/jeroen/ems/repo/homey-energy-manual/docs/data/ems-settings-command.json",
)
HISTORY_DB = os.environ.get("EMS_HISTORY_DB", "/home/jeroen/ems/data/ems-history.sqlite")
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

API_SCHEMA = "EMS_WEB_WW_SEASONAL_ADVICE_V1"
STATE_API_SCHEMA = "EMS_WEB_STATE_CURRENT_V1"
COMMANDS_API_SCHEMA = "EMS_WEB_COMMANDS_CURRENT_V1"
HISTORY_API_SCHEMA = "EMS_WEB_HISTORY_V1"
PV_FLEX_API_SCHEMA = "EMS_WEB_PV_FLEX_ANALYSIS_V1"
PV_FORECAST_API_SCHEMA = "EMS_WEB_PV_FORECAST_V2"
EV_REQUIREMENT_API_SCHEMA = "EMS_WEB_EV_REQUIREMENT_V1"
HEATING_SCHEDULE_API_SCHEMA = "EMS_WEB_HEATING_SCHEDULE_V1"
HONEYWELL_SCHEDULE_FILE = os.environ.get("EMS_HONEYWELL_SCHEDULE_FILE", "/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-schedule.json")
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



def state_current_resource():
    """Return the allowlisted Live V2 projection of canonical Pi energy state."""
    source = load_json(ENERGY_STATE_FILE)
    meta = source.get("meta")
    if not isinstance(meta, dict) or parse_timestamp(meta.get("generated_at")) is None:
        raise ValueError("SOURCE_GENERATED_AT_INVALID")

    allowed_top = {
        "meta": ("generated_at", "state_age_sec"),
        "grid": ("power_w",),
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
    return result


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
    if not isinstance(current_soc, (int, float)) or isinstance(current_soc, bool) or not 0 <= current_soc <= 99:
        raise ValueError("TESLA_CURRENT_SOC_INVALID")
    if not isinstance(target_soc, (int, float)) or isinstance(target_soc, bool) or not 1 <= target_soc <= 100:
        raise ValueError("TESLA_TARGET_SOC_INVALID")
    if target_soc <= current_soc:
        raise ValueError("TESLA_TARGET_SOC_INVALID")
    if not isinstance(max_a, (int, float)) or isinstance(max_a, bool) or not 6 <= max_a <= 16:
        raise ValueError("TESLA_MAX_A_INVALID")
    if not isinstance(deadline, str) or not deadline:
        raise ValueError("TESLA_DEADLINE_INVALID")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("TESLA_REQUEST_ID_INVALID")

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

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro&immutable=1", uri=True) as db:
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
                    bucket["coveredSeconds"] += int(round(segment_seconds))
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
                "coverage": 0.0,
            },
            "devices": {"evPowerW": None, "boilerPowerW": None},
            "forecast": None,
        }
        cursor = nxt

    with sqlite3.connect(f"file:{HISTORY_DB}?mode=ro&immutable=1", uri=True) as db:
        actual_rows = db.execute(
            """
            SELECT start_ts_utc,end_ts_utc,duration_seconds,import_kwh,export_kwh,
                   pv_total_kwh,house_kwh,quality
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

    covered_seconds = {key: 0.0 for key in slots}
    gap_count = 0
    discontinuity_count = 0
    for row in actual_rows:
        row_start, row_end = parse_timestamp(row[0]), parse_timestamp(row[1])
        if row_start is None or row_end is None:
            continue
        quality = row[7]
        if quality == "gap":
            gap_count += 1
            continue
        if quality != "observed":
            discontinuity_count += 1
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
                for name, index in (
                    ("importKWh", 3), ("exportKWh", 4),
                    ("pvKWh", 5), ("houseKWh", 6),
                ):
                    if row[index] is not None:
                        item["actual"][name] += float(row[index]) * fraction
                covered_seconds[key] += seconds
            segment_start = segment_end

    for key, item in slots.items():
        actual = item["actual"]
        # Energy-balance definition: PV production not exported in this slot.
        # Keep the signed balance here; clamp only the reported daily direct-use
        # KPI after aggregation so interval-level metering noise cannot inflate it.
        actual["pvSelfConsumedKWh"] = actual["pvKWh"] - actual["exportKWh"]
        actual["coverage"] = min(1.0, covered_seconds[key] / 900.0)
        for name in ("pvKWh", "houseKWh", "importKWh", "exportKWh", "pvSelfConsumedKWh", "coverage"):
            actual[name] = round(actual[name], 6)

    for slot_start, device_key, metric_key, value_avg, energy_wh, quality in device_rows:
        dt = parse_timestamp(slot_start)
        if dt is None:
            continue
        key = _utc_text(dt.replace(second=0, microsecond=0))
        item = slots.get(key)
        if item is None or quality != "observed":
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

    series = list(slots.values())
    totals = {
        name: round(sum(slot["actual"][name] for slot in series), 6)
        for name in ("pvKWh", "houseKWh", "importKWh", "exportKWh")
    }
    totals["pvSelfConsumedKWh"] = round(max(0.0, totals["pvKWh"] - totals["exportKWh"]), 6)
    forecast_energy = sum(
        slot["forecast"]["pvForecastW"] * 0.25 / 1000.0
        for slot in series if slot["forecast"] is not None
    )
    forecast_slots = sum(1 for slot in series if slot["forecast"] is not None)

    return {
        "schema": PV_FLEX_API_SCHEMA,
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
                "status": "SOURCE_NOT_YET_INTEGRATED",
                "actualSource": None,
                "note": "No Heating Flex events are inferred or fabricated.",
            },
        },
        "quality": {
            "actualCoverage": round(sum(covered_seconds.values()) / max(1.0, (end_utc_dt-start_utc_dt).total_seconds()), 6),
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
    """Return an allowlisted read-only projection of the canonical Honeywell schedule."""
    source = load_json(HONEYWELL_SCHEDULE_FILE)
    if source.get("schema") != "EMS_HONEYWELL_SCHEDULE_V0.2":
        raise ValueError("HEATING_SCHEDULE_SOURCE_INVALID")
    generated_at = source.get("generatedAt")
    if parse_timestamp(generated_at) is None:
        raise ValueError("HEATING_SCHEDULE_SOURCE_INVALID")
    allowed_keys = {"woonkamer", "eetkamer", "keuken", "serre"}
    rooms = []
    for zone in source.get("zones", []):
        if zone.get("key") not in allowed_keys:
            continue
        if zone.get("scheduleStatus") != "OK" or not isinstance(zone.get("weeklySchedule"), list):
            continue
        rooms.append({
            "key": zone["key"],
            "displayName": zone.get("displayName") or zone["key"],
            "weeklySchedule": zone["weeklySchedule"],
        })
    if {room["key"] for room in rooms} != allowed_keys:
        raise ValueError("HEATING_SCHEDULE_ROOMS_INVALID")
    return {
        "schema": HEATING_SCHEDULE_API_SCHEMA,
        "generatedAt": generated_at,
        "readOnly": True,
        "baselineAuthority": "HONEYWELL",
        "source": "CANONICAL_HONEYWELL_RUNTIME",
        "thermalUnits": {
            "livingArea": ["woonkamer", "eetkamer"],
            "kitchen": ["keuken"],
            "conservatory": ["serre"],
        },
        "rooms": rooms,
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




        if len(parts) == 5 and parts[:4] == ["web", "analysis", "pv-flex", "day"]:
            try:
                send_json(self, 200, pv_flex_analysis_resource(parts[4]))
            except ValueError:
                send_json(self, 400, {
                    "schema": "EMS_WEB_ERROR_V1", "status": "ERROR", "reason": "HISTORY_PERIOD_INVALID",
                })
            except (OSError, sqlite3.Error):
                send_json(self, 503, {
                    "schema": "EMS_WEB_ERROR_V1", "status": "UNAVAILABLE", "reason": "RESOURCE_UNAVAILABLE",
                })
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

        if path.path == "/web/planner/pv-forecast":
            try:
                send_json(self, 200, pv_forecast_resource())
            except (OSError, json.JSONDecodeError, ValueError):
                send_json(self, 503, {"schema":"EMS_WEB_ERROR_V1","status":"UNAVAILABLE","reason":"RESOURCE_UNAVAILABLE"})
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

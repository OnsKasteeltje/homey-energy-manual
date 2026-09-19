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

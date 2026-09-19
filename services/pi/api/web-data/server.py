"""Read-only operational data API for EMS Frontend V2.

This service is presentation transport only. It contains no EMS policy and no
control/device write path.
"""

import json
import os
from datetime import datetime, timezone
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

API_SCHEMA = "EMS_WEB_WW_SEASONAL_ADVICE_V1"
STATE_API_SCHEMA = "EMS_WEB_STATE_CURRENT_V1"
COMMANDS_API_SCHEMA = "EMS_WEB_COMMANDS_CURRENT_V1"
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
        "pv": ("total_w",),
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
    result["balance"] = {
        "control_gate": {
            "grid_measurement_valid": gate.get("grid_measurement_valid")
            if isinstance(gate, dict) else None
        }
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

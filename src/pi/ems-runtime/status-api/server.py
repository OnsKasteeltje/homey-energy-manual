import json
import os
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "0.0.0.0"
PORT = 3100

START_TIME = time.time()

PV_FILE = "/home/jeroen/ems/data/pv-forecast.json"
WEATHER_FILE = "/home/jeroen/ems/data/weather-forecast.json"
QUATT_FILE = "/home/jeroen/ems/data/quatt-forecast.json"
WW_FILE = "/home/jeroen/ems/data/ww-plan.json"

STALE_AFTER_SECONDS = 25 * 60


def git_revision():
    try:
        return subprocess.check_output(
            [
                "git",
                "-C",
                "/home/jeroen/ems/repo/homey-energy-manual",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        return "unknown"


def parse_utc_timestamp(value):
    if not value or not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    except Exception:
        return None


def forecast_status(path, expected_schema):
    result = {
        "status": "missing",
        "age_seconds": None,
        "generated_at": None,
        "slot_count": None,
    }

    if not os.path.exists(path):
        return result

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        result["status"] = "invalid"
        return result

    if data.get("schema") != expected_schema:
        result["status"] = "invalid"
        return result

    if data.get("mode") != "shadow":
        result["status"] = "invalid"
        return result

    if data.get("control_writes") is not False:
        result["status"] = "invalid"
        return result

    generated_at = data.get("generated_at")
    generated_dt = parse_utc_timestamp(generated_at)

    if generated_dt is None:
        result["status"] = "invalid"
        return result

    slots = data.get("slots")
    if not isinstance(slots, list):
        result["status"] = "invalid"
        return result

    slot_count = len(slots)

    declared_slot_count = data.get("slot_count")
    if declared_slot_count is not None and declared_slot_count != slot_count:
        result["status"] = "invalid"
        result["slot_count"] = slot_count
        return result

    if slot_count != 96:
        result["status"] = "invalid"
        result["slot_count"] = slot_count
        return result

    age_seconds = max(
        0,
        int((datetime.now(timezone.utc) - generated_dt).total_seconds())
    )

    result["generated_at"] = generated_at
    result["age_seconds"] = age_seconds
    result["slot_count"] = slot_count

    if age_seconds > STALE_AFTER_SECONDS:
        result["status"] = "stale"
    else:
        result["status"] = "ok"

    return result


def ww_plan_status(path):
    result = forecast_status(path, "EMS_PI_WW_PLAN_V0.2")
    result["planned_kwh"] = None

    if result["status"] in ("ok", "stale"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            result["planned_kwh"] = round(
                sum(
                    float(slot.get("allocatedKWh") or 0)
                    for slot in data.get("slots", [])
                ),
                3,
            )
        except Exception:
            result["status"] = "invalid"
            result["planned_kwh"] = None

    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        pv = forecast_status(
            PV_FILE,
            "EMS_PI_PV_FORECAST_V0.1"
        )

        weather = forecast_status(
            WEATHER_FILE,
            "EMS_PI_WEATHER_FORECAST_V0.1"
        )

        quatt = forecast_status(
            QUATT_FILE,
            "EMS_PI_QUATT_FORECAST_V0.2"
        )

        ww = ww_plan_status(WW_FILE)

        overall_status = (
            "ok"
            if (
                pv["status"] == "ok"
                and weather["status"] == "ok"
                and quatt["status"] == "ok"
                and ww["status"] == "ok"
            )
            else "degraded"
        )

        response = {
            "status": overall_status,
            "service": "ems-status-api",
            "mode": "shadow",
            "control_writes": False,
            "git_revision": git_revision(),
            "uptime_seconds": int(time.time() - START_TIME),

            "pv_forecast_status": pv["status"],
            "pv_forecast_age_seconds": pv["age_seconds"],
            "pv_forecast_generated_at": pv["generated_at"],
            "pv_forecast_slot_count": pv["slot_count"],

            "weather_forecast_status": weather["status"],
            "weather_forecast_age_seconds": weather["age_seconds"],
            "weather_forecast_generated_at": weather["generated_at"],
            "weather_forecast_slot_count": weather["slot_count"],

            "quatt_forecast_status": quatt["status"],
            "quatt_forecast_age_seconds": quatt["age_seconds"],
            "quatt_forecast_generated_at": quatt["generated_at"],
            "quatt_forecast_slot_count": quatt["slot_count"],
            "ww_plan_status": ww["status"],
            "ww_plan_age_seconds": ww["age_seconds"],
            "ww_plan_generated_at": ww["generated_at"],
            "ww_plan_slot_count": ww["slot_count"],
            "ww_planned_kwh": ww["planned_kwh"],
        }

        body = json.dumps(
            response,
            separators=(",", ":")
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()

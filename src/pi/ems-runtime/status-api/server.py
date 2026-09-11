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
DYNAMIC_PLAN_FILE = "/home/jeroen/ems/data/dynamic-shadow-plan.json"
CONTROL_POLICY_FILE = "/home/jeroen/ems/runtime/planner/control-authority.json"

STALE_AFTER_SECONDS = 25 * 60


def git_revision():
    try:
        return subprocess.check_output(
            ["git", "-C", "/home/jeroen/ems/repo/homey-energy-manual", "rev-parse", "--short", "HEAD"],
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        return "unknown"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_utc_timestamp(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def forecast_status(path, expected_schema):
    result = {"status": "missing", "age_seconds": None, "generated_at": None, "slot_count": None}
    if not os.path.exists(path):
        return result
    try:
        data = load_json(path)
    except Exception:
        result["status"] = "invalid"
        return result
    if data.get("schema") != expected_schema or data.get("mode") != "shadow" or data.get("control_writes") is not False:
        result["status"] = "invalid"
        return result
    generated_at = data.get("generated_at")
    generated_dt = parse_utc_timestamp(generated_at)
    slots = data.get("slots")
    if generated_dt is None or not isinstance(slots, list):
        result["status"] = "invalid"
        return result
    slot_count = len(slots)
    if data.get("slot_count") not in (None, slot_count) or slot_count != 96:
        result["status"] = "invalid"
        result["slot_count"] = slot_count
        return result
    age_seconds = max(0, int((datetime.now(timezone.utc) - generated_dt).total_seconds()))
    result.update({"generated_at": generated_at, "age_seconds": age_seconds, "slot_count": slot_count})
    result["status"] = "stale" if age_seconds > STALE_AFTER_SECONDS else "ok"
    return result


def ww_plan_status(path):
    result = forecast_status(path, "EMS_PI_WW_PLAN_V0.2")
    result["planned_kwh"] = None
    if result["status"] in ("ok", "stale"):
        try:
            data = load_json(path)
            result["planned_kwh"] = round(sum(float(slot.get("allocatedKWh") or 0) for slot in data.get("slots", [])), 3)
        except Exception:
            result["status"] = "invalid"
    return result


def current_control_command():
    now = datetime.now(timezone.utc)
    policy = load_json(CONTROL_POLICY_FILE)
    plan = load_json(DYNAMIC_PLAN_FILE)

    if policy.get("schema") != "EMS_CONTROL_AUTHORITY_V1.0":
        raise ValueError("CONTROL_POLICY_SCHEMA")
    if policy.get("plannerOwner") != "PI" or policy.get("executor") != "HOMEY":
        raise ValueError("CONTROL_AUTHORITY_MISMATCH")
    if policy.get("executionEnabled") is not True or policy.get("legacyHomeyPlannerAuthority") is not False:
        raise ValueError("CONTROL_AUTHORITY_NOT_LIVE")
    if policy.get("contractMode") != "FIXED" or policy.get("contractId") != "ENGIE_3Y_2026_2029":
        raise ValueError("CONTROL_POLICY_CONTRACT_MISMATCH")

    if plan.get("schema") != policy.get("plannerSourceSchema"):
        raise ValueError("PLAN_SCHEMA_MISMATCH")
    if plan.get("plannerOwner") != "PI" or plan.get("readOnly") is not True or plan.get("control_writes") is not False:
        raise ValueError("PLAN_OWNERSHIP_BOUNDARY")
    contract = plan.get("contract") or {}
    if contract.get("mode") != "FIXED" or contract.get("id") != "ENGIE_3Y_2026_2029" or contract.get("dynamicPricingUsedForProduction") is not False:
        raise ValueError("PLAN_CONTRACT_MISMATCH")
    freshness = plan.get("inputFreshness") or {}
    if freshness.get("status") != "PASS" or freshness.get("failClosed") is not True:
        raise ValueError("PLAN_INPUT_FRESHNESS")

    valid_until = parse_utc_timestamp(plan.get("validUntil"))
    if valid_until is None or valid_until <= now:
        raise ValueError("PLAN_STALE")

    current = None
    for slot in plan.get("slots") or []:
        start = parse_utc_timestamp(slot.get("slot_start_utc"))
        end = parse_utc_timestamp(slot.get("slot_end_utc"))
        if start is not None and end is not None and start <= now < end:
            current = slot
            break
    if current is None:
        raise ValueError("NO_CURRENT_SLOT")

    slot_end = parse_utc_timestamp(current.get("slot_end_utc"))
    command_valid_until = min(valid_until, slot_end)
    ev_w = max(0, int(round(float(current.get("evPlanW") or 0))))
    ww_w = max(0, int(round(float(current.get("wwPlanW") or 0))))

    return {
        "schema": "EMS_PI_CONTROL_COMMAND_V0.1",
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "validUntil": command_valid_until.isoformat().replace("+00:00", "Z"),
        "plannerOwner": "PI",
        "plannerSchema": plan.get("schema"),
        "plannerGeneratedAt": plan.get("generated_at"),
        "executor": "HOMEY",
        "contract": {"mode": "FIXED", "id": "ENGIE_3Y_2026_2029"},
        "slot": {"start": current.get("slot_start_utc"), "end": current.get("slot_end_utc")},
        "targets": {
            "ev": {
                "target_W": ev_w,
                "target_A": current.get("evPlanA"),
                "reason": current.get("evAllocationReason") or "PI_DYNAMIC_SLOT"
            },
            "ww": {
                "target_W": ww_w,
                "target_on": ww_w > 0,
                "reason": current.get("wwAllocationReason") or current.get("wwReason") or "PI_DYNAMIC_SLOT"
            },
            "battery": {"target_W": 0}
        },
        "safety": {
            "failClosed": True,
            "stalePlanRejected": True,
            "plannerDoesNotWriteDevices": True,
            "legacyHomeyPlannerAuthority": False
        }
    }


def send_json(handler, status, payload):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/control/current":
            try:
                send_json(self, 200, current_control_command())
            except Exception as exc:
                send_json(self, 503, {
                    "schema": "EMS_PI_CONTROL_COMMAND_V0.1",
                    "status": "FAIL_CLOSED",
                    "reason": str(exc),
                    "plannerOwner": "PI",
                    "targets": {"ev": {"target_W": 0}, "ww": {"target_on": False}, "battery": {"target_W": 0}}
                })
            return

        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        pv = forecast_status(PV_FILE, "EMS_PI_PV_FORECAST_V0.1")
        weather = forecast_status(WEATHER_FILE, "EMS_PI_WEATHER_FORECAST_V0.2")
        quatt = forecast_status(QUATT_FILE, "EMS_PI_QUATT_FORECAST_V0.2")
        ww = ww_plan_status(WW_FILE)
        overall_status = "ok" if all(x["status"] == "ok" for x in (pv, weather, quatt, ww)) else "degraded"
        try:
            control = current_control_command()
            control_status = "ok"
            control_valid_until = control.get("validUntil")
        except Exception as exc:
            control_status = f"blocked:{exc}"
            control_valid_until = None

        send_json(self, 200, {
            "status": overall_status,
            "service": "ems-status-api",
            "mode": "pi-live-authority",
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
            "control_authority": "PI",
            "control_endpoint_status": control_status,
            "control_valid_until": control_valid_until
        })

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    HTTPServer((HOST, PORT), Handler).serve_forever()

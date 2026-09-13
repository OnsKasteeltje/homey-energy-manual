import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
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
SLOT_MINUTES = 15
CONTROL_POLICY_SCHEMA = "EMS_CONTROL_AUTHORITY_V1.0"
PI_PLAN_SCHEMA = "EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3"
EV_MIN_A = 6
EV_MAX_A = 16


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


def slot_bounds(slot):
    start = parse_utc_timestamp(slot.get("slot_start_utc"))
    if start is None:
        return None, None
    end = parse_utc_timestamp(slot.get("slot_end_utc"))
    if end is None:
        end = start + timedelta(minutes=SLOT_MINUTES)
    return start, end


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


def ev_realtime_envelope(plan, current, ev_w, ww_w):
    """Expose a bounded realtime EV opportunity envelope without changing targets.

    The Pi remains strategy/authority owner. The envelope answers whether Homey
    may *in shadow* evaluate residual-PV EV modulation in the current slot. It
    is deliberately independent of whether the 15-minute planner selected an
    EV target: otherwise a forecast miss could never be recovered from live P1.

    WW remains reserved exactly as planned. Homey must use net P1 export after
    WW and may add back EV actual power only; WW power is never added back.
    Deadline-required slots remain owned by the canonical deadline target and
    are not realtime-opportunity slots.
    """
    reason = str(current.get("evAllocationReason") or "")
    tesla_plan = plan.get("tesla") or {}
    tesla_connected = tesla_plan.get("connectedNow") is True
    deadline_required = (
        current.get("evDeadlineRequired") is True
        or reason == "DEADLINE_REQUIRED"
    )

    deadline_plan = tesla_plan.get("deadlinePlan") or {}
    deadline_active = deadline_plan.get("active") is True
    deadline_max_a = deadline_plan.get("maxA")
    try:
        deadline_max_a = int(round(float(deadline_max_a))) if deadline_max_a is not None else None
    except (TypeError, ValueError):
        deadline_max_a = None

    hard_max_a = EV_MAX_A
    policy_valid = tesla_connected and not deadline_required
    block_reason = None

    if not tesla_connected:
        policy_valid = False
        block_reason = "TESLA_NOT_CONNECTED_AT_PLAN_BUILD"
    elif deadline_required:
        policy_valid = False
        block_reason = "DEADLINE_TARGET_OWNS_SLOT"

    if deadline_active:
        if deadline_max_a is None or not (EV_MIN_A <= deadline_max_a <= EV_MAX_A):
            policy_valid = False
            hard_max_a = 0
            block_reason = "INVALID_DEADLINE_MAX_A"
        else:
            hard_max_a = deadline_max_a

    planner_target_a = current.get("evPlanA")
    try:
        planner_target_a = int(round(float(planner_target_a))) if planner_target_a is not None else 0
    except (TypeError, ValueError):
        planner_target_a = 0

    return {
        "schema": "EMS_PI_EV_REALTIME_ENVELOPE_V0.3",
        "shadowOnly": False,
        "productionConsumerAllowed": True,
        "executionOwner": "HOMEY_BOUNDED_REALTIME_WITHIN_PI_ENVELOPE",
        "allowed": policy_valid,
        "mode": "PV_OPPORTUNITY" if policy_valid else "DISABLED",
        "min_A": EV_MIN_A if policy_valid else 0,
        "max_A": hard_max_a if policy_valid else 0,
        "plannerTarget_A": planner_target_a,
        "plannerTarget_W": ev_w,
        "plannerReason": reason or "PI_DYNAMIC_SLOT",
        "plannerSelectedOpportunity": (
            ev_w > 0
            and (
                (reason.startswith("DYNAMIC_PV_") and "OPPORTUNITY" in reason)
                or reason == "DYNAMIC_PV_PEAK_ABSORBER"
            )
        ),
        "policyBasis": "PI_POLICY_ALLOWS_REALTIME_PV_CAPTURE_INDEPENDENT_OF_SLOT_TARGET",
        "blockReason": block_reason,
        "wwReserved_W": ww_w,
        "wwMustRemainUnchanged": True,
        "deadlineActive": deadline_active,
        "deadlineMax_A": deadline_max_a,
        "deadlineRequiredSlot": deadline_required,
        "selfLoadCorrection": "P1_NET_EXPORT_PLUS_EV_ACTUAL_W",
        "wwSelfLoadCorrection": False,
        "requiresFreshP1": True,
        "requiresFreshEvActualPower": True,
        "failClosed": True,
    }


def current_control_command():
    """Return a valid Pi planner command when the planner is technically ready.

    Runtime authority is deliberately not enforced here. Homey's
    EM2_Planner_Authority selector is the single cutover gate. This endpoint
    only answers whether the Pi planner can safely supply a fresh command.
    """
    now = datetime.now(timezone.utc)
    policy = load_json(CONTROL_POLICY_FILE)
    plan = load_json(DYNAMIC_PLAN_FILE)

    if policy.get("schema") != CONTROL_POLICY_SCHEMA:
        raise ValueError("CONTROL_POLICY_SCHEMA")
    if policy.get("executor") != "HOMEY":
        raise ValueError("CONTROL_EXECUTOR_MISMATCH")
    if policy.get("executionEnabled") is not True:
        raise ValueError("CONTROL_EXECUTION_DISABLED")
    if policy.get("contractMode") != "FIXED" or policy.get("contractId") != "ENGIE_3Y_2026_2029":
        raise ValueError("CONTROL_POLICY_CONTRACT_MISMATCH")

    if plan.get("schema") != PI_PLAN_SCHEMA:
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
    current_start = None
    current_end = None
    for slot in plan.get("slots") or []:
        start, end = slot_bounds(slot)
        if start is not None and end is not None and start <= now < end:
            current = slot
            current_start = start
            current_end = end
            break
    if current is None:
        raise ValueError("NO_CURRENT_SLOT")

    command_valid_until = min(valid_until, current_end)
    ev_w = max(0, int(round(float(current.get("evPlanW") or 0))))
    ww_w = max(0, int(round(float(current.get("wwPlanW") or 0))))

    return {
        "schema": "EMS_PI_CONTROL_COMMAND_V0.1",
        "status": "READY",
        "readyForCutover": True,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "validUntil": command_valid_until.isoformat().replace("+00:00", "Z"),
        "plannerOwner": "PI",
        "plannerSchema": plan.get("schema"),
        "plannerGeneratedAt": plan.get("generated_at"),
        "executor": "HOMEY",
        "contract": {"mode": "FIXED", "id": "ENGIE_3Y_2026_2029"},
        "slot": {
            "start": current_start.isoformat().replace("+00:00", "Z"),
            "end": current_end.isoformat().replace("+00:00", "Z")
        },
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
        "realtime": {
            "ev": ev_realtime_envelope(plan, current, ev_w, ww_w)
        },
        "authority": {
            "enforcedBy": "HOMEY_SELECTOR",
            "piPolicyPlannerOwner": policy.get("plannerOwner"),
            "piPolicyCutoverState": policy.get("cutoverState")
        },
        "safety": {
            "failClosed": True,
            "stalePlanRejected": True,
            "plannerDoesNotWriteDevices": True,
            "singleAuthorityGate": "EM2_Planner_Authority"
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
                    "readyForCutover": False,
                    "reason": str(exc),
                    "plannerOwner": "PI",
                    "targets": {"ev": {"target_W": 0}, "ww": {"target_on": False}, "battery": {"target_W": 0}},
                    "realtime": {
                        "ev": {
                            "schema": "EMS_PI_EV_REALTIME_ENVELOPE_V0.3",
                            "shadowOnly": False,
                            "productionConsumerAllowed": False,
                            "allowed": False,
                            "mode": "DISABLED",
                            "min_A": 0,
                            "max_A": 0,
                            "failClosed": True,
                        }
                    }
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
            control_status = "ready"
            control_valid_until = control.get("validUntil")
        except Exception as exc:
            control_status = f"blocked:{exc}"
            control_valid_until = None

        send_json(self, 200, {
            "status": overall_status,
            "service": "ems-status-api",
            "mode": "pi-planner-command",
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
            "control_authority_gate": "HOMEY_SELECTOR",
            "control_endpoint_status": control_status,
            "control_valid_until": control_valid_until
        })

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    HTTPServer((HOST, PORT), Handler).serve_forever()

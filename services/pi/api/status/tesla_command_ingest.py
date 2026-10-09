"""Authenticated, localhost-only Pi Tesla deadline command ingress.

One atomic command source; no GitHub transport and no device/control writes.
The existing derived-state builder remains the only deadline state computation.
"""
import hmac
import json
import math
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

COMMAND = Path("/home/jeroen/ems/data/tesla-deadline-command.json")
PIN_FILE = Path(os.environ.get("EMS_TESLA_CONTROL_PIN_FILE", "/etc/ems/tesla-control.pin"))
DERIVE = "/home/jeroen/ems/repo/homey-energy-manual/services/pi/state/ev/deadline/build_deadline_state.py"
KWH_PER_SOC_PERCENT = 0.62
MAX_BODY = 4096
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
DEADLINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


def _integer(value, minimum, maximum, error):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(error)
    if not math.isfinite(value) or int(value) != value or not minimum <= value <= maximum:
        raise ValueError(error)
    return int(value)


def validate_intent(data, now=None):
    """Return normalized user intent, with no side effects or generated identity."""
    if not isinstance(data, dict) or not isinstance(data.get("active"), bool):
        raise ValueError("ACTIVE_INVALID")
    active = data["active"]
    if not active:
        return dict(active=False, deadline="", currentSoc=None, targetSoc=None,
                    maxA=11, goalKWh=0.0)
    deadline = data.get("deadline")
    if not isinstance(deadline, str) or not DEADLINE_RE.fullmatch(deadline):
        raise ValueError("DEADLINE_INVALID")
    try:
        instant = datetime.fromisoformat(deadline).replace(tzinfo=LOCAL_TZ)
        if instant.astimezone(timezone.utc) <= (now or datetime.now(timezone.utc)):
            raise ValueError("DEADLINE_NOT_IN_FUTURE")
    except ValueError as e:
        if str(e) == "DEADLINE_NOT_IN_FUTURE":
            raise
        raise ValueError("DEADLINE_INVALID") from e
    current_soc = _integer(data.get("currentSoc"), 0, 99, "CURRENT_SOC_INVALID")
    target_soc = _integer(data.get("targetSoc"), 1, 100, "TARGET_SOC_INVALID")
    if target_soc <= current_soc:
        raise ValueError("TARGET_SOC_INVALID")
    max_a = _integer(data.get("maxA"), 6, 16, "MAX_A_INVALID")
    goal_kwh = round((target_soc - current_soc) * KWH_PER_SOC_PERCENT, 3)
    if not 1 <= goal_kwh <= 75:
        raise ValueError("GOAL_KWH_INVALID")
    return dict(active=True, deadline=deadline, currentSoc=current_soc,
                targetSoc=target_soc, maxA=max_a, goalKWh=goal_kwh)


def build_command(intent, client_request_id, now=None):
    now = now or datetime.now(timezone.utc)
    ts = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return dict(schema=2, requestId=str(uuid.uuid4()), clientRequestId=client_request_id,
                requestedAt=ts, source="website", active=intent["active"],
                deadline=intent["deadline"], currentSoc=intent["currentSoc"],
                targetSoc=intent["targetSoc"],
                socEnteredAt=ts if intent["active"] else "",
                calibrationKWhPerPercent=KWH_PER_SOC_PERCENT,
                goalKWh=intent["goalKWh"], maxA=intent["maxA"])


def persist_atomic(command, path=COMMAND):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(command, f, separators=(",", ":"), ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _pin_ready():
    try:
        secret = PIN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return secret if len(secret) >= 8 else None


def _previous():
    try:
        return json.loads(COMMAND.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def handle_tesla_command(handler, send_json):
    # Both the API and Caddy independently constrain who can reach this route.
    if handler.client_address[0] not in ("127.0.0.1", "::1"):
        send_json(handler, 403, {"ok": False, "error": "LOCALHOST_ONLY"})
        return
    origin = handler.headers.get("Origin")
    if origin and origin != "http://100.127.130.0":
        send_json(handler, 403, {"ok": False, "error": "PRIVATE_TAILNET_ORIGIN_REQUIRED"})
        return
    secret = _pin_ready()
    if secret is None:
        send_json(handler, 503, {"ok": False, "error": "PIN_NOT_CONFIGURED"})
        return
    supplied = handler.headers.get("X-Tesla-Control-Pin", "")
    if not supplied or not hmac.compare_digest(supplied, secret):
        send_json(handler, 401, {"ok": False, "error": "UNAUTHORIZED"})
        return
    if handler.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
        send_json(handler, 415, {"ok": False, "error": "JSON_REQUIRED"})
        return
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    if length < 1 or length > MAX_BODY:
        send_json(handler, 413, {"ok": False, "error": "BODY_SIZE"})
        return
    try:
        incoming = json.loads(handler.rfile.read(length).decode("utf-8"))
        intent = validate_intent(incoming)
        client_id = incoming.get("clientRequestId", "")
        uuid.UUID(client_id)
    except (ValueError, UnicodeError, AttributeError, TypeError, KeyError) as e:
        send_json(handler, 400, {"ok": False, "error": str(e) if isinstance(e, ValueError) else "INVALID_REQUEST"})
        return
    previous = _previous()
    if previous.get("clientRequestId") == client_id:
        existing = {k: previous.get(k) for k in intent}
        if existing != intent:
            send_json(handler, 409, {"ok": False, "error": "IDEMPOTENCY_CONFLICT"})
            return
        send_json(handler, 200, {"ok": True, "command": previous, "duplicate": True,
                                 "derivedState": "ALREADY_ACCEPTED"})
        return

    command = build_command(intent, client_id)
    try:
        persist_atomic(command)
    except OSError:
        send_json(handler, 503, {"ok": False, "error": "COMMAND_PERSIST_FAILED"})
        return

    # Existing builder, same executable and same files as systemd; no alternate planner.
    # It uses a shared file lock with its systemd invocations to prevent concurrent writes.
    try:
        result = subprocess.run(["/usr/bin/python3", DERIVE], timeout=10,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                check=False)
        derived = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        derived = False
    send_json(handler, 200 if derived else 202,
              {"ok": True, "command": command,
               "derivedState": "UPDATED" if derived else "PENDING_WATCHDOG"})

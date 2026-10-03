#!/usr/bin/env python3
"""Read-only EMS/Pi health evidence.

Produces a bounded JSON snapshot for operators and the AI analysis layer.
No device writes, Homey calls, planner writes or remediation actions.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "EMS_PI_HEALTH_V0.1"
DATA = Path("/home/jeroen/ems/data")

DATA_SOURCES = {
    "energyState": (DATA / "energy-state-v2.json", ("meta", "source_sample_at"), 600),
    "dynamicPlan": (DATA / "dynamic-shadow-plan.json", ("generated_at",), 2100),
    "evDeadline": (DATA / "ev-deadline-shadow-state.json", ("generatedAt",), 900),
    "pvForecast": (DATA / "pv-forecast.json", ("generated_at",), 2100),
    "weatherForecast": (DATA / "weather-forecast.json", ("generated_at",), 2100),
    "quattForecast": (DATA / "quatt-forecast.json", ("generated_at",), 2100),
    "wwPlan": (DATA / "ww-plan.json", ("generated_at",), 2100),
}

FUNCTION_UNITS = {
    "statusApi": "ems-status-api.service",
    "webDataApi": "ems-web-data-api.service",
    "aiAnalysis": "ems-ai-analysis.service",
    "forecastChain": "ems-forecast-chain.timer",
    "history15m": "ems-history-15m.timer",
    "historyDaily": "ems-history-daily.timer",
    "evDeadline": "ems-ev-deadline-command.timer",
    "weatherForecast": "ems-weather-forecast.timer",
    "quattCurrent": "ems-quatt-current.timer",
    "honeywellState": "ems-honeywell-state.timer",
    "honeywellSchedule": "ems-honeywell-schedule.timer",
}


def _now():
    return datetime.now(timezone.utc)


def _parse_ts(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _nested(payload, path):
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _data_status():
    now = _now()
    result = {}
    degraded = False
    for name, (path, ts_path, stale_after) in DATA_SOURCES.items():
        payload = _read_json(path)
        if payload is None:
            result[name] = {
                "status": "MISSING_OR_INVALID",
                "path": str(path),
                "ageSec": None,
                "generatedAt": None,
                "staleAfterSec": stale_after,
            }
            degraded = True
            continue
        raw = _nested(payload, ts_path)
        generated = _parse_ts(raw)
        age = None if generated is None else max(0, int((now - generated).total_seconds()))
        status = "OK" if age is not None and age <= stale_after else "STALE"
        if status != "OK":
            degraded = True
        result[name] = {
            "status": status,
            "path": str(path),
            "ageSec": age,
            "generatedAt": raw,
            "staleAfterSec": stale_after,
        }

    for name, path in {
        "historyDb": DATA / "ems-history.sqlite",
        "plannerHistoryDb": DATA / "planner-history.sqlite",
    }.items():
        try:
            age = max(0, int(now.timestamp() - path.stat().st_mtime))
            result[name] = {"status": "OK", "path": str(path), "mtimeAgeSec": age}
        except OSError:
            result[name] = {"status": "MISSING", "path": str(path), "mtimeAgeSec": None}
            degraded = True

    return result, degraded


def _systemctl_show(unit):
    props = (
        "LoadState", "ActiveState", "SubState", "Result",
        "ExecMainStatus", "ExecMainExitTimestamp", "ActiveEnterTimestamp",
    )
    try:
        proc = subprocess.run(
            ["systemctl", "show", unit, "--no-pager",
             "--property=" + ",".join(props)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception as exc:
        return {"unit": unit, "status": "UNAVAILABLE", "error": str(exc)}
    if proc.returncode != 0:
        return {
            "unit": unit,
            "status": "UNAVAILABLE",
            "error": proc.stderr.strip()[:200],
        }
    values = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    active = values.get("ActiveState")
    result = values.get("Result")
    status = "OK"
    if values.get("LoadState") != "loaded":
        status = "MISSING"
    elif active not in ("active", "inactive"):
        status = "DEGRADED"
    elif result not in (None, "", "success"):
        status = "DEGRADED"
    return {"unit": unit, "status": status, **values}


def _functions_status():
    items = {name: _systemctl_show(unit) for name, unit in FUNCTION_UNITS.items()}
    degraded = any(v.get("status") != "OK" for v in items.values())
    return items, degraded


def _memory():
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0]) * 1024
    except Exception:
        return {"totalBytes": None, "availableBytes": None, "usedPct": None}
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used_pct = None
    if total and available is not None:
        used_pct = round((1 - available / total) * 100, 1)
    return {"totalBytes": total, "availableBytes": available, "usedPct": used_pct}


def _disk():
    try:
        usage = shutil.disk_usage("/home/jeroen/ems")
        return {
            "totalBytes": usage.total,
            "freeBytes": usage.free,
            "usedPct": round(usage.used / usage.total * 100, 1),
        }
    except Exception:
        return {"totalBytes": None, "freeBytes": None, "usedPct": None}


def _temperature_c():
    try:
        raw = float(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip())
        return round(raw / 1000.0, 1)
    except Exception:
        return None


def _throttled():
    path = shutil.which("vcgencmd")
    if not path:
        return None
    try:
        proc = subprocess.run(
            [path, "get_throttled"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else None
    except Exception:
        return None


def _system_status():
    try:
        uptime = int(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception:
        uptime = None
    try:
        load = [round(v, 2) for v in os.getloadavg()]
    except Exception:
        load = [None, None, None]
    return {
        "uptimeSec": uptime,
        "load1m": load[0],
        "load5m": load[1],
        "load15m": load[2],
        "memory": _memory(),
        "disk": _disk(),
        "temperatureC": _temperature_c(),
        "throttled": _throttled(),
    }


def _recent_incidents():
    """Best-effort last-24h warning/error evidence.

    Lack of journal permission is reported explicitly. This is not a complete
    incident history; persistent incident archiving remains a later capability.
    """
    try:
        proc = subprocess.run(
            [
                "journalctl", "--since", "24 hours ago",
                "--priority=warning..alert", "--no-pager", "--output=json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {
            "coverage": "UNAVAILABLE",
            "error": str(exc),
            "events": [],
        }
    if proc.returncode != 0:
        return {
            "coverage": "UNAVAILABLE",
            "error": proc.stderr.strip()[:240],
            "events": [],
        }
    events = []
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        unit = str(item.get("_SYSTEMD_UNIT") or "")
        if not unit.startswith("ems-"):
            continue
        realtime = item.get("__REALTIME_TIMESTAMP")
        at = None
        try:
            at = datetime.fromtimestamp(
                int(realtime) / 1_000_000, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
        except Exception:
            pass
        events.append({
            "at": at,
            "unit": unit,
            "priority": item.get("PRIORITY"),
            "message": str(item.get("MESSAGE") or "")[:300],
        })
    return {
        "coverage": "JOURNAL_24H_BEST_EFFORT",
        "events": events[-30:],
        "note": "Not a durable incident archive; recovered incidents can fall outside this window.",
    }


def build_health():
    data, data_degraded = _data_status()
    functions, functions_degraded = _functions_status()
    incidents = _recent_incidents()
    current_degraded = data_degraded or functions_degraded
    has_recent = bool(incidents.get("events"))

    if current_degraded:
        status = "DEGRADED"
    elif has_recent:
        status = "HEALTHY_WITH_RECENT_INCIDENTS"
    else:
        status = "HEALTHY"

    return {
        "schema": SCHEMA,
        "generatedAt": _now().isoformat().replace("+00:00", "Z"),
        "readOnly": True,
        "controlWrites": False,
        "status": status,
        "system": _system_status(),
        "emsData": data,
        "emsFunctions": functions,
        "recentIncidentSignals": incidents,
        "limitations": [
            "Recent incident evidence is best-effort journal coverage, not durable incident history.",
            "Current health does not prove that a historical control decision was healthy at that exact timestamp.",
        ],
    }


def main():
    print(json.dumps(build_health(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

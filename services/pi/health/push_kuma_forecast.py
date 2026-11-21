#!/usr/bin/env python3
"""Send read-only forecast health evidence to one local Uptime Kuma push monitor.

Opt-in only. Reads the existing ems-health command; never contacts Homey or
controllers and never changes EMS state. The push URL is a local secret.
"""

import json
import os
import subprocess
import sys
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import urlopen

HEALTH_COMMAND = "/usr/local/bin/ems-health"
HEALTH_SCHEMA = "EMS_PI_HEALTH_V0.1"


def decide(health):
    """Return (up|down, bounded reason) for the forecast chain only."""
    if not isinstance(health, dict) or health.get("schema") != HEALTH_SCHEMA:
        return "down", "HEALTH_SCHEMA_INVALID"

    for section, key, reason in (
        ("emsFunctions", "forecastChain", "FORECAST_CHAIN_NOT_OK"),
        ("emsData", "dynamicPlan", "DYNAMIC_PLAN_NOT_OK"),
        ("emsData", "wwPlan", "WW_PLAN_NOT_OK"),
    ):
        items = health.get(section)
        item = items.get(key) if isinstance(items, dict) else None
        if not isinstance(item, dict) or item.get("status") != "OK":
            return "down", reason
    return "up", "FORECAST_CHAIN_OK"


def build_url(configured_url, status, reason):
    """Allow only the loopback Kuma push endpoint; never leak its token."""
    try:
        parts = urlsplit(configured_url)
        valid = (
            parts.scheme == "http"
            and parts.hostname in ("127.0.0.1", "localhost")
            and parts.port == 3001
            and parts.username is None
            and parts.password is None
            and parts.path.startswith("/api/push/")
            and len(parts.path.split("/")) == 4
            and bool(parts.path.split("/")[3])
            and not parts.query
            and not parts.fragment
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("KUMA_PUSH_URL_INVALID")
    query = urlencode({"status": status, "msg": reason})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def current_health():
    try:
        proc = subprocess.run(
            [HEALTH_COMMAND], capture_output=True, text=True,
            timeout=25, check=False,
        )
        if proc.returncode != 0:
            return "down", "HEALTH_COMMAND_FAILED"
        return decide(json.loads(proc.stdout))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return "down", "HEALTH_COMMAND_UNAVAILABLE"


def push(url):
    status, reason = current_health()
    target = build_url(url, status, reason)
    try:
        with urlopen(target, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("KUMA_PUSH_HTTP_ERROR")
            data = json.loads(response.read(2048).decode("utf-8"))
            if data.get("ok") is not True:
                raise RuntimeError("KUMA_PUSH_REJECTED")
    except Exception:
        # A secret token is embedded in the URL; never print an exception
        # whose string representation might contain it.
        print("KUMA_PUSH_DELIVERY_FAILED", file=sys.stderr)
        return 1
    print(f"KUMA_FORECAST status={status} reason={reason}")
    return 0


def main():
    configured_url = os.environ.get("KUMA_PUSH_URL", "")
    try:
        build_url(configured_url, "up", "VALIDATE")
    except ValueError:
        print("KUMA_PUSH_URL_INVALID", file=sys.stderr)
        return 2
    return push(configured_url)


if __name__ == "__main__":
    raise SystemExit(main())

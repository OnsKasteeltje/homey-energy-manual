#!/usr/bin/env python3
"""Archive Quatt CiC supervisory mode via the local read-only HTTP feed.

Independent *observation*, not a Quatt or Honeywell control path. A value of
3/4 means boiler operation requested by CiC, not proof of an active flame.
"""
import ipaddress
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
METRIC = "supervisory_control_mode"
SOURCE_RESOLUTION_SECONDS = 60
MAX_RESPONSE_BYTES = 262144


def validate_url(url):
    """Keep this collector on the explicitly configured LAN CiC endpoint."""
    parsed = urlsplit(url)
    try:
        host = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("QUATT_CIC_URL must use a literal private IP") from exc
    if (parsed.scheme != "http" or not host.is_private or host.is_loopback
            or host.is_link_local or port != 8080
            or parsed.path != "/beta/feed/data.json"
            or parsed.query or parsed.fragment or parsed.username
            or parsed.password):
        raise ValueError("QUATT_CIC_URL must be a private LAN CiC feed on port 8080")
    return url


def mode_from_payload(payload):
    qc = payload.get("qc") if isinstance(payload, dict) else None
    mode = qc.get("supervisoryControlMode") if isinstance(qc, dict) else None
    # Do not confuse false/null with STANDBY (0), or reject future mode codes.
    if type(mode) is not int or mode < 0 or mode > 65535:
        raise ValueError("CiC supervisoryControlMode is absent or invalid")
    return mode


def fetch_mode(url, opener=urlopen):
    validate_url(url)
    with opener(url, timeout=3) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("CiC response exceeds size limit")
    return mode_from_payload(json.loads(raw))


def archive_mode(db_path, mode, observed_at):
    if not Path(db_path).is_file():
        raise RuntimeError("Canonical EMS history DB missing")
    # mode=rw must not silently create a second history database.
    with sqlite3.connect(f"file:{db_path}?mode=rw", uri=True, timeout=5) as db:
        device = db.execute(
            "SELECT id FROM devices WHERE device_key='quatt_cic'"
        ).fetchone()
        if device is None:
            raise RuntimeError("Canonical quatt_cic device missing")
        db.execute(
            """INSERT OR IGNORE INTO metrics
               (metric_key, unit, value_type, description)
               VALUES (?, NULL, 'number', ?)""",
            (METRIC, "Read-only Quatt CiC qc.supervisoryControlMode"),
        )
        metric = db.execute(
            "SELECT id FROM metrics WHERE metric_key=?", (METRIC,)
        ).fetchone()
        cur = db.execute(
            """INSERT OR IGNORE INTO measurements
               (ts_utc, device_id, metric_id, value_real, quality,
                source_resolution_seconds)
               VALUES (?, ?, ?, ?, 'observed', ?)""",
            (observed_at, device[0], metric[0], float(mode),
             SOURCE_RESOLUTION_SECONDS),
        )
        return cur.rowcount


def main():
    url = validate_url(os.environ["QUATT_CIC_URL"])
    mode = fetch_mode(url)
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    inserted = archive_mode(DB, mode, observed_at)
    print(f"CiC supervisory_control_mode={mode} observedAt={observed_at} inserted={inserted}")


if __name__ == "__main__":
    main()

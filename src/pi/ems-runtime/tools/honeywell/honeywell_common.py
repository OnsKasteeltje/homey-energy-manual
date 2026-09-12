#!/usr/bin/env python3

"""Shared read-only Honeywell/Resideo helper functions.

Provides shell-safe credential loading, persistent OAuth token caching, normalized
JSON helpers and atomic local-file writes. No vendor/Homey/OpenTherm writes.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from evohomeasync2 import EvohomeClientOld

ROOT = Path(__file__).resolve().parent
ACCOUNT_ENV = ROOT / "config" / "account.env"
ZONE_MAP = ROOT / "config" / "zone-map.json"
TOKEN_CACHE = ROOT / "cache" / "oauth-token.json"


def load_credentials(path: Path = ACCOUNT_ENV) -> tuple[str, str]:
    """Load account.env using Bash semantics because it may contain printf %q data."""
    if not path.exists():
        raise SystemExit(f"ERROR: missing credential file: {path}")

    script = (
        'set -a; source "$1"; '
        'printf "%s\\0%s\\0" "$HONEYWELL_USERNAME" "$HONEYWELL_PASSWORD"'
    )
    result = subprocess.run(
        ["/bin/bash", "-c", script, "bash", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    parts = result.stdout.split(b"\0")
    if len(parts) < 3:
        raise SystemExit("ERROR: credential file did not yield username/password")

    username = parts[0].decode().strip()
    password = parts[1].decode()
    if not username or not password:
        raise SystemExit("ERROR: HONEYWELL_USERNAME/PASSWORD not configured")
    return username, password


def load_mapping(path: Path = ZONE_MAP) -> dict[str, Any]:
    mapping = json.loads(path.read_text())
    zones = mapping.get("zones", [])
    zone_ids = [str(z["honeywellZoneId"]) for z in zones]
    if len(zones) != 8:
        raise SystemExit(f"ERROR: expected 8 mapped zones, got {len(zones)}")
    if len(zone_ids) != len(set(zone_ids)):
        raise SystemExit("ERROR: duplicate honeywellZoneId in zone-map.json")
    return mapping


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return str(value)


def switchpoint(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    when, target = value
    return {
        "time": jsonable(when),
        "targetTemperature_C": jsonable(target),
    }


def atomic_write_json(path: Path, payload: dict[str, Any], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    os.chmod(tmp, mode)
    tmp.replace(path)


def _load_token_cache(path: Path = TOKEN_CACHE) -> tuple[dict[str, Any], bool]:
    try:
        raw = json.loads(path.read_text())
        expires_raw = raw.get("access_token_expires")
        if not raw.get("access_token") or not raw.get("refresh_token") or not expires_raw:
            return {}, False
        return {
            "access_token": raw["access_token"],
            "refresh_token": raw["refresh_token"],
            "access_token_expires": datetime.fromisoformat(expires_raw),
        }, True
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}, False


def create_client() -> tuple[EvohomeClientOld, bool, bool]:
    """Create client using cached OAuth tokens when available.

    Returns (client, cache_loaded, cached_access_token_valid_at_start).
    An expired access token is still useful because its refresh token can avoid a
    username/password grant.
    """
    username, password = load_credentials()
    token_data, cache_loaded = _load_token_cache()

    now = datetime.now().astimezone()
    expires = token_data.get("access_token_expires")
    valid_at_start = bool(
        cache_loaded
        and expires is not None
        and expires.astimezone() > now
    )

    client = EvohomeClientOld(username, password, **token_data)
    return client, cache_loaded, valid_at_start


def save_token_cache(client: EvohomeClientOld, path: Path = TOKEN_CACHE) -> None:
    """Persist current access/refresh token state with restrictive permissions."""
    payload = {
        "schema": "EMS_HONEYWELL_OAUTH_CACHE_V0.1",
        "access_token": client.access_token,
        "access_token_expires": client.access_token_expires.isoformat(),
        "refresh_token": client.refresh_token,
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    atomic_write_json(path, payload, mode=0o600)

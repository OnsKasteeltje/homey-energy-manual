#!/usr/bin/env python3
"""Independent, one-shot PV cloud SHADOW observation. Never a control input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

SCHEMA = "EMS_PV_CLOUD_SHADOW_V0.1"
HISTORY_SCHEMA = "EMS_PV_CLOUD_SHADOW_HISTORY_V0.1"
DEFAULT_OUTPUT = Path("/home/jeroen/ems/runtime/state/pv-cloud-shadow-v0.1.json")
DEFAULT_HISTORY = Path("/home/jeroen/ems/runtime/state/pv-cloud-shadow-history-v0.1.json")
HISTORY_LIMIT = 192
SOLAREDGE_API = "https://monitoringapi.solaredge.com/site/{site_id}/overview"

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def nonnegative_number(value):
    """Missing/malformed values are unknown, not zero."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and result >= 0 else None

def solar_edge_projection(overview, fetched_at):
    if not isinstance(overview, dict):
        raise ValueError("INVALID_OVERVIEW")
    power = nonnegative_number((overview.get("currentPower") or {}).get("power"))
    day_wh = nonnegative_number((overview.get("lastDayData") or {}).get("energy"))
    lifetime_wh = nonnegative_number((overview.get("lifeTimeData") or {}).get("energy"))
    return {
        "source": "SOLAREDGE_MONITORING_API",
        "status": "RECEIVED_SITE_TIME_ONLY" if power is not None else "MISSING_POWER",
        "fetchedAt": fetched_at,
        "sourcePowerMeasuredAt": None,
        "sourceSiteLastUpdateLocal": overview.get("lastUpdateTime") if isinstance(overview.get("lastUpdateTime"), str) else None,
        "powerW": power,
        "todayKWh": day_wh / 1000 if day_wh is not None else None,
        "lifetimeKWh": lifetime_wh / 1000 if lifetime_wh is not None else None,
    }

def goodwe_projection(data, fetched_at):
    if not isinstance(data, dict) or not isinstance(data.get("inverter"), list):
        raise ValueError("INVALID_GOODWE_PAYLOAD")
    records = []
    suffixes = set()
    for item in data["inverter"]:
        if not isinstance(item, dict):
            continue
        serial = item.get("sn")
        if not isinstance(serial, str) or len(serial) < 4:
            continue
        suffix = serial[-4:]
        values = item.get("invert_full") or {}
        if not isinstance(values, dict):
            values = {}
        power = nonnegative_number(values.get("pac"))
        records.append({
            "deviceKey": hashlib.sha256(serial.encode("utf-8")).hexdigest()[:16],
            "serialSuffix": suffix,
            "status": "RECEIVED_SOURCE_TIME_UNKNOWN" if power is not None else "MISSING_POWER",
            "fetchedAt": fetched_at,
            "sourcePowerMeasuredAt": None,
            "powerW": power,
            "todayKWh": nonnegative_number(values.get("eday")),
            "lifetimeKWh": nonnegative_number(values.get("etotal")),
        })
        suffixes.add(suffix)
    records.sort(key=lambda row: row["deviceKey"])
    complete = len(records) == 2 and len(suffixes) == 2 and all(row["powerW"] is not None for row in records)
    return {
        "source": "SEMS_PLUS_WEB_API",
        "status": "RECEIVED_SOURCE_TIME_UNKNOWN" if complete else "INCOMPLETE",
        "fetchedAt": fetched_at,
        "sourcePowerMeasuredAt": None,
        "stationPowerW": nonnegative_number((data.get("powerflow") or {}).get("pv")),
        "inverters": records,
        "sumInverterPowerW": sum(row["powerW"] for row in records) if complete else None,
    }

def fetch_goodwe(config):
    from pygoodwe import API
    api = API(
        system_id=config["SEMSPLUS_STATION_ID"],
        account=config["SEMSPLUS_ACCOUNT"],
        password=config["SEMSPLUS_PASSWORD"],
        skipload=True,
        log_level="WARNING",
    )
    try:
        return goodwe_projection(api.get_current_readings(maxretries=1), utc_now())
    finally:
        api.session.close()

def fetch_solaredge(config):
    url = SOLAREDGE_API.format(site_id=config["SOLAREDGE_SITE_ID"])
    url += "?" + urlencode({"api_key": config["SOLAREDGE_API_KEY"]})
    with urlopen(url, timeout=20) as response:
        payload = response.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise ValueError("OVERSIZED_RESPONSE")
    return solar_edge_projection(json.loads(payload).get("overview"), utc_now())

def error_code(exc):
    """Never print raw error details; HTTP request URL can contain the API key."""
    if isinstance(exc, HTTPError):
        return "RATE_LIMIT" if exc.code == 429 else "AUTH_OR_PERMISSION" if exc.code in (401, 403) else "HTTP_ERROR"
    if isinstance(exc, (URLError, TimeoutError, ConnectionError)):
        return "NETWORK_ERROR"
    kind = getattr(exc, "kind", None)
    if kind is not None:
        value = str(getattr(kind, "value", "UNKNOWN")).upper()
        return value if value in {"AUTHENTICATION", "PERMISSION", "RATE_LIMIT", "TRANSPORT", "API", "UNAVAILABLE", "NO_INVERTERS"} else "UPSTREAM_ERROR"
    return "UPSTREAM_ERROR"

def collect(config, *, goodwe_fetch=fetch_goodwe, solaredge_fetch=fetch_solaredge):
    result = {
        "schema": SCHEMA,
        "generatedAt": utc_now(),
        "mode": "SHADOW",
        "readOnly": True,
        "eligibleForControl": False,
        "eligibleForHouseBalance": False,
        "note": "Cloud fetch timestamps are not physical inverter sample timestamps",
        "goodwe": None,
        "solaredge": None,
    }
    sources = (
        ("goodwe", ("SEMSPLUS_STATION_ID", "SEMSPLUS_ACCOUNT", "SEMSPLUS_PASSWORD"), goodwe_fetch),
        ("solaredge", ("SOLAREDGE_SITE_ID", "SOLAREDGE_API_KEY"), solaredge_fetch),
    )
    for name, keys, fetcher in sources:
        if any(not config.get(key) for key in keys):
            result[name] = {"status": "UNCONFIGURED"}
            continue
        try:
            result[name] = fetcher(config)
        except Exception as exc:
            result[name] = {"status": "FETCH_FAILED", "errorCode": error_code(exc)}
    goodwe_ok = result["goodwe"].get("status") == "RECEIVED_SOURCE_TIME_UNKNOWN"
    solaredge_ok = result["solaredge"].get("status") == "RECEIVED_SITE_TIME_ONLY"
    result["status"] = "OBSERVED_UNVERIFIED_FRESHNESS" if goodwe_ok and solaredge_ok else "DEGRADED"
    return result

def atomic_write(path, data):
    path = Path(path)
    if not path.parent.is_dir():
        raise FileNotFoundError("SHADOW_OUTPUT_DIRECTORY_MISSING")
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".pv-cloud-shadow-", suffix=".tmp", encoding="utf-8", delete=False) as f:
            name = f.name
            os.fchmod(f.fileno(), 0o600)
            json.dump(data, f, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)

def update_history(path, state, *, limit=HISTORY_LIMIT):
    path = Path(path)
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current.get("schema") != HISTORY_SCHEMA or not isinstance(current.get("samples"), list):
            raise ValueError("INVALID_SHADOW_HISTORY")
        samples = current["samples"]
    else:
        samples = []
    samples.append(state)
    atomic_write(path, {"schema": HISTORY_SCHEMA, "samples": samples[-limit:]})

def main():
    parser = argparse.ArgumentParser(description="One-shot PV cloud SHADOW read-only collector")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args()
    state = collect(os.environ)
    atomic_write(args.output, state)
    update_history(args.history, state)
    print(f"PV cloud SHADOW: {state['status']}; GoodWe={state['goodwe']['status']}; SolarEdge={state['solaredge']['status']}")

if __name__ == "__main__":
    main()

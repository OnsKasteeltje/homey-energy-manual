#!/usr/bin/env python3
"""Independent, one-shot PV cloud SHADOW observation. Never a control input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import os
from datetime import timedelta
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
        today = nonnegative_number(values.get("eday"))
        lifetime = nonnegative_number(values.get("etotal"))
        # SEMS+ may omit pac after sunset while still returning valid
        # cumulative counters. Keep missing watts unknown, never 0 W.
        counter_only = power is None and today is not None and lifetime is not None
        records.append({
            "deviceKey": hashlib.sha256(serial.encode("utf-8")).hexdigest()[:16],
            "serialSuffix": suffix,
            "status": (
                "RECEIVED_SOURCE_TIME_UNKNOWN" if power is not None else
                "COUNTER_ONLY_SOURCE_TIME_UNKNOWN" if counter_only else
                "MISSING_POWER"
            ),
            "fetchedAt": fetched_at,
            "sourcePowerMeasuredAt": None,
            "powerW": power,
            "todayKWh": today,
            "lifetimeKWh": lifetime,
        })
        suffixes.add(suffix)
    records.sort(key=lambda row: row["deviceKey"])
    paired = len(records) == 2 and len(suffixes) == 2
    complete = paired and all(row["powerW"] is not None for row in records)
    counter_only = (
        paired and not complete
        and all(row["todayKWh"] is not None and row["lifetimeKWh"] is not None
                for row in records)
    )
    return {
        "source": "SEMS_PLUS_WEB_API",
        "status": (
            "RECEIVED_SOURCE_TIME_UNKNOWN" if complete else
            "COUNTER_ONLY_SOURCE_TIME_UNKNOWN" if counter_only else
            "INCOMPLETE"
        ),
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
    # A deliberately absent source is outside the active measurement chain.
    # Keep per-source UNCONFIGURED for diagnostics, but never downgrade the
    # overall status because of it. Do not call an empty chain healthy.
    expected = {
        "goodwe": "RECEIVED_SOURCE_TIME_UNKNOWN",
        "solaredge": "RECEIVED_SITE_TIME_ONLY",
    }
    active = [name for name, keys, _ in sources if all(config.get(key) for key in keys)]
    result["activeSources"] = active
    if not active:
        result["status"] = "NO_ACTIVE_SOURCES"
    elif all(
        result[name]["status"] == expected[name] or
        (name == "goodwe" and result[name]["status"] == "COUNTER_ONLY_SOURCE_TIME_UNKNOWN")
        for name in active
    ):
        # Preserve a distinct, limited counter-only state; missing inverter
        # power is not silently accepted as a complete live measurement.
        result["status"] = (
            "OBSERVED_COUNTER_ONLY_UNVERIFIED_FRESHNESS"
            if result["goodwe"]["status"] == "COUNTER_ONLY_SOURCE_TIME_UNKNOWN"
            else "OBSERVED_UNVERIFIED_FRESHNESS"
        )
    else:
        result["status"] = "DEGRADED"
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


# Independent, durable SEMS+ daily-counter evidence; no canonical Homey/P1 writes.
GOODWE_ARCHIVE = Path("/home/jeroen/ems/data/ems-history.sqlite")

def archive_goodwe_samples(path, samples):
    """Append validated paired SEMS+ counters; idempotent across restarts.

    Physical inverter measurement time is NOT known. Database timestamps are
    Pi-fetch timestamps, not synthetic source measurement timestamps.
    """
    import sqlite3
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("EXISTING_EMS_HISTORY_DATABASE_MISSING")
    # Reuse canonical history. NEVER create/chmod/replace its database file.
    con = sqlite3.connect(str(path), timeout=5)
    inserted = 0
    try:
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("""
            CREATE TABLE IF NOT EXISTS goodwe_counter_observations (
                fetched_at_utc TEXT NOT NULL,
                device_key TEXT NOT NULL,
                serial_suffix TEXT NOT NULL,
                today_kwh REAL NOT NULL,
                lifetime_kwh REAL NOT NULL,
                power_w REAL,
                source_status TEXT NOT NULL,
                PRIMARY KEY (fetched_at_utc, device_key)
            )
        """)
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            goodwe = sample.get("goodwe")
            if not isinstance(goodwe, dict) or goodwe.get("status") not in (
                "RECEIVED_SOURCE_TIME_UNKNOWN",
                "COUNTER_ONLY_SOURCE_TIME_UNKNOWN",
            ):
                continue
            try:
                when = datetime.fromisoformat(
                    goodwe["fetchedAt"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except (KeyError, AttributeError, TypeError, ValueError):
                continue
            if when > datetime.now(timezone.utc) + timedelta(minutes=2):
                continue
            inverters = goodwe.get("inverters")
            if not isinstance(inverters, list) or len(inverters) != 2:
                continue
            records = []
            identities = set()
            suffixes = set()
            for inv in inverters:
                if not isinstance(inv, dict):
                    break
                key, suffix = inv.get("deviceKey"), inv.get("serialSuffix")
                today, lifetime = inv.get("todayKWh"), inv.get("lifetimeKWh")
                if (not isinstance(key, str) or len(key) != 16 or
                    not all(ch in "0123456789abcdef" for ch in key) or
                    not isinstance(suffix, str) or len(suffix) != 4 or
                    not all(ch.isalnum() for ch in suffix) or
                    not isinstance(today, (int, float)) or isinstance(today, bool) or
                    not isinstance(lifetime, (int, float)) or isinstance(lifetime, bool) or
                    not math.isfinite(today) or not math.isfinite(lifetime) or
                    today < 0 or lifetime < 0):
                    break
                power = inv.get("powerW")
                power = power if (isinstance(power, (int, float)) and
                                 not isinstance(power, bool) and
                                 math.isfinite(power) and power >= 0) else None
                identities.add(key)
                suffixes.add(suffix)
                records.append((
                    when.isoformat(timespec="microseconds"), key, suffix,
                    float(today), float(lifetime), power, goodwe["status"]
                ))
            if len(records) != 2 or len(identities) != 2 or len(suffixes) != 2:
                continue
            before = con.total_changes
            con.executemany("""
                INSERT OR IGNORE INTO goodwe_counter_observations
                (fetched_at_utc, device_key, serial_suffix, today_kwh,
                 lifetime_kwh, power_w, source_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, records)
            inserted += con.total_changes - before
        con.commit()
        return inserted
    finally:
        con.close()


def _archive_needs_seed(path):
    """Seed the bounded JSON ring once when the dedicated table first appears."""
    import sqlite3
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5) as db:
        return db.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='goodwe_counter_observations'
        """).fetchone() is None


def main():
    parser = argparse.ArgumentParser(description="One-shot PV cloud SHADOW read-only collector")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args()
    # Fail closed on third-party diagnostics; exceptions are sanitized in collect().
    logging.disable(logging.CRITICAL)
    state = collect(os.environ)
    atomic_write(args.output, state)
    bootstrap_archive = _archive_needs_seed(GOODWE_ARCHIVE)
    update_history(args.history, state)
    if bootstrap_archive:
        # Seed the existing ~48-hour bounded history exactly once. Old missing
        # periods remain unknown; later runs archive each new observation.
        all_samples = json.loads(args.history.read_text(encoding="utf-8"))["samples"]
        archive_goodwe_samples(GOODWE_ARCHIVE, all_samples)
    else:
        archive_goodwe_samples(GOODWE_ARCHIVE, [state])
    print(f"PV cloud SHADOW: {state['status']}; GoodWe={state['goodwe']['status']}; SolarEdge={state['solaredge']['status']}")

if __name__ == "__main__":
    main()

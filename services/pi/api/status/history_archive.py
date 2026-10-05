"""Local historical archive for accepted Homey Core state snapshots.

Runtime direction remains one-way for observed state:
Homey Core -> Pi status API -> local current state + local SQLite history.

This module performs no Homey calls, no GitHub calls and no device writes.
Archiving is intentionally idempotent on (timestamp, device, metric).
"""

import sqlite3
from pathlib import Path

HISTORY_DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
DEFAULT_SOURCE_RESOLUTION_SECONDS = 300

POWER_DEVICES = {
    "grid_p1": {
        "source_device_id": "em2:p1",
        "name": "P1 Grid",
        "device_type": "grid_meter",
        "path": ("grid", "power_w"),
    },
    "pv_solaredge": {
        "source_device_id": "em2:solaredge",
        "name": "SolarEdge",
        "device_type": "pv_inverter",
        "path": ("pv", "solaredge_w"),
    },
    "pv_goodwe4200": {
        "source_device_id": "em2:goodwe4200",
        "name": "GoodWe 4200",
        "device_type": "pv_inverter",
        "path": ("pv", "goodwe_4200_w"),
    },
    "pv_goodwe2000": {
        "source_device_id": "em2:goodwe2000",
        "name": "GoodWe 2000",
        "device_type": "pv_inverter",
        "path": ("pv", "goodwe_2000_w"),
    },
    "tesla": {
        "source_device_id": "em2:tesla",
        "name": "Tesla charging",
        "device_type": "ev_charger",
        "path": ("tesla", "power_w"),
    },
    "boiler": {
        "source_device_id": "em2:boiler",
        "name": "Stiebel Eltron HSTP200",
        "device_type": "water_heater",
        "path": ("hot_water", "boiler_power_w"),
    },
    "quatt_cic": {
        "source_device_id": "em2:quatt",
        "name": "Quatt CIC",
        "device_type": "heatpump",
        "path": ("quatt", "power_w"),
    },
}

COUNTER_DEVICES = {
    "grid_p1": {
        "spec": POWER_DEVICES["grid_p1"],
        "metrics": {
            "energy_import_kwh": ("grid", "energy_import_kwh"),
            "energy_export_kwh": ("grid", "energy_export_kwh"),
        },
    },
    "pv_solaredge": {
        "spec": POWER_DEVICES["pv_solaredge"],
        "metrics": {
            "energy_produced_kwh": ("pv", "solaredge_energy_kwh"),
        },
    },
    "pv_goodwe4200": {
        "spec": POWER_DEVICES["pv_goodwe4200"],
        "metrics": {
            "energy_produced_kwh": ("pv", "goodwe_4200_energy_kwh"),
        },
    },
    "pv_goodwe2000": {
        "spec": POWER_DEVICES["pv_goodwe2000"],
        "metrics": {
            "energy_produced_kwh": ("pv", "goodwe_2000_energy_kwh"),
        },
    },
    "tesla": {
        "spec": POWER_DEVICES["tesla"],
        "metrics": {
            "energy_delivered_kwh": ("tesla", "meter_kwh"),
        },
    },
}

STATE_DEVICES = {
    "washer": {
        "source_device_id": "em2:washer",
        "name": "Washing machine",
        "device_type": "appliance",
        "path": ("loads", "washer", "active"),
    },
    "dryer": {
        "source_device_id": "em2:dryer",
        "name": "Dryer",
        "device_type": "appliance",
        "path": ("loads", "dryer", "active"),
    },
}


EV_EVIDENCE_METRICS = {
    "ev_connected": ("boolean", None, ("tesla", "connected")),
    "ev_charging": ("boolean", None, ("tesla", "charging")),
    "ev_requested_a": ("number", "A", ("tesla", "requested_a")),
    "ev_offered_a": ("number", "A", ("tesla", "offered_a")),
    "ev_l1_a": ("number", "A", ("tesla", "l1_a")),
    "ev_l2_a": ("number", "A", ("tesla", "l2_a")),
    "ev_l3_a": ("number", "A", ("tesla", "l3_a")),
    "ev_deadline_active": ("boolean", None, ("tesla", "deadline_active")),
    "ev_deadline_max_a": ("number", "A", ("tesla", "deadline_max_a")),
    "ev_remaining_kwh": ("number", "kWh", ("tesla", "remaining_kwh")),
    "ev_charge_state": ("text", None, ("tesla", "charge_state")),
    "ev_need": ("text", None, ("tesla", "need")),
}

MANAGER_EVIDENCE_METRICS = {
    "manager_decision": ("text", None, ("manager", "decision")),
    "manager_reason": ("text", None, ("manager", "reason")),
    "manager_priority": ("text", None, ("manager", "priority")),
}

MANAGER_DEVICE = {
    "source_device_id": "em2:manager",
    "name": "EMS Manager",
    "device_type": "ems_manager",
}

PV_FRESHNESS_KEYS = {
    "pv_solaredge": "solarEdge",
    "pv_goodwe4200": "goodWe4200",
    "pv_goodwe2000": "goodWe2000",
}


def _value_at(payload, path):
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _source_resolution(payload):
    value = (payload.get("meta") or {}).get("min_publish_interval_sec")
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SOURCE_RESOLUTION_SECONDS
    if value <= 0 or value > 3600:
        return DEFAULT_SOURCE_RESOLUTION_SECONDS
    return value


def _ensure_metric(con, metric_key, value_type, unit=None):
    con.execute(
        """
        INSERT OR IGNORE INTO metrics
        (metric_key, unit, value_type, description)
        VALUES (?, ?, ?, ?)
        """,
        (metric_key, unit, value_type, "EMS analysis evidence"),
    )
    return con.execute(
        "SELECT id FROM metrics WHERE metric_key=?",
        (metric_key,),
    ).fetchone()[0]


def _ensure_device(con, device_key, spec):
    row = con.execute(
        "SELECT id FROM devices WHERE device_key=?",
        (device_key,),
    ).fetchone()
    if row:
        return row[0]

    con.execute(
        """
        INSERT INTO devices
        (source, source_device_id, device_key, name, device_type)
        VALUES ('homey_core_push', ?, ?, ?, ?)
        """,
        (
            spec["source_device_id"],
            device_key,
            spec["name"],
            spec["device_type"],
        ),
    )
    return con.execute(
        "SELECT id FROM devices WHERE device_key=?",
        (device_key,),
    ).fetchone()[0]


def _quality_for_power(payload, device_key):
    if device_key == "grid_p1":
        gate = _value_at(payload, ("balance", "control_gate", "grid_measurement_valid"))
        if gate is False:
            return None
        p1_fresh = _value_at(payload, ("balance", "source_timing", "p1Fresh"))
        return "observed" if p1_fresh is not False else "held"

    freshness_key = PV_FRESHNESS_KEYS.get(device_key)
    if freshness_key:
        fresh = _value_at(
            payload,
            ("balance", "source_timing", "freshness", freshness_key, "fresh"),
        )
        return "observed" if fresh is not False else "held"

    return "observed"


def archive_state_history(payload, db_path=HISTORY_DB):
    """Archive one already-validated Homey state snapshot in local SQLite.

    Duplicate source samples are ignored by the measurements uniqueness
    constraint, which also makes same-revision heartbeat pushes harmless.
    """
    meta = payload.get("meta") or {}
    ts = meta.get("source_sample_at")
    if not isinstance(ts, str) or not ts:
        raise ValueError("HISTORY_SOURCE_SAMPLE_AT_MISSING")

    resolution = _source_resolution(payload)
    con = sqlite3.connect(str(db_path), timeout=2.0)
    con.execute("PRAGMA busy_timeout=2000")

    try:
        power_metric = con.execute(
            "SELECT id FROM metrics WHERE metric_key='electrical_power_w'"
        ).fetchone()
        if not power_metric:
            raise RuntimeError("Metric electrical_power_w not found")
        power_metric_id = power_metric[0]

        con.execute(
            """
            INSERT OR IGNORE INTO metrics
            (metric_key, unit, value_type, description)
            VALUES ('active', NULL, 'boolean', 'Device active state')
            """
        )
        active_metric_id = con.execute(
            "SELECT id FROM metrics WHERE metric_key='active'"
        ).fetchone()[0]

        counter_metric_ids = {}
        for metric_key, description in (
            ("energy_import_kwh", "Cumulative lifetime grid import"),
            ("energy_export_kwh", "Cumulative lifetime grid export"),
            ("energy_produced_kwh", "Cumulative lifetime energy production"),
            ("energy_delivered_kwh", "Cumulative Easee delivered charging energy"),
        ):
            con.execute(
                """
                INSERT OR IGNORE INTO metrics
                (metric_key, unit, value_type, description)
                VALUES (?, 'kWh', 'number', ?)
                """,
                (metric_key, description),
            )
            counter_metric_ids[metric_key] = con.execute(
                "SELECT id FROM metrics WHERE metric_key=?",
                (metric_key,),
            ).fetchone()[0]

        inserted = 0
        skipped = 0

        for device_key, spec in POWER_DEVICES.items():
            value = _number(_value_at(payload, spec["path"]))
            quality = _quality_for_power(payload, device_key)
            if value is None or quality is None:
                skipped += 1
                continue

            device_id = _ensure_device(con, device_key, spec)
            cur = con.execute(
                """
                INSERT OR IGNORE INTO measurements
                (
                    ts_utc, device_id, metric_id, value_real,
                    quality, source_resolution_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, device_id, power_metric_id, value, quality, resolution),
            )
            inserted += cur.rowcount

        for device_key, counter_spec in COUNTER_DEVICES.items():
            device_id = _ensure_device(con, device_key, counter_spec["spec"])
            quality = _quality_for_power(payload, device_key)
            if quality is None:
                skipped += len(counter_spec["metrics"])
                continue
            for metric_key, path in counter_spec["metrics"].items():
                value = _number(_value_at(payload, path))
                if value is None or value < 0:
                    skipped += 1
                    continue
                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO measurements
                    (
                        ts_utc, device_id, metric_id, value_real,
                        quality, source_resolution_seconds
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ts, device_id, counter_metric_ids[metric_key], value, quality, resolution),
                )
                inserted += cur.rowcount

        for device_key, spec in STATE_DEVICES.items():
            value = _value_at(payload, spec["path"])
            if not isinstance(value, bool):
                skipped += 1
                continue

            device_id = _ensure_device(con, device_key, spec)
            cur = con.execute(
                """
                INSERT OR IGNORE INTO measurements
                (
                    ts_utc, device_id, metric_id, value_real,
                    quality, source_resolution_seconds
                )
                VALUES (?, ?, ?, ?, 'observed', ?)
                """,
                (ts, device_id, active_metric_id, 1.0 if value else 0.0, resolution),
            )
            inserted += cur.rowcount

        # Archive EV/manager observability already present in the canonical
        # Homey -> Pi state push. These rows are analysis evidence only; they
        # are never consumed by realtime control.
        tesla_spec = POWER_DEVICES["tesla"]
        tesla_device_id = _ensure_device(con, "tesla", tesla_spec)
        manager_device_id = _ensure_device(con, "ems_manager", MANAGER_DEVICE)

        for metric_key, (value_type, unit, path) in EV_EVIDENCE_METRICS.items():
            value = _value_at(payload, path)
            if value is None:
                continue
            metric_id = _ensure_metric(con, metric_key, value_type, unit)
            value_real = None
            value_text = None
            if value_type == "boolean":
                if not isinstance(value, bool):
                    continue
                value_real = 1.0 if value else 0.0
            elif value_type == "number":
                value_real = _number(value)
                if value_real is None:
                    continue
            else:
                value_text = str(value)
            cur = con.execute(
                """
                INSERT OR IGNORE INTO measurements
                (
                    ts_utc, device_id, metric_id, value_real, value_text,
                    quality, source_resolution_seconds
                )
                VALUES (?, ?, ?, ?, ?, 'observed', ?)
                """,
                (
                    ts, tesla_device_id, metric_id, value_real, value_text,
                    resolution,
                ),
            )
            inserted += cur.rowcount

        for metric_key, (value_type, unit, path) in MANAGER_EVIDENCE_METRICS.items():
            value = _value_at(payload, path)
            if value is None:
                continue
            metric_id = _ensure_metric(con, metric_key, value_type, unit)
            cur = con.execute(
                """
                INSERT OR IGNORE INTO measurements
                (
                    ts_utc, device_id, metric_id, value_real, value_text,
                    quality, source_resolution_seconds
                )
                VALUES (?, ?, ?, NULL, ?, 'observed', ?)
                """,
                (ts, manager_device_id, metric_id, str(value), resolution),
            )
            inserted += cur.rowcount

        con.commit()
        return {
            "archived": True,
            "inserted": inserted,
            "skipped": skipped,
            "source_sample_at": ts,
        }
    finally:
        con.close()

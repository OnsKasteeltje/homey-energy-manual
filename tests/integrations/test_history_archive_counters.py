import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "services/pi/api/status/history_archive.py"


def _load_archive():
    spec = importlib.util.spec_from_file_location("history_archive_under_test", ARCHIVE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_db(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_device_id TEXT NOT NULL UNIQUE,
        device_key TEXT NOT NULL UNIQUE,
        name TEXT,
        device_type TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_key TEXT NOT NULL UNIQUE,
        unit TEXT,
        value_type TEXT NOT NULL DEFAULT 'number',
        description TEXT
    );
    CREATE TABLE measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_utc TEXT NOT NULL,
        device_id INTEGER NOT NULL,
        metric_id INTEGER NOT NULL,
        value_real REAL,
        value_text TEXT,
        quality TEXT NOT NULL DEFAULT 'ok',
        source_resolution_seconds INTEGER,
        collected_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ts_utc, device_id, metric_id)
    );
    INSERT INTO metrics(metric_key, unit, value_type, description)
    VALUES ('electrical_power_w', 'W', 'number', 'power');
    """)
    con.commit()
    con.close()


def test_archive_cumulative_energy_counters(tmp_path):
    db = tmp_path / "history.sqlite"
    _create_db(db)
    payload = {
        "meta": {"source_sample_at": "2026-09-19T19:45:00Z", "min_publish_interval_sec": 300},
        "grid": {"power_w": 100.0, "energy_import_kwh": 36361.009, "energy_export_kwh": 31834.622},
        "pv": {
            "solaredge_w": 0.0, "goodwe_4200_w": 59.0, "goodwe_2000_w": 80.0,
            "solaredge_energy_kwh": 17351.444,
            "goodwe_4200_energy_kwh": 23772.8,
            "goodwe_2000_energy_kwh": 10708.9,
        },
        "balance": {
            "control_gate": {"grid_measurement_valid": True},
            "source_timing": {
                "p1Fresh": True,
                "freshness": {
                    "solarEdge": {"fresh": True},
                    "goodWe4200": {"fresh": True},
                    "goodWe2000": {"fresh": True},
                },
            },
        },
    }
    module = _load_archive()
    result = module.archive_state_history(payload, db)
    assert result["archived"] is True

    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT d.device_key, m.metric_key, x.value_real
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE m.metric_key LIKE 'energy_%_kwh'
        ORDER BY d.device_key, m.metric_key
    """).fetchall()
    con.close()

    assert rows == [
        ("grid_p1", "energy_export_kwh", 31834.622),
        ("grid_p1", "energy_import_kwh", 36361.009),
        ("pv_goodwe2000", "energy_produced_kwh", 10708.9),
        ("pv_goodwe4200", "energy_produced_kwh", 23772.8),
        ("pv_solaredge", "energy_produced_kwh", 17351.444),
    ]


def test_archive_stale_pv_counter_is_held(tmp_path):
    db = tmp_path / "history.sqlite"
    _create_db(db)
    payload = {
        "meta": {"source_sample_at": "2026-09-23T12:00:00Z", "min_publish_interval_sec": 300},
        "grid": {"power_w": -1000.0, "energy_import_kwh": 100.0, "energy_export_kwh": 50.0},
        "pv": {
            "solaredge_w": 900.0, "goodwe_4200_w": 0.0, "goodwe_2000_w": 0.0,
            "solaredge_energy_kwh": 1000.0,
            "goodwe_4200_energy_kwh": 2000.0,
            "goodwe_2000_energy_kwh": 3000.0,
        },
        "balance": {
            "control_gate": {"grid_measurement_valid": True},
            "source_timing": {
                "p1Fresh": True,
                "freshness": {
                    "solarEdge": {"fresh": True},
                    "goodWe4200": {"fresh": False},
                    "goodWe2000": {"fresh": False},
                },
            },
        },
    }
    module = _load_archive()
    module.archive_state_history(payload, db)

    con = sqlite3.connect(db)
    rows = con.execute("""
        SELECT d.device_key, x.quality
        FROM measurements x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE m.metric_key='energy_produced_kwh'
        ORDER BY d.device_key
    """).fetchall()
    con.close()

    assert rows == [
        ("pv_goodwe2000", "held"),
        ("pv_goodwe4200", "held"),
        ("pv_solaredge", "observed"),
    ]

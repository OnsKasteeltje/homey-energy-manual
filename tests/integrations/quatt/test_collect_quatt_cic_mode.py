"""Only two focused checks: payload safety and canonical archive semantics."""
import importlib.util
import io
import json
import sqlite3
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "services/pi/integrations/quatt/collect_quatt_cic_mode.py"
)
spec = importlib.util.spec_from_file_location("collect_quatt_cic_mode", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_readonly_feed_validates_modes_and_url():
    url = "http://192.168.1.182:8080/beta/feed/data.json"
    for mode in (0, 2, 3, 4, 96):
        opener = lambda requested, timeout: io.BytesIO(
            json.dumps({"qc": {"supervisoryControlMode": mode}}).encode()
        )
        assert module.fetch_mode(url, opener=opener) == mode

    for value in (None, False, True, "3", 2.0, -1, 65536):
        with pytest.raises(ValueError):
            module.mode_from_payload({"qc": {"supervisoryControlMode": value}})
    with pytest.raises(ValueError):
        module.mode_from_payload({})
    with pytest.raises(ValueError):
        module.validate_url("https://example.com/beta/feed/data.json")


def test_archive_reuses_quatt_device_and_is_idempotent(tmp_path):
    dbpath = tmp_path / "history.sqlite"
    with sqlite3.connect(dbpath) as db:
        db.executescript("""
            CREATE TABLE devices (id INTEGER PRIMARY KEY, device_key TEXT UNIQUE);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT UNIQUE,
                                  unit TEXT, value_type TEXT, description TEXT);
            CREATE TABLE measurements (
                ts_utc TEXT, device_id INTEGER, metric_id INTEGER, value_real REAL,
                quality TEXT, source_resolution_seconds INTEGER,
                UNIQUE(ts_utc, device_id, metric_id));
            INSERT INTO devices(device_key) VALUES ('quatt_cic');
        """)

    timestamp = "2026-10-16T18:12:00Z"
    assert module.archive_mode(dbpath, 3, timestamp) == 1
    assert module.archive_mode(dbpath, 3, timestamp) == 0

    with sqlite3.connect(dbpath) as db:
        records = db.execute("""
            SELECT d.device_key, m.metric_key, x.value_real, x.quality,
                   x.source_resolution_seconds
            FROM measurements x
            JOIN devices d ON x.device_id=d.id
            JOIN metrics m ON x.metric_id=m.id
        """).fetchall()
    assert records == [
        ("quatt_cic", "supervisory_control_mode", 3.0, "observed", 60)
    ]
    with pytest.raises(RuntimeError):
        module.archive_mode(tmp_path / "missing.sqlite", 0, timestamp)

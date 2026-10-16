#!/usr/bin/env python3
"""Single acceptance contract: publish good quarters; preserve last good on degraded input."""
import importlib.util
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/pi/ems-runtime/planner/pv-forecast/build_pv_history_profile.py"
SERVICE = (ROOT / "deploy/systemd/ems-pv-history-profile.service").read_text()
TIMER = (ROOT / "deploy/systemd/ems-pv-history-profile.timer").read_text()
DEPLOY = (ROOT / "scripts/deploy_ems_pi.sh").read_text()
CHAIN = (ROOT / "deploy/systemd/ems-forecast-chain.service").read_text()
assert "00:27:00 Europe/Amsterdam" in TIMER
assert "Persistent=true" in TIMER
assert "/runtime/planner/pv-forecast/build_pv_history_profile.py" in SERVICE
assert "systemctl enable --now ems-pv-history-profile.timer" in DEPLOY
assert "build_pv_history_profile.py" not in CHAIN

spec = importlib.util.spec_from_file_location("pv_daily_contract", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

with tempfile.TemporaryDirectory() as temp:
    mod.DB = Path(temp) / "history.sqlite"
    mod.OUTPUT = Path(temp) / "pv-history-profile.json"
    con = sqlite3.connect(mod.DB)
    con.executescript("""
        CREATE TABLE devices (id INTEGER, device_key TEXT);
        CREATE TABLE metrics (id INTEGER, metric_key TEXT);
        CREATE TABLE measurements_15m (
            slot_start_utc TEXT, device_id INTEGER, metric_id INTEGER,
            value_avg REAL, sample_count INTEGER, quality TEXT
        );
        INSERT INTO devices VALUES (1,'pv_solaredge');
        INSERT INTO devices VALUES (2,'pv_goodwe4200');
        INSERT INTO devices VALUES (3,'pv_goodwe2000');
        INSERT INTO metrics VALUES (1,'electrical_power_w');
    """)
    rows = []
    today = datetime.now(timezone.utc).date()
    for d in range(8):
        day = today - timedelta(days=8-d)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        for q in range(96):
            ts = (start + timedelta(minutes=15*q)).isoformat().replace("+00:00", "Z")
            for dev in (1, 2, 3):
                bad = (d == 7 and q == 48 and dev == 1)
                rows.append((ts, dev, 1, 250000 if bad else 1800 if q == 48 else 0,
                             3, "partial" if bad else "complete"))
    con.executemany("INSERT INTO measurements_15m VALUES (?,?,?,?,?,?)", rows)
    con.commit()

    mod.main()
    profile = json.loads(mod.OUTPUT.read_text())
    assert profile["usable_day_count"] >= 7
    assert profile["observed_quarter_bins"] == 96
    assert profile["complete_measurement_share"] >= .95
    assert max(b["clearEnvelopeW"] or 0 for b in profile["profile"].values()) < 10000
    accepted = mod.OUTPUT.read_bytes()

    con.execute("UPDATE measurements_15m SET quality='partial'")
    con.commit()
    try:
        mod.main()
    except RuntimeError as exc:
        assert "existing profile preserved" in str(exc)
    else:
        raise AssertionError("degraded input was promoted")
    assert mod.OUTPUT.read_bytes() == accepted
    con.close()
print("PASS: daily PV profile quality gate, atomic promotion and fallback")

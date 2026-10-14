#!/usr/bin/env python3
"""KISS daily report archive regression; no pytest or production writes."""

import importlib.util
import json
import tempfile
from pathlib import Path

SOURCE = Path("services/pi/history/daily_performance_evaluation.py")
spec = importlib.util.spec_from_file_location("daily_performance_archive", SOURCE)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

def sample(date_text, exp):
    return {
        "schema": app.SCHEMA,
        "dateLocal": date_text,
        "status": "READY", "readOnly": True, "controlWrites": False,
        "accounting": {"gridExportKWh": exp, "authority": "P1_CUMULATIVE_ENERGY_COUNTERS"},
    }

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "archive.json"
    latest = Path(tmp) / "latest.json"
    app._write_atomic(latest, sample("2026-10-13", 3.347))
    app._update_archive(path, sample("2026-10-12", 1.234))
    app._update_archive(path, sample("2026-10-13", 3.347))
    app._update_archive(path, sample("2026-10-12", 1.238))  # one-day backfill/reconciliation
    d = json.loads(path.read_text())
    assert d["schema"] == "EMS_PI_DAILY_PERFORMANCE_ARCHIVE_V0.1"
    assert list(d["days"]) == ["2026-10-12", "2026-10-13"]
    assert d["days"]["2026-10-12"]["accounting"]["gridExportKWh"] == 1.238
    assert d["days"]["2026-10-13"]["accounting"]["gridExportKWh"] == 3.347
    assert json.loads(latest.read_text())["dateLocal"] == "2026-10-13"

    # A malformed archive must never silently be overwritten.
    path.write_text('{"schema":"UNKNOWN","days":{}}')
    try:
        app._update_archive(path, sample("2026-10-11", 0.7))
    except ValueError:
        pass
    else:
        raise AssertionError("Malformed archive overwritten")

source = SOURCE.read_text(encoding="utf-8")
assert 'parser.add_argument("--archive-only"' in source
assert 'parser.add_argument("--no-write-output"' in source
assert 'if not args.no_write_output:' in source
assert 'if not args.archive_only:' in source
assert 'if args.no_write_output and args.archive_only:' in source
assert '"--no-write-output"' in source
print("PASS: daily archive atomic updates, historical backfill and latest preservation")

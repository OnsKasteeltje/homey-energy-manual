#!/usr/bin/env python3
"""V2-only orientation correction; evidence from old forecasts is immutable."""
import json
from pathlib import Path
src=Path("services/pi/forecast/pv/build_pv_forecast_v2.py").read_text()
cfg=json.loads(Path("src/pi/ems-runtime/planner/pv-forecast/pv-array-config.json").read_text())
assert 'PV_ARRAYS = [("goodwe2000", -45, 30), ("goodwe4200", 45, 30), ("solaredge", 45, 25)]' in src
assert cfg["arrays"]["goodwe2000"]["azimuth_deg"] == -45
assert cfg["arrays"]["goodwe4200"]["azimuth_deg"] == 45
assert cfg["arrays"]["solaredge"]["azimuth_deg"] == 45
assert 'AZIMUTH_FIXED_V2_20261010' in src
assert 'HISTORICAL_ENVELOPE_CLOUD_ADJUSTED_AZIMUTH_FIXED_V2' in src
archive=Path("services/pi/forecast/pv/archive_forecast.py").read_text()
assert 'INSERT OR IGNORE INTO pv_forecast_v2_archive' in archive
print("PASS: corrected ZO/ZW azimuth in shadow V2; past archive unchanged")

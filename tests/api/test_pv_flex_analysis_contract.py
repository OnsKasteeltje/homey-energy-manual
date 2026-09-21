#!/usr/bin/env python3
"""Contract checks for the read-only PV & Flex Analysis V2 web resource."""

from pathlib import Path

p = Path("services/pi/api/web-data/server.py")
s = p.read_text(encoding="utf-8")

required = [
    'PV_FLEX_API_SCHEMA = "EMS_WEB_PV_FLEX_ANALYSIS_V1"',
    'def pv_flex_analysis_resource(value):',
    '"mode": "READ_ONLY"',
    '"controlWrites": False',
    '"realtimeAuthority": "P1"',
    '"kind": "FIXED_LEAD_12H"',
    '"SOURCE_NOT_YET_INTEGRATED"',
    'd.device_key=\'tesla\'',
    'd.device_key=\'boiler\'',
    '["web", "analysis", "pv-flex", "day"]',
]
for token in required:
    assert token in s, token

for forbidden in (
    "requests.post(",
    "requests.put(",
    "requests.patch(",
    "forecastExportW",
):
    assert forbidden not in s, forbidden

assert "julianday(f2.generated_at) <= julianday(f.slot_start_utc) - (12.0/24.0)" in s, "forecast selection must enforce 12h no-hindsight lead"
assert 'max(0.0, totals["pvKWh"] - totals["exportKWh"])' in s, "daily PV self-use must derive from the daily energy balance"
assert "quality != \"observed\"" in s, "non-observed actuals must not be treated as measured truth"
print("PASS: PV & Flex Analysis V2 read-only contract")

#!/usr/bin/env python3
"""Static contract checks for the shadow PV Forecast V2 builder and archive."""
from pathlib import Path

p = Path("services/pi/forecast/pv/build_pv_forecast_v2.py")
s = p.read_text()
required = [
    'CLOSED_VALIDATED_HISTORY_ONLY',
    'prev_map',
    'EMS_PI_PV_FORECAST_V2_CONFIDENCE_STATE',
    '"recentLocalAccuracy"',
    '"forecastConsistency"',
    '"EMS_PI_PV_FORECAST_V2"',
    '"realtimeAuthority": "P1"',
    '"forecastMeaning": "PV_PRODUCTION_NOT_GUARANTEED_EXPORT"',
    '"confidenceAdvisoryOnly": True',
    '"controlWrites": False',
    '"geometryBasis": "ARRAY_GTI" if gti_complete else "HORIZONTAL_RADIATION_FALLBACK"',
    'confidence = None',
    'PV_ARRAYS =',
    '"arrayCapacityBasis": "NOT_ASSUMED_FROM_INVERTER_AC_RATING"',
]
for token in required:
    assert token in s, token
for forbidden in ("base-load-forecast", "quatt-forecast", "forecastExportW", "3680),", "4200),", "2000),"):
    assert forbidden not in s, forbidden
assert "energy-state-v2.json" not in s, "PV forecast must not use live energy state for model accuracy"

archive = Path("services/pi/forecast/pv/archive_forecast.py").read_text()
for token in (
    "idx_pv_forecast_v2_slot_generated",
    "ON pv_forecast_v2_archive(slot_start_utc, generated_at)",
    "CREATE INDEX IF NOT EXISTS",
):
    assert token in archive, token

# One intentional tuning value for both the active V1 and read-only V2 builders.
# Guard against silently reverting to the former 85% sunny-day envelope.
v1 = Path("src/pi/ems-runtime/planner/pv-forecast/fetch_pv_forecast.py").read_text()
assert "HISTORICAL_WEIGHT = 0.20" in v1
assert "HISTORICAL_WEIGHT = 0.20" in s

print("PASS: PV Forecast V2 static contract")

#!/usr/bin/env python3
"""Focused proof of source-refresh isolation, bounded reuse, and fail-closed."""
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORECAST = ROOT / "services/pi/forecast"
sys.path.insert(0, str(FORECAST))
spec = importlib.util.spec_from_file_location("source_cache_contract", FORECAST / "open_meteo_cache.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
UTC = timezone.utc
now = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)

def valid_source(name, at=now):
    base = module.floor_quarter(at)
    times = [(base + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(104)]
    fields = module.SOURCE_FIELDS[name]
    return {"minutely_15": {"time": times, **{k: [600] * len(times) for k in fields}}}

def valid_bundle(at=now):
    return {k: valid_source(k, at) for k in module.SOURCE_FIELDS}

# Same source must be reusable across three quarter cycles without network access.
source = valid_bundle()
module.validate_sources(source, now)
with tempfile.TemporaryDirectory() as t:
    path = Path(t) / "cache.json"
    attempts = []
    def fetch(request, *, label):
        attempts.append(label)
        return source[label]

    result = module.refresh(path=path, fetch=fetch, clock=lambda: now)
    assert attempts == list(module.SOURCE_FIELDS)
    assert result["controlWrites"] is False
    assert module.load_snapshot(path, now + timedelta(minutes=15))["sources"]["weather"]
    assert module.load_snapshot(path, now + timedelta(minutes=30))["sources"]["weather"]
    assert module.load_snapshot(path, now + timedelta(minutes=90))["sources"]["weather"]
    try:
        module.load_snapshot(path, now + timedelta(minutes=90, seconds=1))
        raise AssertionError("stale source must fail closed")
    except ValueError as exc:
        assert "stale" in str(exc)

    # A failed intermediate GTI request never overwrites the complete prior cache.
    before = path.read_bytes()
    def broken(request, *, label):
        if label == "gti_goodwe4200":
            raise RuntimeError("HTTP 503 after bounded retries")
        return source[label]
    try:
        module.refresh(path=path, fetch=broken, clock=lambda: now + timedelta(minutes=30))
        raise AssertionError("source refresh must fail")
    except RuntimeError:
        pass
    assert path.read_bytes() == before

    # A missing source/slot is NEVER silently replaced by zero.
    broken_bundle = valid_bundle()
    broken_bundle["gti_solaredge"]["minutely_15"]["time"].pop(8)
    broken_bundle["gti_solaredge"]["minutely_15"]["global_tilted_irradiance"].pop(8)
    try:
        module.validate_sources(broken_bundle, now)
        raise AssertionError("missing quarter must fail")
    except ValueError as exc:
        assert "missing forecast slot" in str(exc)

    for field in ("shortwave_radiation", "terrestrial_radiation"):
        broken_bundle = valid_bundle()
        broken_bundle["weather"]["minutely_15"][field][1] = None
        try:
            module.validate_sources(broken_bundle, now)
            raise AssertionError(f"missing {field} must fail")
        except ValueError:
            pass

# Full-horizon source coverage must also decay with the clock even before age cap.
try:
    module.validate_sources(valid_bundle(), now + timedelta(hours=3))
    raise AssertionError("insufficient horizon must fail")
except ValueError as exc:
    assert "missing forecast slot" in str(exc)

w = (ROOT / "src/pi/ems-runtime/planner/weather-forecast/fetch_weather_forecast.py").read_text()
p = (ROOT / "src/pi/ems-runtime/planner/pv-forecast/fetch_pv_forecast.py").read_text()
h = (ROOT / "src/pi/ems-runtime/planner/dynamic-plan/build_hardened_dynamic_shadow_plan.py").read_text()
chain = (ROOT / "deploy/systemd/ems-forecast-chain.service").read_text()
assert "load_snapshot()" in w and "load_snapshot()" in p
assert "fetch_json_with_retry" not in w and "fetch_json_with_retry" not in p
assert "sourceFetchedAt" in w and "sourceFetchedAt" in p
assert "sourceFetchedAt" in h and "sourceMaxAgeSec" in h
assert "open_meteo_cache.py" not in chain
print("PASS: 30-minute Open-Meteo intake, 15-minute offline planner, 90m source age/horizon gate")

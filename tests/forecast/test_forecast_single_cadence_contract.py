#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEALTH = ROOT / "services/pi/health/ems_health.py"
DEPLOY = ROOT / "scripts/deploy_ems_pi.sh"
DRIFT = ROOT / "scripts/ems_pi_drift_check.sh"
CHAIN_TIMER = ROOT / "deploy/systemd/ems-forecast-chain.timer"
LEGACY_UNITS = (
    "ems-weather-forecast.timer",
    "ems-weather-forecast.service",
    "ems-pv-forecast.timer",
    "ems-pv-forecast.service",
)


def load_health():
    spec = importlib.util.spec_from_file_location("ems_health_forecast_contract", HEALTH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    health = load_health()

    assert "forecastChain" in health.FUNCTION_UNITS
    assert "weatherForecast" not in health.FUNCTION_UNITS
    assert "weatherForecast" in health.DATA_SOURCES
    assert "pvForecast" in health.DATA_SOURCES

    chain_timer = CHAIN_TIMER.read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* *:03,18,33,48:00" in chain_timer

    # Retired standalone producers must no longer exist in canonical systemd source.
    for unit in LEGACY_UNITS:
        assert not (ROOT / "deploy/systemd" / unit).exists(), unit

    deploy = DEPLOY.read_text(encoding="utf-8")
    assert "RETIRED_FORECAST_TIMERS" in deploy
    assert "RETIRED_FORECAST_SERVICES" in deploy
    assert "RETIRED_FORECAST_UNITS" in deploy
    assert 'systemctl disable --now "$unit"' in deploy
    assert 'systemctl stop "$unit"' in deploy
    assert 'rm -f "/etc/systemd/system/$unit"' in deploy
    for unit in LEGACY_UNITS:
        assert unit in deploy

    drift = DRIFT.read_text(encoding="utf-8")
    assert "RETIRED_FORECAST_UNITS" in drift
    assert "STALE RETIRED UNIT" in drift
    for unit in LEGACY_UNITS:
        assert unit in drift

    print("PASS: atomic forecast single-cadence retirement contract")


if __name__ == "__main__":
    main()

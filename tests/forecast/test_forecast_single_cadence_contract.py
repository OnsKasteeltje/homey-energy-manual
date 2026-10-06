#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEALTH = ROOT / "services/pi/health/ems_health.py"
DEPLOY = ROOT / "scripts/deploy_ems_pi.sh"
CHAIN_TIMER = ROOT / "deploy/systemd/ems-forecast-chain.timer"
WEATHER_TIMER = ROOT / "deploy/systemd/ems-weather-forecast.timer"
PV_TIMER = ROOT / "deploy/systemd/ems-pv-forecast.timer"


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

    deploy = DEPLOY.read_text(encoding="utf-8")
    for unit in (
        "ems-weather-forecast.timer",
        "ems-pv-forecast.timer",
    ):
        assert unit in deploy
    assert "PARKED_FORECAST_TIMERS" in deploy
    assert 'systemctl disable --now "$unit"' in deploy
    assert 'systemctl is-active --quiet "$unit"' in deploy
    assert 'systemctl is-enabled --quiet "$unit"' in deploy

    chain_timer = CHAIN_TIMER.read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* *:03,18,33,48:00" in chain_timer

    for path in (WEATHER_TIMER, PV_TIMER):
        source = path.read_text(encoding="utf-8")
        assert "PARKED LEGACY" in source
        assert "ems-forecast-chain.timer" in source

    print("PASS: atomic forecast single-cadence contract")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"
PERFORMANCE = ROOT / "services/pi/history/ems_performance.py"
ARCHIVE = ROOT / "services/pi/api/status/history_archive.py"


def main():
    server = SERVER.read_text(encoding="utf-8")
    performance = PERFORMANCE.read_text(encoding="utf-8")
    archive = ARCHIVE.read_text(encoding="utf-8")

    assert "performance.evEnergyAccounting.authoritativeChargedEnergy" in server
    assert "the only authoritative charged-kWh field when available" in server
    assert "derivedSourceAllocation" in server
    assert "must be described as Afleiding" in server
    assert "do not silently substitute the power-integrated value" in server

    assert '"energy_delivered_kwh": ("tesla", "meter_kwh")' in archive
    assert "Cumulative Easee delivered energy" in archive

    assert '"evEnergyAccounting": ev_energy_accounting' in performance
    assert '"authoritativeChargedEnergy"' in performance
    assert '"DERIVED_FROM_SAMPLED_POWER_INTEGRATION"' in performance
    assert '"SIMULTANEOUS_POWER_ALLOCATION_EV_FIRST_V0.1"' in performance
    assert '"measuredDirectly": False' in performance

    constrained = (
        ROOT / "services/pi/history/constrained_replay_v0_1.py"
    ).read_text(encoding="utf-8")
    assert "EMS_PI_CONSTRAINED_REPLAY_V0.1.1" in constrained

    print("PASS: AI EV energy accounting semantics contract")


if __name__ == "__main__":
    main()

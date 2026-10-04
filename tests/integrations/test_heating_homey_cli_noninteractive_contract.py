#!/usr/bin/env python3
"""Regression contract for noninteractive Homey CLI use in Heating SHADOW."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PUBLISHER = ROOT / "services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py"
COMMISSION = ROOT / "services/pi/commissioning/install_heating_homey_shadow_chain_v0_1.py"
SERVICE = ROOT / "deploy/systemd/ems-heating-homey-shadow-publish.service"


def require_env(text: str, label: str) -> None:
    assert 'HOMEY_SKIP_STARTUP_NOTIFIERS' in text, label
    assert 'NO_UPDATE_NOTIFIER' in text, label


def main() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    commission = COMMISSION.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    require_env(publisher, "publisher")
    require_env(commission, "commissioning")

    assert "Environment=HOMEY_SKIP_STARTUP_NOTIFIERS=1" in service
    assert "Environment=NO_UPDATE_NOTIFIER=1" in service

    # Keep the sandbox strict. The fix must suppress nonessential CLI startup
    # writes, not grant the CLI write access to the user's home/config tree.
    assert "ProtectHome=read-only" in service
    assert "ReadWritePaths=/home/jeroen/ems/data" in service
    assert "ReadWritePaths=/home/jeroen/.config" not in service
    assert "ProtectHome=false" not in service

    print("PASS: Heating Homey CLI runs noninteractively without writable home")


if __name__ == "__main__":
    main()

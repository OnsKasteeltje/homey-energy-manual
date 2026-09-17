from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLISHER = ROOT / "services/pi/integrations/github/publish_energy_state.py"
SERVICE = ROOT / "deploy/systemd/ems-energy-state-publication.service"
TIMER = ROOT / "deploy/systemd/ems-energy-state-publication.timer"
LEGACY = ROOT / "src/pi/ems-runtime/publisher/publish_energy_state.py"


def test_publisher_is_target_structure_and_observability_only():
    text = PUBLISHER.read_text(encoding="utf-8")
    assert 'TARGET = "docs/data/energy-state-v2.json"' in text
    assert 'SOURCE = Path("/home/jeroen/ems/data/energy-state-v2.json")' in text
    assert 'meta["publish_reason"] = "PI_TELEMETRY"' in text
    assert "/control/current" not in text
    assert "EM2_Power_Intent" not in text
    assert "homey" not in text.lower()
    assert not LEGACY.exists()


def test_systemd_unit_is_observability_only_and_uses_target_path():
    service = SERVICE.read_text(encoding="utf-8")
    timer = TIMER.read_text(encoding="utf-8")
    assert "services/pi/integrations/github/publish_energy_state.py" in service
    assert "OBSERVABILITY ONLY" in service
    assert "OnCalendar=*:0/15" in timer
    assert "ems-energy-state-publication.service" in timer
    assert "ems-pi-control-publish" not in service + timer

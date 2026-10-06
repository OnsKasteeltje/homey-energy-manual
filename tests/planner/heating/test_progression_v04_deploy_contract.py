from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / "deploy/install/install_heating_preheat_progression_shadow_v0_4.sh"
SERVICE = ROOT / "deploy/systemd/ems-heating-preheat-progression-shadow.service"


def test_v04_installer_validates_step_history_contract():
    source = INSTALLER.read_text()

    assert 'stepHistoryRetentionHours")==48' in source
    assert 'history=room.get("stepHistory")' in source
    assert "assert isinstance(history,list)" in source
    assert 'interval.get("startedAt")' in source
    assert 'interval.get("endedAt")' in source
    assert "assert ended >= started" in source
    assert 'assert "physicalWritePerformed" not in interval' in source


def test_v04_installer_keeps_shadow_write_guards():
    source = INSTALLER.read_text()

    assert 'd.get("controlWrites") is False' in source
    assert 'd.get("physicalWriteAllowed") is False' in source
    assert 'progression.get("physicalWritePerformed") is False' in source
    assert 'rollbackBehavior")=="NOT_DEFINED_SHADOW_ONLY"' in source


def test_v04_service_builds_production_grant_before_progression():
    source = SERVICE.read_text()

    assert "run_heating_production_grant_v0_1.py" in source
    assert "run_heating_preheat_progression_shadow_v0_4.py" in source
    assert source.index("ExecStartPre=") < source.index("ExecStart=")
    assert "Homey" not in source

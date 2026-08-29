import pytest

from config import Settings
from gateways.mock_homey import MockHomeyGateway


def test_default_mode_is_shadow():
    settings = Settings(_env_file=None)
    assert settings.ems_mode == 'SHADOW'
    settings.assert_safe_mode()


def test_live_mode_is_rejected():
    settings = Settings(EMS_MODE='LIVE', _env_file=None)
    with pytest.raises(RuntimeError):
        settings.assert_safe_mode()


@pytest.mark.asyncio
async def test_mock_gateway_forbids_physical_write():
    gateway = MockHomeyGateway()
    with pytest.raises(RuntimeError):
        await gateway.write_device('easee', {'current_A': 10})


@pytest.mark.asyncio
async def test_mock_gateway_reads_fixture_once():
    gateway = MockHomeyGateway(devices={'p1': {'power_W': 123}})
    result = await gateway.read_device('p1')
    assert result['power_W'] == 123
    assert gateway.reads_total == 1

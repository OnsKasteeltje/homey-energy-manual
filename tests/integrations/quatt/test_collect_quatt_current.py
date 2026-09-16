import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[3] / "services/pi/integrations/quatt/collect_quatt_current.py"
spec = importlib.util.spec_from_file_location("collect_quatt_current", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_numeric_value_preserves_numeric_semantics():
    assert module.numeric_value(True) == 1.0
    assert module.numeric_value(False) == 0.0
    assert module.numeric_value(12) == 12.0
    assert module.numeric_value(1.25) == 1.25
    assert module.numeric_value("12") is None
    assert module.numeric_value(None) is None


def test_capability_is_read_only_projection():
    caps = {"measure_power": {"value": 321, "lastUpdated": "2026-09-16T12:00:00Z", "extra": "ignored"}}
    assert module.capability(caps, "measure_power") == {
        "value": 321,
        "sourceLastUpdated": "2026-09-16T12:00:00Z",
    }
    assert module.capability(caps, "missing") is None


def test_quatt_collector_keeps_existing_schema_and_read_only_mode():
    source = MODULE_PATH.read_text()
    assert '"EMS_QUATT_CURRENT_STATE_V0.1"' in source
    assert '"mode": "READ_ONLY"' in source
    assert "set-capability" not in source

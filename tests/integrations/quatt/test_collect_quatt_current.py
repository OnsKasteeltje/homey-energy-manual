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
    assert module.capability(caps, "measure_power", "2026-09-27T07:00:00Z") == {
        "value": 321,
        "observedAt": "2026-09-27T07:00:00Z",
        "sourceLastUpdated": "2026-09-16T12:00:00Z",
    }
    assert module.capability(caps, "missing", "2026-09-27T07:00:00Z") is None


def test_quatt_collector_keeps_existing_schema_and_read_only_mode():
    source = MODULE_PATH.read_text()
    assert '"EMS_QUATT_CURRENT_STATE_V0.1"' in source
    assert '"mode": "READ_ONLY"' in source
    assert "set-capability" not in source


def test_cv_active_is_canonical_observer_name():
    assert module.OBSERVER_ONLY["measure_boiler_cic_central_heating_onoff_boiler"] == "cvActive"
    assert "boilerAssistOn" not in module.OBSERVER_ONLY.values()


def test_observed_at_is_independent_of_source_last_updated():
    caps = {
        "measure_boiler_cic_central_heating_onoff_boiler": {
            "value": False,
            "lastUpdated": "2026-09-25T07:15:32Z",
        }
    }
    state = module.capability(
        caps,
        "measure_boiler_cic_central_heating_onoff_boiler",
        "2026-09-27T07:10:55Z",
    )
    assert state["value"] is False
    assert state["observedAt"] == "2026-09-27T07:10:55Z"
    assert state["sourceLastUpdated"] == "2026-09-25T07:15:32Z"

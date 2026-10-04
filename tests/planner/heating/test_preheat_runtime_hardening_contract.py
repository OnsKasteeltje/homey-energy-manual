import importlib.util
from pathlib import Path


RUNNER = Path(__file__).parents[3] / "services/pi/planner/heating/run_heating_preheat_shadow_v0_3.py"
DEPLOY = Path(__file__).parents[3] / "scripts/deploy_ems_pi.sh"

spec = importlib.util.spec_from_file_location("run_heating_preheat_shadow_v0_3", RUNNER)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_missing_quatt_artifact_becomes_invalid_fail_closed_source(tmp_path):
    source = m.load_optional_json(tmp_path / "missing-quatt.json", label="Quatt current")
    assert source["schema"] is None
    assert source["mode"] == "READ_ONLY"
    assert source["sourceError"] == "FileNotFoundError"


def test_malformed_quatt_artifact_becomes_invalid_fail_closed_source(tmp_path):
    path = tmp_path / "quatt-current.json"
    path.write_text("{not-json", encoding="utf-8")
    source = m.load_optional_json(path, label="Quatt current")
    assert source["schema"] is None
    assert source["mode"] == "READ_ONLY"
    assert source["sourceError"] == "JSONDecodeError"


def test_generic_pi_deploy_preserves_derived_thermal_runtime_state():
    source = DEPLOY.read_text()
    assert "-not -path './thermal/*'" in source
    assert "--exclude='thermal/'" in source

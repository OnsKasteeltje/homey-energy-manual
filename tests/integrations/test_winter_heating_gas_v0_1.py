"""Two risk-based checks: approximate day attribution and incomplete gaps."""
import importlib.util
from pathlib import Path

PATH = (Path(__file__).resolve().parents[2] / "services/pi/history/winter_heating_gas_v0_1.py")
spec = importlib.util.spec_from_file_location("winter_gas", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample(values):
    hours = ["2025-12-31T18:00:00Z", "2026-01-01T00:00:00Z",
             "2026-01-01T06:00:00Z", "2026-01-01T12:00:00Z",
             "2026-01-01T18:00:00Z"]
    return [{"t": t, "v": v} for t, v in zip(hours, values)]


def evidence(gas):
    return {"schema": "EMS_WINTER_HEATING_GAS_EVIDENCE_V0.1", "series": {
        "gas_m3": {"2026": gas},
        "outside_c": {"2026": sample([5, 5, 5, 5, 5])[1:]},
        "woonkamer_target_c": {"2026": sample([19, 19, 19, 19, 19])},
        "woonkamer_actual_c": {"2026": sample([18, 18, 18, 18, 18])},
    }}


def test_complete_day_uses_counter_differences_without_room_gas_allocation():
    result = mod.evaluate(evidence(sample([100, 100.25, 100.50, 100.75, 101])),
                          "2026-01-01", "2026-01-02")
    assert result["days"][0]["quality"] == "approx_6h"
    assert result["days"][0]["gas_m3"] == 1.0
    assert result["months"][0]["observed_days"] == 1
    assert result["rooms"][0]["pct_target_above_actual_by_05c"] == 100.0
    assert "gas_by_room" not in result


def test_missing_six_hour_counter_bucket_is_incomplete_not_interpolated():
    points = sample([100, 100.25, 100.5, 100.75, 101])
    result = mod.evaluate(evidence([p for p in points if p["t"] != "2026-01-01T12:00:00Z"]),
                          "2026-01-01", "2026-01-02")
    assert result["rejected_gas_intervals"] == 1
    assert result["days"][0]["quality"] == "incomplete"
    assert result["days"][0]["gas_m3"] is None
    assert result["months"][0]["observed_days"] == 0

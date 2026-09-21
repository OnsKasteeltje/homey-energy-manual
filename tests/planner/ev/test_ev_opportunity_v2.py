#!/usr/bin/env python3
import importlib.util
from pathlib import Path

P = Path(__file__).parents[3] / "services/pi/planner/ev/build_ev_opportunity_v2.py"
spec = importlib.util.spec_from_file_location("ev_v2", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_start_thresholds_and_forecast_role():
    assert m.decide_start(p1_export_w=1999, better_normal_opportunity_later=False).mode == "OFF"
    assert m.decide_start(p1_export_w=2500, better_normal_opportunity_later=True).mode == "OFF"
    d = m.decide_start(p1_export_w=2500, better_normal_opportunity_later=False)
    assert (d.mode, d.target_a) == ("GRAY_OPPORTUNITY", 6)
    d = m.decide_start(p1_export_w=4140, better_normal_opportunity_later=True)
    assert (d.mode, d.target_a) == ("NORMAL_PV_OPPORTUNITY", 6)


def test_gray_hold_stop_and_promotion():
    assert m.modulate(mode="GRAY_OPPORTUNITY", samples_w=[2500]*5).target_a == 6
    assert m.modulate(mode="GRAY_OPPORTUNITY", samples_w=[1900]*5).mode == "OFF"
    d = m.modulate(mode="GRAY_OPPORTUNITY", samples_w=[5000]*5)
    assert (d.mode, d.target_a) == ("NORMAL_PV_OPPORTUNITY", 7)


def test_normal_does_not_fall_back_to_gray():
    d = m.modulate(mode="NORMAL_PV_OPPORTUNITY", samples_w=[3500]*5)
    assert (d.mode, d.target_a) == ("OFF", 0)


def test_modulation_is_symmetric_and_direct():
    up = m.modulate(mode="NORMAL_PV_OPPORTUNITY", samples_w=[7600]*5)
    down = m.modulate(mode="NORMAL_PV_OPPORTUNITY", samples_w=[4830]*5)
    assert up.target_a == 11
    assert down.target_a == 7


def test_reconstruct_available_pv_and_latest_five_average():
    assert m.available_pv_w(ev_power_w=4140, p1_export_w=0, p1_import_w=1640) == 2500
    assert m.rolling_average_w([1000,2000,3000,4000,5000,6000]) == 4000


def test_gray_forecast_uses_relative_pv_uplift_not_absolute_production():
    slots = [
        {"start":"2026-09-20T11:00:00Z","pvForecastW":5000,"confidence":0.2},
        {"start":"2026-09-20T11:15:00Z","pvForecastW":6200,"confidence":0.9},
    ]
    # 2500 W measured export + (5000-4000) forecast uplift = 3500: not normal.
    # 2500 W + (6200-4000) = 4700: a better normal opportunity exists.
    assert m.better_normal_opportunity_later(
        p1_export_w=2500, now_forecast_w=4000, future_slots=slots
    ) is True


def test_gray_forecast_respects_requirement_horizon():
    slots = [{"start":"2026-09-20T14:00:00Z","pvForecastW":7000}]
    assert m.better_normal_opportunity_later(
        p1_export_w=2500, now_forecast_w=4000, future_slots=slots,
        horizon_end="2026-09-20T13:00:00Z",
    ) is False


def test_gray_forecast_confidence_is_not_gate():
    slots = [{"start":"2026-09-20T11:00:00Z","pvForecastW":6000,"confidence":0.01}]
    assert m.better_normal_opportunity_later(
        p1_export_w=2500, now_forecast_w=4000, future_slots=slots
    ) is True

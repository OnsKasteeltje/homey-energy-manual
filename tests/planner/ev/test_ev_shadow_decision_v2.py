#!/usr/bin/env python3
import importlib.util, sys
from pathlib import Path

D = Path(__file__).parents[3] / "services/pi/planner/ev"
sys.path.insert(0, str(D))
P = D / "build_ev_shadow_decision_v2.py"
spec = importlib.util.spec_from_file_location("ev_shadow_v2", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def base(**overrides):
    x=dict(connected=True,current_mode="OFF",p1_export_w=2500,now_forecast_w=4000,
           future_slots=[],available_pv_samples_w=[],deadline_active=False,
           deadline_required_now=False,deadline_max_a=None,horizon_end=None)
    x.update(overrides); return x


def test_disconnected_is_off():
    assert m.decide_ev_shadow(**base(connected=False))["mode"] == "OFF"


def test_gray_start_when_no_better_future():
    d=m.decide_ev_shadow(**base())
    assert (d["mode"],d["targetA"]) == ("GRAY_OPPORTUNITY",6)


def test_gray_waits_when_normal_future_exists():
    d=m.decide_ev_shadow(**base(future_slots=[{"start":"2026-09-20T12:00:00Z","pvForecastW":6000}]))
    assert (d["mode"],d["targetA"]) == ("OFF",0)


def test_active_normal_modulates_from_rolling_samples():
    d=m.decide_ev_shadow(**base(current_mode="NORMAL_PV_OPPORTUNITY",
        available_pv_samples_w=[6900]*5))
    assert (d["mode"],d["targetA"]) == ("NORMAL_PV_OPPORTUNITY",10)


def test_deadline_has_priority_over_opportunity():
    d=m.decide_ev_shadow(**base(current_mode="NORMAL_PV_OPPORTUNITY",
        available_pv_samples_w=[7600]*5,deadline_active=True,
        deadline_required_now=True,deadline_max_a=13))
    assert (d["mode"],d["targetA"],d["reason"]) == ("DEADLINE",13,"HARD_DEADLINE_REQUIRED_NOW")


def test_invalid_deadline_limit_fails_closed():
    d=m.decide_ev_shadow(**base(deadline_active=True,deadline_required_now=True,deadline_max_a=20))
    assert (d["mode"],d["targetA"]) == ("OFF",0)

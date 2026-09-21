#!/usr/bin/env python3
import importlib.util
from pathlib import Path
P=Path(__file__).parents[3]/"services/pi/planner/ev/model_homey_rolling_v2.py"
s=importlib.util.spec_from_file_location("r",P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)

def test_homey_p1_sign_reconstruction():
    assert m.available_pv_from_homey(p1_measure_power_w=-2500,ev_actual_power_w=0)==2500
    assert m.available_pv_from_homey(p1_measure_power_w=1640,ev_actual_power_w=4140)==2500

def test_keeps_latest_five_and_average():
    x=[]
    for i,w in enumerate([1000,2000,3000,4000,5000,6000]):
        x=m.append_sample(x,at=f"2026-09-20T12:0{i}:00Z",available_pv_w=w)
    assert len(x)==5
    assert m.rolling_w(x)==4000

def test_same_timestamp_replaces_by_newest_append_semantics():
    x=m.append_sample([],at="2026-09-20T12:00:00Z",available_pv_w=2000)
    x=m.append_sample(x,at="2026-09-20T12:00:00Z",available_pv_w=3000)
    assert len(x)==1 and m.rolling_w(x)==3000

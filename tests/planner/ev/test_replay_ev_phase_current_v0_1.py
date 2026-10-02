import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "pi"
    / "planner"
    / "ev"
    / "replay_ev_phase_current_v0_1.py"
)
spec = importlib.util.spec_from_file_location("ev_replay_v01", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def ts(seconds):
    return datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def sample(seconds, available_w):
    # With EV actual=0, negative P1 means exactly the requested reconstructed surplus.
    return m.Sample(ts(seconds), p1_w=-available_w, ev_actual_w=0)


def test_candidate_off_to_1p_requires_sustained_rolling_window():
    state = m.State(mode="OFF", mode_since=ts(-1000))
    rolling = m.Rolling()

    avg, ready, _ = rolling.add(ts(0), 1700)
    s0 = m.candidate_policy_step(state, sample(0, 1700), avg, ready)
    assert s0.mode == "OFF"

    avg, ready, _ = rolling.add(ts(95), 1700)
    s1 = m.candidate_policy_step(state, sample(95, 1700), avg, ready)
    assert ready is True
    assert s1.mode == "1P"
    assert s1.requested_a >= 6


def test_candidate_1p_to_3p_uses_rolling_and_300s_dwell():
    state = m.State(mode="1P", mode_since=ts(0), requested_a=16)
    rolling = m.Rolling()

    # A high instantaneous point before dwell expiry must not switch phase.
    avg, ready, _ = rolling.add(ts(100), 5000)
    rolling.add(ts(195), 5000)
    avg, ready, _ = rolling.add(ts(200), 5000)
    s0 = m.candidate_policy_step(state, sample(200, 5000), avg, ready)
    assert s0.mode == "1P"

    # Once 300 s dwell is satisfied and the rolling signal remains high, switch.
    rolling.add(ts(300), 5000)
    avg, ready, _ = rolling.add(ts(305), 5000)
    s1 = m.candidate_policy_step(state, sample(305, 5000), avg, ready)
    assert ready is True
    assert s1.mode == "3P"


def test_current_policy_can_switch_1p_to_3p_on_instantaneous_spike():
    state = m.State(mode="1P", mode_since=ts(-1000), requested_a=10)
    s = m.current_policy_step(state, sample(0, 4500), rolling_w=3000)
    assert s.mode == "3P"
    assert s.mode_reason == "1P_TO_3P_INSTANT"


def test_candidate_current_downscale_is_phase_aware_in_1p():
    state = m.State(mode="1P", mode_since=ts(-1000), requested_a=12)
    # 12 A target = 2760 W. Available 2000 W => 760 W synthetic import.
    # Above 250 W deadband by 510 W => ceil(510/230)=3 A reduction.
    s = m.candidate_policy_step(state, sample(0, 2000), rolling_w=2000, rolling_ready=False)
    assert s.mode == "1P"
    assert s.requested_a == 9
    assert s.current_reason == "FAST_IMPORT_DOWN"


def test_candidate_current_downscale_is_phase_aware_in_3p():
    state = m.State(mode="3P", mode_since=ts(-1000), requested_a=10)
    # 10 A target = 6900 W. Available 5000 W => 1900 W synthetic import.
    # Above 250 W deadband by 1650 W => ceil(1650/690)=3 A reduction.
    s = m.candidate_policy_step(state, sample(0, 5000), rolling_w=5000, rolling_ready=False)
    assert s.mode == "3P"
    assert s.requested_a == 7
    assert s.current_reason == "FAST_IMPORT_DOWN"


def test_current_only_change_keeps_phase_unchanged():
    state = m.State(mode="1P", mode_since=ts(-1000), requested_a=6)
    s = m.candidate_policy_step(state, sample(0, 2500), rolling_w=2500, rolling_ready=False)
    assert s.mode == "1P"
    # No mode transition is needed for a current-regulation opportunity.
    assert s.mode_reason == "HOLD"

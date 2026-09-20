import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parents[2] / "src/pi/ems-runtime/ev/deadline/build_deadline_shadow_state.py"
spec = importlib.util.spec_from_file_location("deadline_shadow", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

NOW = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
CMD = {
    "requestId": "req-1", "requestedAt": "2026-09-19T20:53:16Z",
    "active": True, "deadline": "2026-09-20T07:00",
    "currentSoc": 66, "targetSoc": 90,
    "calibrationKWhPerPercent": 0.55, "goalKWh": 13.2, "maxA": 8,
}


def test_waits_without_meter_and_does_not_capture_baseline():
    out = m.build(CMD, {"tesla": {}}, {}, NOW)
    assert out["status"] == "WAITING_FOR_METER_TELEMETRY"
    assert out["baselineMeterKWh"] is None


def test_new_request_captures_meter_once():
    out = m.build(CMD, {"tesla": {"meter_kwh": 100.0}}, {}, NOW)
    assert out["status"] == "TRACKING"
    assert out["baselineMeterKWh"] == 100.0
    assert out["remainingKWh"] == 13.2


def test_same_request_keeps_immutable_baseline_and_tracks_progress():
    previous = m.build(CMD, {"tesla": {"meter_kwh": 100.0}}, {}, NOW)
    out = m.build(CMD, {"tesla": {"meter_kwh": 102.5}}, previous, NOW)
    assert out["baselineMeterKWh"] == 100.0
    assert out["deliveredKWh"] == 2.5
    assert out["remainingKWh"] == 10.7


def test_new_request_gets_new_baseline():
    previous = m.build(CMD, {"tesla": {"meter_kwh": 100.0}}, {}, NOW)
    cmd2 = dict(CMD, requestId="req-2")
    out = m.build(cmd2, {"tesla": {"meter_kwh": 104.0}}, previous, NOW)
    assert out["baselineMeterKWh"] == 104.0
    assert out["remainingKWh"] == 13.2


def test_meter_reset_fails_closed_without_rebaselining():
    previous = m.build(CMD, {"tesla": {"meter_kwh": 100.0}}, {}, NOW)
    out = m.build(CMD, {"tesla": {"meter_kwh": 99.0}}, previous, NOW)
    assert out["status"] == "METER_RESET_SUSPECTED"
    assert out["baselineMeterKWh"] == 100.0


def test_inactive_command_never_captures_baseline():
    cmd = dict(CMD, active=False)
    out = m.build(cmd, {"tesla": {"meter_kwh": 100.0}}, {}, NOW)
    assert out["status"] == "INACTIVE"
    assert out["baselineMeterKWh"] is None


def test_missing_meter_after_baseline_retains_previous_progress():
    previous = m.build(CMD, {"tesla": {"meter_kwh": 102.5}}, {
        "requestId": "req-1",
        "baselineMeterKWh": 100.0,
        "baselineCapturedAt": "2026-09-19T21:00:00Z",
        "deliveredKWh": 2.5,
        "remainingKWh": 10.7,
        "latestStartAt": "2026-09-20T03:00:00Z",
    }, NOW)
    out = m.build(CMD, {"tesla": {}}, previous, NOW)
    assert out["status"] == "METER_TELEMETRY_UNAVAILABLE"
    assert out["baselineMeterKWh"] == 100.0
    assert out["remainingKWh"] == 10.7

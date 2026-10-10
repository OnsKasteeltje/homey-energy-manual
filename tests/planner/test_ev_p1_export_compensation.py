#!/usr/bin/env python3
"""Standalone regressions for the read-only dynamic-planner EV/P1 correction."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE = Path("src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py")
spec = importlib.util.spec_from_file_location("ems_dynamic_planner_ev_p1", SOURCE)
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

now = datetime(2026, 10, 10, 9, 18, 7, tzinfo=timezone.utc)
state = {
    "meta": {"source_sample_at": "2026-10-10T09:18:06Z"},
    "grid": {"power_w": -388, "export_w": 388},
    "tesla": {"connected": True, "charging": True, "power_w": 2200},
    "balance": {"control_gate": {"p1_fresh": True}},
}

available, offset = planner.ev_available_pv_export(state, now)
assert (available, offset) == (2588, 2200)

importing = {**state, "grid": {"power_w": 300, "export_w": 0}}
assert planner.ev_available_pv_export(importing, now) == (1900, 2200)

idle = {**state, "tesla": {**state["tesla"], "charging": False}}
assert planner.ev_available_pv_export(idle, now) == (388, 0.0)

disconnected = {**state, "tesla": {**state["tesla"], "connected": False}}
assert planner.ev_available_pv_export(disconnected, now) == (388, 0.0)

# The five-minute Homey push from 09:15 is 187 seconds old at 09:18:07.
# This must compensate; the former 120-second guard suppressed it.
assert planner.EV_P1_COMPENSATION_MAX_STATE_AGE_SEC == 360
five_minute_push = {**state, "meta": {"source_sample_at": "2026-10-10T09:15:00Z"}}
assert planner.ev_available_pv_export(five_minute_push, now) == (2588, 2200)

at_freshness_limit = {**state, "meta": {"source_sample_at": "2026-10-10T09:12:07Z"}}
assert planner.ev_available_pv_export(at_freshness_limit, now) == (2588, 2200)

stale = {**state, "meta": {"source_sample_at": "2026-10-10T09:12:06Z"}}
assert planner.ev_available_pv_export(stale, now) == (388, 0.0)

future = {**state, "meta": {"source_sample_at": "2026-10-10T09:18:08Z"}}
assert planner.ev_available_pv_export(future, now) == (388, 0.0)

high_voltage = {**state, "tesla": {**state["tesla"], "power_w": 11650}}
assert planner.ev_available_pv_export(high_voltage, now) == (12038, 11650)

invalid = {**state, "tesla": {**state["tesla"], "power_w": 20000}}
assert planner.ev_available_pv_export(invalid, now) == (388, 0.0)

no_meta = {**state, "meta": {}}
assert planner.ev_available_pv_export(no_meta, now) == (388, 0.0)

no_p1 = {**state, "balance": {"control_gate": {"p1_fresh": False}}}
assert planner.ev_available_pv_export(no_p1, now) == (388, 0.0)

history = {"recentP1ExportSamples": [
    {"ts": "2026-10-10T08:48:06Z", "exportW": 388, "availableForEvW": 2588},
    {"ts": "2026-10-10T09:03:06Z", "exportW": 1844},
]}
updated = planner.update_recent_export_history(history, now, 382, 3805)
assert [s["exportW"] for s in updated] == [388, 1844, 382]
assert [s["availableForEvW"] for s in updated] == [2588, 1844, 3805]
baseline, trend = planner.recent_export_baseline(updated, 3805)
assert baseline == 2588 + 0.25 * (3805 - 2588)
assert trend == 3805 - 2588

# Demonstrate why the realtime correction may cross the 1P start band.
near_slot = now + timedelta(minutes=15)
corrected, _ = planner.realtime_corrected_export(
    1081, 0.6, 0.7, near_slot, now, 3805, updated
)
raw_only = [{"ts": sample["ts"], "exportW": sample["exportW"]} for sample in updated]
uncorrected, _ = planner.realtime_corrected_export(
    1081, 0.6, 0.7, near_slot, now, 382, raw_only
)
assert corrected >= planner.EV_START_1P_W, corrected
assert uncorrected < planner.EV_START_1P_W, uncorrected

print("PASS: EV-corrected P1 headroom; raw P1 preserved; fail-closed fallback")

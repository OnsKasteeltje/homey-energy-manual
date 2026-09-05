# Planner v0.5.1 EV deadline allocation — validation

Status: **PREPARED / NOT DEPLOYED**

Validated outside Homey on 2026-09-05.

Test source: `tests/planner-v0.5.1-ev-deadline-allocation.test.mjs`.

Local Node execution result:

```text
PASS planner-v0.5.1 EV deadline allocation
```

Covered cases:

1. Live reproduction: 10:45 deadline, 3.3 kWh remaining, 9 A, latest start about 10:13, planner run after latest start. Expected 6210 W, three theoretical slots required, only 10:15 + 10:30 available before deadline, residual ~0.195 kWh explicitly reported.
2. Pre-latest-start optimization: exact required slot count is selected from the existing ranking, rather than reserving a fixed 12 slots.
3. Current clamp: out-of-range max current is clamped to 16 A.
4. Zero obligation: zero remaining kWh creates no Tesla deadline slots.

Deployment gate remains closed. Before promotion to Homey runtime, apply the prepared Core pass-through and Planner allocation changes together, then verify one fresh Planner snapshot for `inputs.tesla.maxA`, `requiredDeadlineSlots`, positive `actions[].targets.evTargetW`, and `deadlineCatchUp` behavior.

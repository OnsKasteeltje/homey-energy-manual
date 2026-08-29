# Pi EMS Replay Test v0.1

Status: PRE-HARDWARE / SHADOW PREPARATION

## Purpose

Provide deterministic, offline replay tests for Pi EMS logic without reading or writing Homey. This allows Core/Publisher and later Planner/Adapter/Gate behavior to be validated while Homey is throttled or unavailable.

## Rules

- Fixtures are immutable input snapshots.
- Replay functions perform no external I/O.
- Replay functions receive an explicit clock; wall-clock time must not influence a result.
- Missing/stale safety inputs fail closed.
- Expected outputs are stored with the fixture or as explicit assertions.
- A replay PASS is necessary but not sufficient for production ownership transfer; live SHADOW comparison remains mandatory.

## Initial fixtures

### GOOD baseline
- P1 grid: +1250 W import
- PV total: 4400 W
- derived house load: 5650 W
- EV charger available
- WW off
- expected safety: positive writes may proceed to later gates

### STALE P1 baseline
- same nominal P1 value but outside the 30 s freshness window
- expected result: `GRID_POWER_STALE`
- expected safety: positive writes blocked

## Comparison ladder

```text
OFFLINE FIXTURE
      ↓
DETERMINISTIC REPLAY
      ↓
EXPECTED OUTPUT PASS
      ↓
PI SHADOW WITH RECORDED HOMEY SNAPSHOT
      ↓
HOMEY ↔ PI COMPARISON
      ↓
24/48h OBSERVATION
      ↓
OWNERSHIP TRANSFER ELIGIBLE
```

No replay result authorizes a physical write.

## Next extensions

1. Add fixtures captured from real Homey state once rate limiting has cleared.
2. Add EV semantic cases: HOLD, OPPORTUNITY, DEADLINE and unavailable charger.
3. Add WW cases: schedule, post-goal opportunity, seasonal source and stale boiler state.
4. Add Publisher payload projection and revision mismatch fixtures.
5. Store Homey/Pi deltas in `shadow_comparisons` once Pi runtime is connected.

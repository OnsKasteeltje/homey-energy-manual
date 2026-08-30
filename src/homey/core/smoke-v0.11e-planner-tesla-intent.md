# Smoke / regression plan — Core v0.11e Planner Tesla Intent

Status: **OFFLINE PREPARATION ONLY / NO HOMEY MUTATION**

Baseline under test: Core v0.11d + only the proposed Planner Tesla intent delta.

## Acceptance rule

v0.11e is acceptable only if every scenario below produces the expected Core decision semantics and no existing WW/EV safety contract regresses.

## A. Planner Tesla deadline-slot behavior

| # | Scenario | Expected priority | Expected intent | Key expectation |
|---|---|---|---|---|
| A1 | Active deadline, remaining > 0, before latestStart, active `PREFERRED_BEFORE_DEADLINE`, connected, P1 fresh, import budget >= 4140 W | SHOULD | TESLA_CHARGE_DEADLINE | Planner slot is consumed |
| A2 | Same as A1 but import budget < 4140 W | MAY | HOLD | Planner blocked by realtime import guard |
| A3 | Same as A1 but P1 stale | MAY | HOLD | Fail closed; Planner cannot bypass P1 freshness |
| A4 | Same as A1 but grid measurement invalid | MAY | HOLD | Fail closed |
| A5 | Same as A1 but Tesla not connected | SHOULD | TESLA_WAIT_NOT_CONNECTED | No charge command |
| A6 | Planner slot active but deadline inactive | existing non-deadline policy | not Planner-driven deadline charge | Planner cannot invent obligation |
| A7 | Planner slot active, deadline active, remaining = 0 | existing idle policy | not Planner-driven deadline charge | No unnecessary charge |
| A8 | Planner value unknown/unrecognized | existing policy | no planner-driven charge | Fail closed on semantic mismatch |
| A9 | Planner snapshot stale | existing policy | no planner-driven charge | Existing planner freshness rule preserved |
| A10 | Planner schema incompatible | existing policy | no planner-driven charge | Existing compatibility guard preserved |

## B. MUST precedence

| # | Scenario | Expected |
|---|---|---|
| B1 | `now >= latestStart`, active obligation, connected | MUST `TESLA_CHARGE_DEADLINE` regardless of Planner slot |
| B2 | `now >= latestStart`, active obligation, not connected | MUST `TESLA_DEADLINE_BLOCKED_NOT_CONNECTED` |
| B3 | MUST catch-up coincides with low discretionary import budget | MUST semantics preserved; downstream safety remains authoritative |
| B4 | MUST catch-up coincides with WW SHOULD slot | Tesla MUST priority semantics unchanged; no silent demotion |

## C. Existing opportunity behavior must not regress

| # | Scenario | Expected |
|---|---|---|
| C1 | Active deadline, no Planner slot, sufficient flex export | existing `TESLA_CHARGE_OPPORTUNITY` behavior unchanged |
| C2 | Active deadline, no Planner slot, negative price | existing opportunity behavior unchanged |
| C3 | Active deadline, no Planner slot, cheap context + import budget | existing opportunity behavior unchanged |
| C4 | No deadline, connected, flex export >= existing buffer threshold | existing `TESLA_BUFFER_EXPORT` behavior unchanged |
| C5 | No deadline and no export opportunity | HOLD |

## D. Downstream Power Intent invariants

For an accepted Planner deadline slot Core emits the same semantic intent as normal deadline catch-up:

```text
TESLA_CHARGE_DEADLINE
```

Verify:

1. Power Intent schema remains `EM2_POWER_INTENT_V0.2`.
2. EV target is still calculated from remaining energy over time to deadline.
3. Planner does not supply requested amps.
4. Planner does not supply executable watts.
5. EV Adapter remains sole W→A translator.
6. Adapter never rounds upward beyond upstream target except existing max-clamp semantics.
7. Gate remains required before LIVE actuator execution.

## E. Minimum executable power edge

Power Intent may mathematically yield a target below 4140 W while Planner is inside a preferred slot. The current EV Adapter deliberately maps such a target to 0 A.

This must be visible as a separate downstream condition and must **not** be 'fixed' in Core by adding requested-A logic.

Expected chain:

```text
Planner slot accepted
-> Core TESLA_CHARGE_DEADLINE
-> Power Intent numeric target
-> EV Adapter BELOW_MINIMUM_EXECUTABLE_POWER if target < 4140 W
-> 0 A
```

If this creates undesirable scheduling in practice, the later fix belongs in Planner/Power-Intent energy scheduling semantics, not by bypassing the adapter.

## F. WW regression

Run the full v0.11d thermostat-verification regression unchanged. At minimum verify:

- 19:00 hard stop unchanged;
- catch-up/MUST unchanged;
- thermostat verification max 20 min unchanged;
- re-arm only after genuine stop-request clear edge;
- no inferred goal without actual `<100 W / 10 min` evidence;
- Planner WW slot handling unchanged;
- WW actuator ownership unchanged.

## G. Load/regression budget

v0.11e PASS requires:

- zero additional Homey device reads relative to v0.11d;
- zero additional broad Logic collection scans;
- no new cron/poller;
- reuse the already-read Planner snapshot;
- no network call added to Core;
- no device write added to Core.

## H. Observability checks

For A1, evidence must make the source of the decision unambiguous:

- Planner snapshot fresh/compatible;
- active slot start/end;
- `plannerTesla=PREFERRED_BEFORE_DEADLINE`;
- deadline active;
- remaining kWh > 0;
- before latestStart;
- P1 fresh/grid valid;
- import guard PASS;
- final Core decision `SHOULD / TESLA_CHARGE_DEADLINE`;
- downstream Power Intent target;
- downstream Adapter requested A/status;
- Gate PASS/FAIL;
- actual charger state kept separate from Planner forecast.

## I. Deployment smoke — later, only after offline PASS

1. Capture live Core v0.11d complete rollback source.
2. Apply one Advanced Flow update to v0.11e only.
3. Do not start unrelated flows.
4. Do not perform broad device/flow discovery.
5. Observe one natural Core tick with an active deadline and connected Tesla.
6. If the Planner slot is active, verify the semantic chain without forcing a device write.
7. Only if existing LIVE ownership is already intentionally enabled and Gate naturally PASSes may the normal actuator act; do not bypass it.
8. On 429/throttling, stop validation immediately.

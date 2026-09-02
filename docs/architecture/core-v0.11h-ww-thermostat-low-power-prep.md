# Core v0.11h — WW thermostat verification low-power gate

**Status: PREP ONLY / NOT DEPLOYED**

## Incident evidence

On 2026-09-02 the boiler was still physically heating at roughly 1.9–2.0 kW while the P1 meter showed sustained grid import after a preceding PV-export period. The current v0.11g policy can enter `THERMOSTAT_VERIFY` after a discretionary stop is requested, even when the element is still actively heating. The verification import guard only requires import to remain below the broad 4 kW discretionary-import ceiling.

## Root cause

`THERMOSTAT_VERIFY` was designed to preserve the boiler switch in the ON state long enough to confirm a *natural thermostat stop*: after confirmed heating, measured boiler power should already have dropped below 100 W and stay low long enough for the existing WW-state logic to latch `goalReachedToday`.

In v0.11g, low measured power is not part of `thermostatVerifyBaseEligible`. As a result, the verification branch precedes and masks `PLANNER_SLOT_END`, `WAIT_PRICE`, or `WAIT_IMPORT` while the element may still be drawing ~1900 W.

Exact runtime baseline: `src/homey/core/core-v0.11g.live-homey.js` from immutable commit `bd4edecc219c035399a18671429c2cf24eaea1be`.

## Candidate v0.11h rule

The surgical change is restricted to thermostat-verification semantics:

1. Introduce `THERMOSTAT_VERIFY_LOW_W = 100`.
2. Define `thermostatVerifyLowPower = boilerOn && powerW < THERMOSTAT_VERIFY_LOW_W`.
3. Require `thermostatVerifyLowPower` before a new verification may start.
4. If an already-active verification sees power return to `>=100 W`, abort verification and issue `BOILER_OFF` rather than continuing HOLD.
5. Publish `thermostatVerifyLowPower` as a guard/evidence field.
6. Keep the existing ten-minute low-power goal-confirmation mechanism unchanged.

## Explicit non-changes

The candidate must not change the 15-minute PV run-lock, 30-minute price run-lock, catch-up MUST policy, post-goal policy, mode switch semantics, 19:00 hard stop, P1 freshness rules, planner compatibility, Tesla logic, actuator/adapters, or the `EM2_CONTROL_WW_V0.11` downstream schema.

## Offline acceptance matrix

The regression harness `src/homey/core/tests/core-v0.11h-ww-thermostat-regression.js` must pass all cases before any Homey edit. Critical cases are:

- ~1950 W boiler + 900 W import + run-lock expired + no opportunity -> `BOILER_OFF / WAIT_IMPORT`.
- Same conditions while the minimum run-lock is still active -> `HOLD / RUN_LOCK`.
- <100 W boiler after confirmed heating + discretionary stop request -> `HOLD / THERMOSTAT_VERIFY`.
- Power rises to >=100 W during verification -> `BOILER_OFF / THERMOSTAT_VERIFY_ABORT`.
- Catch-up, source-mode hard-off, and after-19:00 behavior remain unchanged.

## Deployment gate

Do not modify the current Homey Core until all of the following are true:

- exact v0.11g baseline and candidate diff have been reviewed;
- offline regression passes;
- only the intended WW thermostat-verification lines differ aside from version/diagnostic metadata;
- candidate source is pinned to an immutable Git commit;
- rollback source and current Homey flow configuration are recorded;
- explicit deployment approval is given.

When deployment is eventually approved, replace the Core code as one reviewed unit; do not live-edit individual fragments in Homey. After deployment, first observe a normal PV run and its natural run-lock without inducing a test load. A genuine low-power thermostat event should still be allowed to latch the daily goal. No actuator, adapter, or planner change is part of this patch.

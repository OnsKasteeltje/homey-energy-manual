# EV Bridge v1.5.9 adaptive 3P upscale — 2026-10-04

Status: **CANDIDATE — repository validation required before Homey cutover**

## Evidence and scope

Same-day PV/EV replay showed that the v1.5.8 planner and realtime phase selector
found the relevant PV windows, while about 6.10 kWh still exported during the
main EV/PV window. Approximately 5.49 kWh of that export occurred while the EV
was already charging (about 2.81 kWh in 1P and 2.68 kWh in 3P). This is evidence
for current-response tuning, not for relaxing phase dwell or planner opportunity
selection.

v1.5.9 changes only same-phase **3P upward current steps**. It does not change
planner allocation, phase thresholds, dwell timers, downward control, deadline
force, Adapter/Gate semantics or physical-writer ownership.

## Stable production target

- Advanced Flow ID: `8bf53fdb-76f4-47db-8ccb-773ac515f06e`
- v1.5.8 name:
  `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.8 PRODUCTION TUNED [READY]`
- v1.5.9 name:
  `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.9 ADAPTIVE UPSCALE [READY]`
- Script card ID: `44444444-eeee-4444-8444-444444444444`
- Canonical v1.5.9 source:
  `apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.9.adaptive-upscale.js`

The existing five-card Advanced Flow, stable Flow ID and every non-script card
must remain unchanged.

## Control rule

Baseline behaviour remains:

- 1P upstep: max +3 A;
- 3P upstep: max +2 A;
- physical target must be settled before any positive current step;
- fast import down-regulation is unchanged;
- predictive preference remains up to +300 W import.

A 3P step may exceed the normal +2 A bound, up to **+4 A**, only when all of the
following are true in the same decision:

1. phase mode is already 3P;
2. the 120-second rolling signal is ready (>=90 s coverage);
3. current P1 shows export;
4. instantaneous export supports the larger step, including the existing
   +300 W import preference;
5. the 2-minute rolling available-power signal supports the same larger step;
6. the normal instantaneous predictive desired current supports the step;
7. Easee physical offered current has settled to the previous requested current.

The adaptive step is therefore:

```text
min(
  4 A,
  current-export-supported step,
  rolling-supported step,
  instantaneous predictive desired step
)
```

Only when that result exceeds the normal 3P +2 A limit is the larger step used.
Otherwise v1.5.8 behaviour is retained.

The explicit reason for a larger step is
`PREDICTIVE_UP_ADAPTIVE_EXPORT`.

## Unchanged safety / ownership

- rolling window 120 s;
- minimum rolling coverage 90 s;
- OFF re-entry dwell 120 s;
- 1P→3P promotion dwell 180 s;
- OFF→1P 1500 W;
- 1P stop 1100 W;
- OFF/1P→3P 4400 W;
- 3P leave 3600 W;
- 6–16 A envelope;
- +3 A 1P baseline step;
- +2 A 3P baseline step;
- +300 W predictive import preference / down-limit;
- phase-entry viability margin 250 W;
- deadline hard force remains last and forced 3P;
- Adapter/Gate/Writer unchanged;
- writer v0.4.5 remains the sole physical Easee writer.

## Diagnostics

Controller version becomes `EM2_EV_PHASE_CURRENT_CONTROLLER_V0.4` and exposes:

- `predictiveDesiredA`;
- `rollingDesiredA`;
- `currentExportW`;
- `adaptive3pCandidateStepA`;
- `appliedUpscaleStepA`;
- `maxAdaptiveUpscaleStep3pA=4`.

These fields exist so replay can distinguish a normal +2 A increase from an
export-backed adaptive increase.

## Deployment transaction

Follow the existing v1.5.8 targeted transaction:

1. targeted read of stable Flow ID;
2. retain complete writable v1.5.8 body for rollback;
3. prepare exact v1.5.9 body outside Homey;
4. update only `name`, `enabled`, `cards`;
5. one targeted readback;
6. verify stable ID, enabled=true, broken=false, five cards, unchanged non-script
   cards and exact script bytes;
7. rollback exact v1.5.8 body on any mismatch;
8. never trigger the physical actuator as deployment validation.

A Homey 429 is a hard stop; no immediate retry.

## Acceptance

Before cutover:

- repository structure gate PASS;
- EMS Architecture Gate PASS;
- v1.5.9 regression PASS;
- existing EV bridge/writer regressions PASS;
- security scan PASS.

After the normal minute trigger, verify:

- `policyRevision=PI_DYNAMIC_PLANNER_BRIDGE_V1.5.9_ADAPTIVE_UPSCALE`;
- `controllerVersion=EM2_EV_PHASE_CURRENT_CONTROLLER_V0.4`;
- existing dwell values unchanged;
- `maxUpscaleStep3pA=2`;
- `maxAdaptiveUpscaleStep3pA=4`;
- Adapter/Gate PASS on valid control;
- no new writer exists.

## Rollback

Rollback is the exact pre-deploy v1.5.8 writable body captured from stable
Advanced Flow `8bf53fdb-76f4-47db-8ccb-773ac515f06e`. No Pi planner,
Adapter, Gate or actuator rollback is required.

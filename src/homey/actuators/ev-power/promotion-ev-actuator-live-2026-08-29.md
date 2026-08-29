# EV Power Actuator — production LIVE promotion

Date: 2026-08-29

## Result

**PASS** — `EM2_EV_Actuator_Live_Enabled` was promoted to `true` after a guarded production-readiness check.

## Preconditions verified

- Fresh Core/Power Intent revision: `3118`
- `EV_target_W = 2176 W`
- EV status: `NUMERIC_PV_EXPORT_TARGET`
- `requested_A = 0 A` because the target is below the 3×6 A minimum executable charging threshold
- EV Adapter Gate: `PASS`
- Intent/adapter/state/gate/core revisions all equal `3118`
- `coherent = true`
- Adapter remained SHADOW/read-only (`deviceWrites=false`, `physicalWrite=false`) and fail-closed
- Requested current domain valid (`0` or integer `6..16 A`)

## Promotion action

A temporary one-shot guarded promotion flow set `EM2_EV_Actuator_Live_Enabled=true` only after re-validating freshness, revision coherence, Gate PASS, adapter safety and requested-current validity. The temporary promotion flow was disabled immediately afterwards.

## Verification

`docs/data/ev-control-status.json` published at `2026-08-29T07:42:16.255Z` confirmed:

- revision `3118`
- Gate `PASS`
- `coherent=true`
- actuator `live=true`
- `physicalWritePerformed=false`

No physical Easee write was caused by the promotion itself. The next natural valid Gate revision is allowed to invoke the production actuator. The actuator continues to fail closed on stale, incoherent or invalid input.

## Prior physical evidence

STOP ownership had already passed before this promotion: a coherent `0 W -> 0 A -> PASS` chain physically set Easee dynamic charger current to `0 A`, and charging stopped. See `smoke-ev-actuator-stop-ownership-2026-08-29.md`.

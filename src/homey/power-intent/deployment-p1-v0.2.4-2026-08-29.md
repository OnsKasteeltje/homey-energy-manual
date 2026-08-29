# Power Intent P1 v0.2.4 — dual-semantic deployment

Date: 2026-08-29

Status: **DEPLOYED / NATURAL EV TRANSITION VALIDATION OPEN**

## Runtime

Homey Advanced Flow: `19d9d8a6-ec32-4639-be5e-71e9f034d31b`

Runtime name: `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD`

Readback after deployment:

- `enabled=true`
- `broken=false`
- trigger 1: `EM2_Control_WW changed`
- trigger 2: `EM2_Control_EV changed`
- `EM2_Control_EV` Logic ID: `67451f33-20e6-46b0-9528-9c04bf6425dc`
- five exact `Homey.logic.getVariable({id})` reads per invocation
- zero `getVariables()` collection scans
- zero device reads
- zero network calls
- zero direct device writes
- no `EM2_Public_State` dependency

## Runtime coherency refinement

The implementation-ready design originally proposed strict equality between the current Decision revision and `Control_EV.coreRevision`.

Runtime Core v0.10.18 intentionally writes `EM2_Control_EV` only when EV semantics materially change. Therefore `Control_EV.coreRevision` may legitimately lag the current State/Decision revision while its semantic snapshot remains current. Strict revision equality would incorrectly fail closed on valid WW-only updates.

The deployed v0.2.4 contract therefore uses:

1. strict revision alignment for `EM2_State`, `EM2_Decision`, and `EM2_Control_WW`;
2. schema validation of `EM2_Control_EV_V0.1`;
3. semantic validation that `Control_EV.mode` matches the current authoritative Decision intent;
4. `Control_EV.semanticRevision` as part of the combined idempotency key.

This preserves semantic suppression and avoids turning `EM2_Control_EV` into a per-Core-tick heartbeat.

## Downstream compatibility

The output schema remains `EM2_POWER_INTENT_V0.2` and `policyRevision` remains `P1_V0.2.2_PUBLIC_DECOUPLED` so the existing EV/WW Adapter → Gate → Actuator contracts are unchanged. `engineVersion=P1_V0.2.4_DUAL_SEMANTIC` records the new trigger engine.

Power Intent itself remains read-only / `deviceWrites=false`. No EV actuator code was modified in this deployment.

## Remaining acceptance gate

The deployment is structurally complete. Final promotion status becomes PASS after a natural Tesla-only semantic transition demonstrates that an EV change with unchanged WW wakes Power Intent exactly once, followed by a reverse transition. Any Homey 429 during that validation fails the promotion and triggers rollback to v0.2.3.

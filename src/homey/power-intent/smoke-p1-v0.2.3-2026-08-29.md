# Power Intent P1 v0.2.3 TARGETED-READ LOW-LOAD smoke — 2026-08-29

Result: **PASS (deployment/start smoke)**

## Scope

Flow: `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD`  
Flow ID: `19d9d8a6-ec32-4639-be5e-71e9f034d31b`

This smoke intentionally validates only the low-load runtime replacement and safe start path. It does not perform any actuator write.

## Observed evidence

- Homey accepted the Advanced Flow update.
- Flow returned `enabled=true` and `broken=false` after update.
- Existing trigger remains `EM2_Control_WW changed`.
- Runtime now uses four targeted `Homey.logic.getVariable({id})` reads for `EM2_State`, `EM2_Decision`, `EM2_Control_WW` and `EM2_Power_Intent`.
- No `Homey.logic.getVariables()` collection scan remains in the Power Intent script.
- Output schema remains `EM2_POWER_INTENT_V0.2` and policyRevision remains `P1_V0.2.2_PUBLIC_DECOUPLED` deliberately, so deployment itself does not force a version-only downstream variable change.
- `readOnly=true`, `controlMode='SHADOW'`, `deviceWrites=false` remain unchanged.
- Manual Advanced Flow smoke start returned `Successfully started the Flow.`
- No `Too many requests` response occurred during deployment or the single smoke start.
- No Watchdog enabling, device reads, device writes, actuator writes or broad/repeated runtime polling were performed as part of this smoke.

## Interpretation

The low-load deployment/start gate passes. The Power Intent route now removes one broad Logic collection enumeration per trigger and replaces it with four stable targeted reads while preserving the v0.2.2 control/output contract.

A future natural sourceRevision change can provide the separate end-to-end evidence that a genuine semantic intent change still propagates once through the downstream Gate/Adapter chain. That is not required for this deployment/start smoke and must not be artificially forced while the throttling baseline is under investigation.

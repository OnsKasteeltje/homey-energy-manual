# EV Power Adapter v0.1.1 TARGETED-READ LOW-LOAD — prepared

Status: PREPARED / NOT DEPLOYED / ID-BINDING PENDING

Homey flow ID: `953e9b18-3576-4557-b940-ed4a64eb2516`
Runtime verified: 2026-08-29
Runtime state: `enabled=false`, `broken=false`, `triggerable=true`
Trigger: `EM2_Power_Intent` changed + manual Start

## Finding

The current v0.1 SHADOW runtime performs one full `Homey.logic.getVariables()` collection enumeration per execution. Because the flow is currently disabled, it contributes zero current runtime load and must remain disabled during the throttling baseline.

## Low-load redesign

Replace the full collection enumeration with four targeted `Homey.logic.getVariable({id})` reads:

1. `EM2_Power_Intent` — known stable ID `04b57041-dd7f-41f7-a00a-f023afb1ccee`
2. `EM2_State` — known stable ID `8e1efbb0-7999-494c-9429-7d274afacd79`
3. `EV Max laadstroom A` — stable ID still to bind before deployment
4. `EM2_EV_Power_Adapter` — stable ID still to bind before deployment

The adapter output variable already exists in the captured runtime contract; v0.1.1 must not introduce create-on-missing behavior in normal operation. Missing targeted variables must fail closed and return false without device/network access.

## Invariants that must not change

- Input remains `EM2_Power_Intent.targets.ev.target_W` only.
- Fixed electrical model remains 3 × 230 V.
- `MIN_A=6`, configured maximum remains capped at 16 A.
- Floor quantization remains authoritative; adapter must never increase upstream requested power.
- Freshness window remains 120 s.
- Revision/schema alignment remains mandatory.
- SHADOW only: `readOnly=true`, `controlMode='SHADOW'`, `deviceWrites=false`.
- No device reads, device writes, Insights calls, network calls or poller.
- Existing output schema remains `EM2_EV_POWER_ADAPTER_V0.1` to avoid deployment-only downstream fan-out.
- Idempotency remains based on source revision, input schema, target W, max A and mapping revision.

## Expected load effect when eventually enabled

Before: 1 full Logic collection enumeration per `EM2_Power_Intent` event.
After: 4 targeted Logic reads per event, with no collection scan.

This has no effect on the current throttling baseline while the flow remains disabled.

## Deployment gate

Do not deploy or enable until:

- stable IDs for `EV Max laadstroom A` and `EM2_EV_Power_Adapter` are explicitly bound;
- a future control-path test requires the adapter to be re-enabled;
- Homey is not rate-limited;
- exactly one SHADOW smoke is planned;
- no safety criteria are relaxed.

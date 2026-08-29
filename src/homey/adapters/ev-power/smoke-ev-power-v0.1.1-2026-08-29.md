# EV Power Adapter v0.1.1 TARGETED-READ SHADOW — runtime smoke

Date: 2026-08-29
Flow ID: `953e9b18-3576-4557-b940-ed4a64eb2516`

## Change
- Re-enabled the flow.
- Replaced full `Homey.logic.getVariables()` enumeration with four targeted reads:
  - `EM2_Power_Intent` — `04b57041-dd7f-41f7-a00a-f023afb1ccee`
  - `EM2_State` — `8e1efbb0-7999-494c-9429-7d274afacd79`
  - `EV Max laadstroom A` — `4a7398bb-9253-49ab-8850-820d1a622bd6`
  - `EM2_EV_Power_Adapter` — `f2118322-d59d-4aa8-b478-234effc3983c`
- Preserved SHADOW safety and deterministic 3x230 V floor W-to-A mapping.
- `deviceWrites=false`; no device/network access.

## Runtime result
- Deployment: PASS (`enabled=true`, `broken=false`).
- One manual Advanced Flow smoke: PASS (`Successfully started the Flow.`).
- No Homey throttling response observed.
- No physical charger write was possible/performed.

## Promotion decision
PASS — keep enabled and continue to EV Power Adapter Gate.

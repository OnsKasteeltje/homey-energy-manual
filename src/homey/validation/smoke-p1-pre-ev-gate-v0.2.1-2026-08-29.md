# P1 Pre-EV Gate v0.2.1 TARGETED-READ — runtime smoke

Date: 2026-08-29
Flow ID: `557ed7e8-9efe-4173-bc06-8e629214e172`

## Change
- Re-enabled the flow.
- Replaced full `Homey.logic.getVariables()` enumeration with two targeted `getVariable(id)` reads:
  - `EM2_Power_Intent` — `04b57041-dd7f-41f7-a00a-f023afb1ccee`
  - `EM2_P1_PreEV_Gate` — `54c7537c-54ac-4534-af7f-39b972ca6067`
- Removed obsolete `inputRevisions.publicState` coherence requirement.
- Coherence now follows Power Intent v0.2.3 inputs: `state`, `decision`, `wwControl`.
- Safety remains Logic-only; no device/network access.

## Runtime result
- Deployment: PASS (`enabled=true`, `broken=false`).
- One manual Advanced Flow smoke: PASS (`Successfully started the Flow.`).
- No Homey throttling response observed during the smoke.
- No device or actuator write was performed.

## Promotion decision
PASS — keep enabled and continue to EV Power Adapter only after recording this result.

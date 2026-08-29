# EV Power Actuator v0.2.2 TARGETED-READ LIVE OWNERSHIP — runtime smoke

Date: 2026-08-29
Flow ID: `fea23193-a03f-49dd-9780-7e72ee48747d`

## Change
- Re-enabled the flow.
- Replaced full `Homey.logic.getVariables()` enumeration with six targeted reads: LIVE flag, status, Power Intent, EV Power Adapter, EV Adapter Gate, and EM2 State.
- Natural execution remains Gate-driven.
- Added permanent safe manual-start path: manual Start first sets `EM2_EV_Actuator_Live_Enabled=false`, then executes actuator logic.
- LIVE=false performs zero charger reads/writes.
- LIVE=true requirements remain unchanged: fresh schemas, exact intent/adapter/state/core/Gate revision coherence, adapter contract valid, Gate PASS, numeric safe requested current.

## Runtime result
- Deployment: PASS (`enabled=true`, `broken=false`).
- One manual Advanced Flow smoke: PASS (`Successfully started the Flow.`).
- Manual smoke normalized LIVE=false before actuator execution.
- Therefore the smoke used the SHADOW/no-write ownership path; no Easee read/write was permitted.
- No Homey throttling response observed.

## EV four-flow restoration status
1. P1 Pre-EV Gate v0.2.1 TARGETED-READ — enabled, smoke PASS.
2. EV Power Adapter v0.1.1 TARGETED-READ SHADOW — enabled, smoke PASS.
3. EV Power Adapter Gate v0.2.1 TARGETED-READ — enabled, smoke PASS.
4. EV Power Actuator v0.2.2 TARGETED-READ LIVE OWNERSHIP — enabled, smoke PASS.

## Promotion decision
PASS for safe SHADOW operation. Do not arm LIVE for a positive physical write until a fresh natural positive Power Intent produces expected requested_A and current Gate PASS with exact revision coherence.

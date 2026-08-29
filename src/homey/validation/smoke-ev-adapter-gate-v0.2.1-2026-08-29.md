# EV Power Adapter Gate v0.2.1 TARGETED-READ — runtime smoke

Date: 2026-08-29
Flow ID: `ec5e5d34-8205-4cf0-a661-7bf744feb6e0`

## Change
- Re-enabled the flow.
- Replaced full `Homey.logic.getVariables()` enumeration with four targeted reads: Power Intent, EV Power Adapter, EM2 State, and EV Adapter Gate.
- Preserved the 2-second settle delay and all schema/revision/safety/electrical/translation checks.
- Logic-only; no device/network access.

## Runtime result
- Deployment: PASS (`enabled=true`, `broken=false`).
- One manual Advanced Flow smoke: PASS (`Successfully started the Flow.`).
- No Homey throttling response observed.
- No device or actuator write performed.

## Promotion decision
PASS — keep enabled and proceed to EV actuator only after explicitly normalizing LIVE=false.

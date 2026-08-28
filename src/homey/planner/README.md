# Homey EMS 24h Planner runtime source

This directory is the versioned source baseline for the Homey Advanced Flow **EM v2 | 45 Planner | 24h Energy Plan v0.4.3 SHADOW**.

- Homey Advanced Flow ID: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`
- Current captured runtime: `energy-plan-24h-v0.4.3.js`
- Homey runtime status at capture: `enabled=false`, `broken=false`, `triggerable=true`
- Schedule in Homey: every 15 minutes with a 45-second stagger; manual start path is also present.
- Safety: SHADOW/read-only; no Victron, Easee, boiler, or other physical device writes.

## Inputs and outputs

The planner reads the current EMS state, warm-water state, contract/price context, day history and PBTH price buffer. It also retrieves a 15-minute shortwave-radiation forecast for Hauwert from Open-Meteo.

It writes only Homey Logic state:

- `EM2_Energy_Plan_24h`
- `EM2_Energy_Planner_Status`

## Migration and change rule

GitHub is the source-of-truth for planner code. Never reconstruct or simplify the HomeyScript while deploying a change: start from the latest captured baseline, make the smallest reviewable diff, preserve SHADOW safety, and smoke-test the relevant chain before migrating the next flow.

**Migration gate:** one flow migration = one change-set = one chain smoke test = PASS before the next migration.

# Homey EMS 24h Planner runtime source

This directory is the versioned source baseline for the Homey Advanced Flow **EM v2 | 45 Planner | 24h Energy Plan**.

- Homey Advanced Flow ID: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`
- Last captured runtime baseline: `energy-plan-24h-v0.4.4.js`
- Next source candidate: `energy-plan-24h-v0.4.5.js`
- Schedule in Homey: every 15 minutes with a 45-second stagger; manual start path is also present.
- Safety: SHADOW/read-only; no Victron, Easee, boiler, or other physical device writes.

## v0.4.5 base-load hardening

v0.4.5 prevents sparse history from turning a high unexplained global median into a fictitious all-night base-load forecast.

- Tesla and boiler power remain subtracted from house power before base learning.
- Samples marked washer-active or dryer-active are excluded from base learning.
- Residual base samples at or above the existing `HIGH_LOAD_UNIDENTIFIED` threshold of 1500 W are excluded from base learning.
- A quarter-bin forecast requires at least two clean samples for that local quarter.
- A global clean fallback requires at least three clean samples and must remain below 1500 W.
- If neither condition is met, `baseLoadForecastW` stays `null` and quality becomes `INSUFFICIENT_CLEAN_BASE_HISTORY`; the planner does not invent a high fallback.
- This remains SHADOW-only and cannot perform physical writes.

## Inputs and outputs

The planner reads the current EMS state, warm-water state, contract/price context, day history and PBTH price buffer. It also retrieves a 15-minute shortwave-radiation forecast for Hauwert from Open-Meteo.

It writes only Homey Logic state:

- `EM2_Energy_Plan_24h`
- `EM2_Energy_Planner_Status`

## Migration and change rule

GitHub is the source-of-truth for planner code. Never reconstruct or simplify the HomeyScript while deploying a change: start from the latest captured baseline, make the smallest reviewable diff, preserve SHADOW safety, and smoke-test the relevant chain before migrating the next flow.

**Migration gate:** one flow migration = one change-set = one chain smoke test = PASS before the next migration.

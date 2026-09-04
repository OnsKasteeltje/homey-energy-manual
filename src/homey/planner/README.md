# Homey EMS 24h Planner runtime source

This directory is the versioned source baseline for the Homey Advanced Flow **EM v2 | 45 Planner | 24h Energy Plan**.

- Homey Advanced Flow ID: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`
- **Current verified live Homey runtime (2026-09-04): `EM v2 | 45 Planner | 24h Energy Plan v0.5.0 SHADOW LOW-LOAD`**
- **Exact live source baseline: `energy-plan-24h-v0.5.0.live-homey.js`**
- Schedule in Homey: every 15 minutes with a 45-second stagger; manual start path is also present.
- Safety: SHADOW/read-only; no Victron, Easee, boiler, or other physical device writes.

## Current live v0.5.0

Direct Homey inspection on 2026-09-04 verified the complete Advanced Flow and executable HomeyScript. The exact script is captured as `src/homey/planner/energy-plan-24h-v0.5.0.live-homey.js` and supersedes older planner candidates/baselines for current-state work.

v0.5.0 retains the hardened base-load and Tesla PV-opportunity logic and adds the current warm-water scheduling model:

- 96 × 15-minute shadow horizon.
- Uses Hauwert Open-Meteo `shortwave_radiation` at 15-minute resolution; historical PV/irradiance ratios calibrate the forecast when enough points exist.
- Known Tesla and boiler load are removed before base learning; washer/dryer-active and residual base samples >=1500 W are rejected.
- Tesla PV opportunity start requires 4830 W forecast surplus; continuation requires 4140 W; minimum run is two slots / 30 minutes.
- WW is planned as an energy budget rather than a single contiguous window.
- WW allocation ranks full PV surplus first, then lowest marginal import; DYNAMIC price is a secondary ordering factor when usable.
- Current-day grid energy can be deferred by the receding horizon until deadline slack falls to the two-slot / 30-minute safety margin before 19:00.
- Tesla deadline slots have priority over non-MUST WW slots; conflicting WW SHOULD slots are relocated before the deadline where possible.
- Each local Europe/Amsterdam day in the horizon has its own WW deadline and daily planning state.
- Battery scheduling remains theoretical only (`simulationOnly`); no Victron writes exist.

## Inputs and outputs

The planner performs one targeted read of the canonical Planner input Logic variable. That input contains current EMS state, warm-water state, contract/price context, day history and the PBTH price buffer. The planner additionally retrieves the Hauwert weather forecast from Open-Meteo.

It writes only the canonical planner snapshot Logic state consumed by downstream publication/core logic. It performs no physical device writes.

## Source parity

**PASS — 2026-09-04.** `src/homey/planner/energy-plan-24h-v0.5.0.live-homey.js` was captured from the executable HomeyScript action of live flow `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`.

The authoritative current reconciliation record is:

`docs/architecture/homey-runtime-baseline-2026-09-04.md`

Older `energy-plan-24h-v0.4.x.js`, candidate Markdown and smoke material remain historical/development evidence and are not the current live source.

## Migration and change rule

Never reconstruct or simplify the HomeyScript while deploying a planner change. Start from the exact latest captured live baseline, make the smallest reviewable diff, preserve SHADOW safety, and smoke-test the relevant chain before migrating the next flow.

**Migration gate:** one flow migration = one change-set = one chain smoke test = PASS before the next migration.

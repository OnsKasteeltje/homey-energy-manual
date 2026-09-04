# Homey runtime baseline — 2026-09-04

Status: **authoritative runtime reconciliation baseline for the current Homey EMS runtime — reconciled directly against live Homey on 2026-09-04**.

This baseline supersedes `homey-runtime-baseline-2026-08-30.md` for all current-state documentation and Pi migration work. The 2026-08-30 baseline remains historical audit evidence.

## Authority and reconciliation rule

1. Live Homey flow identity, enabled/broken state and embedded HomeyScript are the runtime truth.
2. Exact HomeyScript captured from live Homey is stored in `*.live-homey.js` files where listed below.
3. Historical candidate, patch, smoke, rollback, TEMP and old baseline material must not be interpreted as current production ownership.
4. No Homey flow was changed as part of this reconciliation; GitHub was brought forward to the observed Homey runtime.

## Current core and orchestration

| Classification | Homey flow | Flow ID | Current source / role |
|---|---|---|---|
| LIVE | `EM v2 | 00 Core Tick | v0.11i PINNED SOURCE` | `227f8d3b-7551-46dd-837d-1b8c69add824` | enabled, not broken; 5-minute Core; exact embedded source captured as `src/homey/core/core-v0.11i.live-homey.js`; `PUB_VERSION=EM2_CORE_STATE_V0.11i`; schema 2.12; Core performs no physical device writes |
| ACTIVE SHADOW | `EM v2 | 12 Input | Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER` | `758f3353-51f5-4e68-a1f4-3acf30ec5a87` | active input aggregation/parity layer |
| ACTIVE SHADOW | `EM v2 | 45 Planner | 24h Energy Plan v0.5.0 SHADOW LOW-LOAD` | `27617767-0a64-43a3-9bcb-e34b0dd6a5c0` | enabled, not broken; 15-minute planner; exact embedded source captured as `src/homey/planner/energy-plan-24h-v0.5.0.live-homey.js`; no physical writes |
| LIVE publication | `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD` | `5b3b80fe-96d1-406d-91ef-cf75a4e65d45` | current Planner Shadow publication component |
| LIVE publication | `EM v2 | 40 Data | Publisher v1.0.13 CONTROL EVIDENCE LOW-LOAD` | `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd` | enabled, not broken; exact embedded source captured as `src/homey/publication/publisher-v1.0.13.live-homey.js`; 15-minute/+8 s publication cadence with control evidence |
| LIVE watchdog | `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | `8526109f-5c8d-428e-ac24-85a71c95ac36` | current freshness watchdog |
| LIVE config | `EM v2 | 05 Config | EMS Settings Sync v0.4.1 TARGETED 15-MIN LOW-LOAD` | `9193b3ae-1e3d-4b52-aa95-60aff099e68a` | enabled, not broken; exact embedded source captured as `src/homey/config/ems-settings-sync-v0.4.1.live-homey.js`; targeted Logic reads; canonical raw GitHub command first, API fallback |
| LIVE context | `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD` | `69648157-892b-49d2-bc4d-e61a1a4d78ab` | current FIXED/DYNAMIC price-context bridge |

## Current EV path

| Classification | Homey flow | Flow ID | Current source / role |
|---|---|---|---|
| LIVE | `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD` | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | current P1-authoritative Power Intent producer |
| LIVE | `EM v2 | 60 Actuator | EV Power v0.2.3 MIN7 TARGETED-READ LIVE OWNERSHIP` | `fea23193-a03f-49dd-9780-7e72ee48747d` | enabled, not broken; exact embedded source captured as `src/homey/actuators/ev-power-v0.2.3.live-homey.js`; gate-driven physical writer; accepts 0 A or 7–16 A |
| ACTIVE SHADOW | `EM v2 | 60 Adapter | EV Power v0.1.2 MIN7 TARGETED-READ SHADOW` | `953e9b18-3576-4557-b940-ed4a64eb2516` | enabled, not broken; exact embedded source captured as `src/homey/adapters/ev-power-v0.1.2.live-homey.js`; fixed 3×230 V, floor mapping, fail-closed, no device writes |
| VALIDATION | `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.2 MIN7 TARGETED-READ` | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | enabled, not broken; exact embedded source captured as `src/homey/validation/ev-power-adapter-gate-v0.2.2.live-homey.js`; requires MIN7 mapping and revision alignment |
| VALIDATION | `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ` | `557ed7e8-9efe-4173-bc06-8e629214e172` | current validation gate |
| OBSERVABILITY | `EM v2 | 81 Observability | EV Control Status v0.1` | `f6edba38-ddf1-45e5-890e-c183aa2055d5` | EV control observability |
| REPLACED / LEGACY | `Tesla laden v2.7.15 + RC run lease [DISABLED - REPLACED BY EV POWER ARCH]` | `e82dd325-8a09-4b43-a0b4-1be277ab5d91` | never document as current EV control owner |

## Current warm-water path

| Classification | Homey flow | Flow ID | Role |
|---|---|---|---|
| LIVE | `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE` | `40d45aeb-174e-4a83-9a42-71ae46065cb4` | current boiler physical-write owner |
| ACTIVE SHADOW | `EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW` | `472d0355-3bb9-4a42-be43-114b57822136` | current WW adapter shadow layer |
| ACTIVE SHADOW | `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` | `5538f1c9-9a21-4328-9896-942952f5c55f` | post-goal opportunity logic |
| ACTIVE SHADOW | `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` | `543664be-d07a-4099-92d1-07878b73215d` | manual-only seasonal source advice; no source-switch write |
| OBSERVER | `EM v2 | 15 State | Warm Water Observer v0.2` | `957a85b5-a4ff-4fe2-bc6b-2e56e60387ea` | WW state observation |
| LEGACY CANDIDATE | `EM v2 | 60 Control | Warm Water Actuator v0.6` | `2b9284f6-1d41-453e-a8f9-10c634f56fe5` | older actuator; not current ownership |

## Core v0.11i runtime facts

Current documentation and Pi migration must preserve these observed runtime facts:

- Core cadence remains five minutes.
- Core performs no physical device writes.
- Core currently reads ten named devices and still performs one broad `Homey.logic.getVariables()` enumeration per run.
- P1 remains authoritative for flex/export budget and fails closed when P1 is stale.
- Planner compatibility includes both `EM2_ENERGY_PLAN_24H_V0.4.9` and `EM2_ENERGY_PLAN_24H_V0.5.0` with a stricter v0.5 slot contract.
- Planner Tesla admission uses projected grid `gridW + 4140 W <= 4000 W`; latest-start MUST catch-up retains precedence.
- Warm-water goal detection requires confirmed heating and observed low power; the current Core contains the bounded thermostat-verification gate.
- Laundry state semantics treat explicit `IDLE`, `OFF`, `READY`, `STANDBY`, `FINISHED` and equivalent states as inactive even when stale cycle/time-to-end signals remain.
- `WW_Boilermodus` remains a direct safety-critical input.
- Quooker Logic data remains present in state/diagnostics and known measured load.
- Planner input still carries contract-price context, contract type and the PBTH price buffer.

## Planner v0.5.0 runtime facts

- 96 × 15-minute shadow horizon.
- Uses Hauwert Open-Meteo 15-minute shortwave-radiation forecast and historical calibration when sufficient samples exist.
- WW scheduling is energy-budget based, ranks full PV surplus first and then marginal import, and uses receding-horizon deadline fallback with a two-slot (30-minute) safety margin before 19:00.
- Tesla deadline slots retain priority over non-MUST WW slots; WW SHOULD slots are relocated where possible.
- Battery logic remains theoretical/simulation-only; there are no Victron writes.
- Planner itself has no Easee or boiler actuator writes.

## EV MIN7 runtime contract

The current live EV chain is internally versioned by flow names as Actuator v0.2.3, Adapter v0.1.2 and Gate v0.2.2. The embedded JSON schemas intentionally remain `EM2_EV_ACTUATOR_V0.2`, `EM2_EV_POWER_ADAPTER_V0.1` and `EM2_EV_ADAPTER_GATE_V0.2`; those schema identifiers must not be mistaken for older flow revisions.

The executable current mapping is fixed 3×230 V, 690 W/A, with a minimum executable charging current of 7 A. Adapter and gate fail closed below the minimum; the live actuator accepts only 0 A or integer 7–16 A and requires a PASS from the aligned MIN7 gate before applying non-zero current.

## Reconciliation evidence

Exact live source capture commits made during this reconciliation:

- Settings Sync v0.4.1: `1731ae37f9c209ebefe63eef9884fcb62a5352f0`
- Publisher v1.0.13: `d7eb1872c503dca977fd2f9561267fff7f2f7865`
- EV Actuator v0.2.3: `eb890d32edc462ed8f735185f0d4e413da574525`
- Planner v0.5.0: `c713b7310f2e7426a446dcba1dfc753aa3902711`
- Core v0.11i: `daa756a424ef3281feaa8fb3622871ecda5eeb97`
- EV Adapter v0.1.2: `8d4f7856887ac61a737c42dbefa9a180ab0e6c35`
- EV Adapter Gate v0.2.2: `315cdc461b066ae16ab7abe4c2af6b33bd0d511b`

## Known metadata caveat

The live Core Advanced Flow contains an old note card referring to `v0.11g` and commit `bd4edecc`. That note is stale metadata. The live flow name and executable HomeyScript action identify v0.11i (`PUB_VERSION='EM2_CORE_STATE_V0.11i'`) and are authoritative. Do not use the old note card as the current source reference.

## Certification state

- Direct live Homey read of the changed runtime components: **PASS**.
- Exact source capture in GitHub for Core v0.11i, Planner v0.5.0, Publisher v1.0.13, Settings Sync v0.4.1, EV Actuator v0.2.3, EV Adapter v0.1.2 and EV Gate v0.2.2: **PASS**.
- No Homey writes performed during reconciliation: **PASS**.
- This baseline supersedes the 2026-08-30 baseline for current-state work.

Final Homey/GitHub sync certification requires a final post-update Homey inventory read and GitHub source/policy readback after this baseline and source policy have been committed.
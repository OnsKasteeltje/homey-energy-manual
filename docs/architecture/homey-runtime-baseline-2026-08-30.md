# Homey runtime baseline — 2026-08-30

Status: **authoritative runtime reconciliation baseline for documentation generation — CERTIFIED PASS for the reconciled current runtime scope below**.

This file records the Homey flow inventory observed directly on 2026-08-30 after Cleanup Round 2A. It is the reference for deciding whether a component is LIVE, ACTIVE SHADOW, VALIDATION, ROLLBACK/LEGACY, TEMP/RETIRED or HISTORICAL. Software documentation generated from repository Markdown must not infer current production status from file names alone; it must reconcile against this baseline and the exact runtime source files named below.

## Documentation rule

For every process flow in generated software documentation:

1. Prefer exact live runtime source captured from Homey over older candidate/patch/prep files.
2. Use this registry to determine whether a Homey flow is current LIVE/ACTIVE SHADOW versus rollback, validation or historical.
3. Do not present TEMP, DONE, ONE-SHOT, ROLLBACK or explicitly replaced flows as current architecture.
4. Do not treat the word SHADOW as obsolete by itself; several SHADOW flows are intentional active architecture.
5. Flow diagrams must describe current implemented runtime, not intended future design.
6. For Core, `src/homey/core/core-v0.11f.live-homey.js` is the authoritative source baseline until a newer live version is reconciled.

## Current core and orchestration

| Classification | Homey flow | Flow ID | Runtime status / role |
|---|---|---|---|
| LIVE | `EM v2 | 00 Core Tick | v0.11f (Planner Tesla Headroom)` | `227f8d3b-7551-46dd-837d-1b8c69add824` | enabled; 5-minute Core; exact source captured as `src/homey/core/core-v0.11f.live-homey.js`; no physical device writes; Planner Tesla admission uses projected grid `gridW + 4140 W <= 4000 W`; `PUB_VERSION=EM2_CORE_STATE_V0.11f`, schema 2.12 |
| ACTIVE SHADOW | `EM v2 | 12 Input | Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER` | `758f3353-51f5-4e68-a1f4-3acf30ec5a87` | active input aggregation / parity architecture; parity rev107 previously PASS with zero mismatches |
| ACTIVE SHADOW | `EM v2 | 45 Planner | 24h Energy Plan v0.4.9 SHADOW LOW-LOAD` | `27617767-0a64-43a3-9bcb-e34b0dd6a5c0` | active planner |
| LIVE publication | `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD` | `5b3b80fe-96d1-406d-91ef-cf75a4e65d45` | active planner publication |
| LIVE publication | `EM v2 | 40 Data | Publisher v1.0.12 SCHEDULED LOW-LOAD` | `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd` | active public-state publisher |
| LIVE watchdog | `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | `8526109f-5c8d-428e-ac24-85a71c95ac36` | active freshness watchdog |
| LIVE config | `EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD` | `9193b3ae-1e3d-4b52-aa95-60aff099e68a` | enabled; targeted Logic reads; 15-minute cadence; exact runtime in `src/homey/config/ems-settings-sync-v0.4-targeted-15min.js` |
| LIVE context | `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD` | `69648157-892b-49d2-bc4d-e61a1a4d78ab` | current FIXED/DYNAMIC price-context bridge; FIXED does not invoke PBTH |

## Current EV path

| Classification | Homey flow | Flow ID | Role |
|---|---|---|---|
| LIVE | `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD` | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | current Power Intent producer |
| LIVE | `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` | `fea23193-a03f-49dd-9780-7e72ee48747d` | current EV physical-write owner |
| ACTIVE SHADOW | `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW` | `953e9b18-3576-4557-b940-ed4a64eb2516` | shadow adapter retained for architecture/validation pending Round 2B dependency review |
| VALIDATION | `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ` | `557ed7e8-9efe-4173-bc06-8e629214e172` | validation gate |
| VALIDATION | `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ` | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | validation gate |
| OBSERVABILITY | `EM v2 | 81 Observability | EV Control Status v0.1` | `f6edba38-ddf1-45e5-890e-c183aa2055d5` | EV control observability |
| REPLACED / LEGACY | `Tesla laden v2.7.15 + RC run lease [DISABLED - REPLACED BY EV POWER ARCH]` | `e82dd325-8a09-4b43-a0b4-1be277ab5d91` | never document as current EV control owner |

## Current warm-water path

| Classification | Homey flow | Flow ID | Role |
|---|---|---|---|
| LIVE | `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE` | `40d45aeb-174e-4a83-9a42-71ae46065cb4` | current boiler physical-write owner |
| ACTIVE SHADOW | `EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW` | `472d0355-3bb9-4a42-be43-114b57822136` | current WW adapter shadow layer |
| ACTIVE SHADOW | `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` | `5538f1c9-9a21-4328-9896-942952f5c55f` | post-goal opportunity logic |
| ACTIVE SHADOW | `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` | `543664be-d07a-4099-92d1-07878b73215d` | manual-only seasonal source advice; no source switch write |
| OBSERVER | `EM v2 | 15 State | Warm Water Observer v0.2` | `957a85b5-a4ff-4fe2-bc6b-2e56e60387ea` | WW state observation |
| LEGACY CANDIDATE | `EM v2 | 60 Control | Warm Water Actuator v0.6` | `2b9284f6-1d41-453e-a8f9-10c634f56fe5` | older actuator; dependency-check before deletion; do not describe as current actuator |

## Core runtime truth that documentation must preserve

The exact live Core v0.11f source establishes several facts that supersede older design assumptions: Core itself still performs a broad `Homey.logic.getVariables()` scan every five minutes; `WW_Boilermodus` remains a direct safety-critical Core input; Planner price input comes through `EM2_ContractPrice_Context`, `EM2_Contract_Type` and `TEMP_PBTH_JSON_BUFFER`; legacy M7 context variables remain fallback inputs; Quooker Logic data is again present in live Core state/diagnostics and `knownMeasuredLoadW`; P1 remains authoritative for flex budget; Core performs no physical device writes.

## Data, evidence and history

Current inventory also includes `EM v2 | 70 History | Day Series v0.6.1 TARGETED LOCAL SAMPLER`, `EM v2 | 76 Publish | Day Series v0.1.1 TARGETED LOW-FREQUENCY`, `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first`, `EM v2 | 70 History | Control Audit v0.4 low-load`, `EM v2 | 72 History | Immutable Day Archive v0.1`, and the washer/dryer analyse, logging and publication flows. Their presence in Homey is current, but enabled/disabled state was not individually re-read during this reconciliation; documentation must therefore avoid claiming runtime enablement unless separately verified.

## Contract and price legacy/shadow variants still present

The Homey inventory still contains older alternatives such as `EM v2 | 30 Context | Contract Price Adapter v0.8`, `EM v2 | 30 Context | Price + PV v0.5.1 [ROLLBACK ACTIVE]`, `EM v2 | 30 Context | Price + PV v0.6.1 SHADOW`, `EM v2 | 30 Context | PBTH API Price Adapter v0.1 SHADOW`, `EM v2 | 40 Decision | Contract-aware v0.1 [ROLLBACK]` and `EM v2 | 40 Decision | Contract-aware v0.2`. These must not be promoted to current production status merely because they still exist. The current contract-price bridge is v0.10 above.

## Cleanup Round 2A — removed from Homey

The following explicit temporary one-shot/done flows were removed on 2026-08-30. Deletion was executed with a 5-second Homey Flow delay between each delete and verified afterwards against the Homey flow inventory:

- `TEMP | WW Planner v0.4.2 Regression Harness Run [DONE]` (both copies)
- `TEMP | P1 Runtime Probe v0.1 [DONE]`
- `TEMP | Planner v0.4.4 Logic Provisioning [DONE]`
- `TEMP | Planner v0.4.4 Snapshot Smoke [ONE-SHOT]`
- `TEMP | Planner Shadow v0.4 Event Smoke [DONE]`
- `TEMP | EV STOP ownership LIVE arm [ONE-SHOT]`
- `TEMP | EV LIVE production promotion [ONE-SHOT]`
- `TEMP | Core v0.11b Snapshot Provisioning [ONE-SHOT]`

These are historical evidence only and must not appear as current runtime components in generated architecture documentation.

## Remaining TEMP flows after Round 2A

The inventory still contains temporary candidates that require separate dependency review before deletion, including `TEMP | PBTH API vs Card A-B v0.3`, `TEMP | Planner v0.4.4 Smoke Shutdown`, multiple `TEMP | EM2 Control EV Observer` / `Observer Setup` flows, `TEMP | EM2 Control EV Observer Setup 2026-08-29`, and standard flow `TEMP | EM2 Control EV Semantic Observer 2026-08-29`. Reconciliation/cleanup helper flows are temporary and must not be documented as architecture.

## Exact Core v0.11f reconciliation

**PASS.** On 2026-08-30 the live Core Advanced Flow was read directly and its exact HomeyScript action source was committed without reconstruction as:

`src/homey/core/core-v0.11f.live-homey.js`

GitHub readback confirms the file exists and begins with the live v0.11f header, contains `PUB_VERSION='EM2_CORE_STATE_V0.11f'`, and contains `plannerTeslaProjectedGridW=gridW+PLANNER_TESLA_MIN_POWER_W`. The manually copied live HomeyScript supplied during the reconciliation session independently shows the same v0.11f runtime identity and projected-grid logic.

## Certification state

- Flow inventory reconciliation: **PASS** for the observed 2026-08-30 inventory.
- Settings Sync v0.4 status/version: **PASS** from direct Homey validation performed on 2026-08-30.
- Contract Price Adapter v0.10 and FIXED switch acceptance: **PASS** from controlled runtime validation performed on 2026-08-30.
- Cleanup Round 2A inventory: **PASS** after post-cleanup list verification.
- Exact Core v0.11f source in GitHub: **PASS**.
- Core README current-version/source reference: **PASS**.
- Overall current-runtime registry for documentation generation: **PASS for the explicitly reconciled runtime scope in this file**.

This certification does not mean every historical Markdown file in the repository has been rewritten. Documentation generators must use this registry and exact current runtime sources as authority and must ignore superseded historical/candidate files for current-state diagrams and descriptions. A separate repository-wide Markdown consistency sweep remains appropriate before producing a final polished software document.

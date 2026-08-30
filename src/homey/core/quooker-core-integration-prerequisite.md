# Quooker — Core integration prerequisite

Status: **SEMANTIC COMMIT PRODUCER v0.4 DEPLOYED DISABLED / SHADOW VALIDATION PENDING**

Date: 2026-08-30

## Project decision

The current Quooker signal path must **not** be used directly as an event-driven source for Core v0.11b or the Core Snapshot Aggregator.

`EM_Quooker_Last_Sample` is coupled to the former frequent P1/heartbeat path. Using that variable directly as an aggregator trigger would cause unnecessary wake-ups and fan-out.

Canonical marker: `EM_Quooker_Commit` (`f1b9000f-9f98-480e-89a5-7518d7b82a6c`).

## Low-load semantic commit contract

Schema: `EM_QUOOKER_COMMIT_V0.1`.

The commit contains `generatedAt`, `semanticRevision`, `lastSample`, `active`, `powerW`, `status`, `switchOn`, `baselineL3W`, `lastTransition`, `lastHeatingAt`, `lastHeatingPowerW`, and `transitionHistory`.

A new commit is written only when the effective semantic payload changes or when the previous commit requires the 120-second freshness keepalive. `generatedAt` and `lastSample` are excluded from the semantic signature. `semanticRevision` increments only for a semantic payload change.

## Homey producer v0.4

Advanced Flow: `04a713a5-105e-439a-a93a-441fb2ca50b4`

Name: `EM v2 | 01 Quooker Detector | v0.4 LOW-LOAD SEMANTIC COMMIT SHADOW`

Deployment state on 2026-08-30: `enabled=false`, `broken=false` as returned directly by the update operation.

Runtime design:

- two-minute schedule plus manual start;
- one targeted Logic read: `EM_Quooker_Commit`;
- two targeted device reads in parallel: Cooker switch and P1;
- maximum one Logic write per run: `EM_Quooker_Commit`;
- no `Homey.logic.getVariables()`;
- no discovery calls;
- no P1 heartbeat dependency;
- no physical device writes;
- Cooker `onoff` remains authoritative for OFF/ON;
- P1 L3 delta remains the heating/power signature;
- baseline smoothing remains limited to Cooker OFF state;
- transition history remains bounded to eight entries;
- last-heating timestamp is updated on transition into HEATING rather than on every heating sample.

The previous v0.3 legacy-variable fan-out is intentionally not reproduced in v0.4. The compact commit is the new publication boundary. Existing production consumers are not cut over yet, which is why v0.4 remains disabled during SHADOW validation.

## Homey API discipline used for deployment

The deployment followed `docs/architecture/homey-api-access-guidelines.md`:

1. one targeted pre-change read of the existing Quooker Advanced Flow;
2. one Advanced Flow update;
3. no separate post-read because the update response itself returned the complete updated Flow and confirmed `enabled=false` and `broken=false`.

No autocomplete/discovery burst, Flow start, physical write, or additional Homey verification call was performed.

## Aggregator integration after producer validation

After a controlled SHADOW producer run validates the commit:

- trigger the Core Snapshot Aggregator on `EM_Quooker_Commit changed`, never `EM_Quooker_Last_Sample`;
- perform one targeted read of the commit;
- map it into `EM2_Core_Input.sources.quooker`;
- retain existing lease/semantic suppression;
- retain hourly FULL reconciliation temporarily during SHADOW validation.

## Acceptance gate

Completed:

- stable ID resolved;
- v0.4 producer deployed disabled;
- broad Logic scan removed;
- heartbeat dependency removed;
- commit construction uses canonical previous state and targeted device reads only.

Still required before production v0.11b cut-over:

- controlled SHADOW run of v0.4;
- validate commit schema and values;
- validate semantic-change behavior and 120-second keepalive;
- wire aggregator to `EM_Quooker_Commit changed` with one compact read;
- parity against legacy Quooker semantics;
- confirm no material CPU or 429/rate-limit regression.

Until those criteria pass, Quooker remains a blocker for production cut-over of Core v0.11b.
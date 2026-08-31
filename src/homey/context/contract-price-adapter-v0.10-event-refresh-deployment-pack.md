# Contract Price Adapter v0.10 — Event Refresh Deployment Pack

Status: **FULLY PREPARED OUTSIDE HOMEY / ONLY ONE-SHOT STATE PROVISION + ONE CURRENT FLOW READ + ONE ATOMIC UPDATE REMAIN**

Purpose: prepare and validate everything possible outside Homey first. Homey is used only for runtime-specific state provisioning and the final current-state-preserving mutation.

## Live baseline

- Flow: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Existing schedule: every 15 minutes + manual start
- DYNAMIC action: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`, `period=next_hours`
- Canonical DYNAMIC context already includes validated `priceSeries: prices`
- No actuator/device writes
- Remaining functional gap: PBTH event branch only

## PBTH trigger resolved outside Homey

Upstream source file: `gruijter/com.gruijter.powerhour/.homeycompose/flow/triggers/new_prices.json`.

It defines:

```text
base trigger id     new_prices
title               New prices received
titleFormatted      New prices received for [[period]]
device filter       driver_id=dap|dap15|dapg
periods             this_day | tomorrow | next_hours
tokens              prices | provider
```

Our branch uses device `d28cdd44-ab8c-4f4c-8ea7-279f444ecd81` and `period=next_hours`, therefore the source-derived device-scoped card ID is:

```text
homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:new_prices
```

No Homey trigger-card enumeration is part of the deployment plan. Only if Homey explicitly rejects this source-derived card ID may one targeted verification be considered.

The PBTH event is only a wake-up signal. Semantic comparison remains mandatory because an event does not prove that the useful future horizon extended.

## Stable IDs — no rediscovery

```text
PBTH device                        d28cdd44-ab8c-4f4c-8ea7-279f444ecd81
Contract Price Adapter flow       69648157-892b-49d2-bc4d-e61a1a4d78ab
EMS_ContractType                  8d346495-f183-4072-86d0-c4bc9da94e2e
EM2_Contract_Type                 211e5846-aada-4607-8d52-01b2ef578866
TEMP_PBTH_JSON_BUFFER             29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b
EM2_ContractPrice_Context         93e41221-6b4d-4f5f-83dc-997c9620f758
EM2_ContractPrice_Source          3e5a182d-2479-479a-bb58-42a27f4a4e23
EM2_ContractPrice_Quality         abedc6f4-cfee-4496-9b3c-418f1f3ad2bc
EM2_ContractPrice_Horizon         587ea957-f9e9-44c7-b975-3bed53bd9ab8
EM2_ContractPrice_UpdatedAt       77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb
Planner flow                      27617767-0a64-43a3-9bcb-e34b0dd6a5c0
Planner publisher flow            5b3b80fe-96d1-406d-91ef-cf75a4e65d45
```

## Exact one-shot state provisioning

Prepared script:

`src/homey/context/contract-price-event-refresh-v0.11-provision-state.homeyscript.js`

It performs exactly one API mutation:

```js
Homey.logic.createVariable({
  variable: {
    name: 'EM2_ContractPrice_EventRefresh_State',
    type: 'string',
    value: '{"schema":"EM2_PRICE_EVENT_REFRESH_STATE_V0.1","lastAttemptAt":null,"cooldownUntil":null,"lastResult":"NEVER","lastReason":null}'
  }
})
```

Crucially, `createVariable()` returns the created object including its ID. Therefore **no follow-up Logic enumeration, autocomplete lookup or full variable read is needed**. The script returns the ID directly. Run it exactly once; do not retry blindly because a second successful execution would create a duplicate variable.

`EVENT_STATE_ID` is then substituted into the prepared eligibility and post-fetch scripts.

## Prepared scripts

```text
contract-price-event-refresh-v0.11-provision-state.homeyscript.js
contract-price-event-refresh-v0.11-eligibility.homeyscript.js
contract-price-event-refresh-v0.11-post-fetch.homeyscript.js
build-contract-price-event-refresh-v0.11-patch.mjs
```

The first three contain the complete runtime logic. The patch builder performs no Homey calls.

## Exact event branch

```text
PBTH new_prices(period=next_hours)
  -> HomeyScript runCode_v2 condition: EVENT ELIGIBILITY GATE
      false -> stop
      true  -> PBTH prices_json(next_hours) exactly once
             -> cloned existing TEMP_PBTH_JSON_BUFFER setter
             -> HomeyScript runCode_v2 condition: EVENT POST-FETCH PROCESSOR
                 false -> stop; no canonical publish
                 true  -> canonical context update -> normal downstream semantic chain
```

Eligibility: `DYNAMIC && horizonHours < 12 && cooldown expired`.

Degraded/unchanged starts a 60-minute cooldown. A semantic extension/change clears it.

## Deterministic flow-patch builder

Prepared file:

`src/homey/context/build-contract-price-event-refresh-v0.11-patch.mjs`

It takes exactly two runtime inputs:

1. the **single current production Advanced Flow read** immediately before mutation;
2. the provisioned `EVENT_STATE_ID` returned by the one-shot provisioning script.

It then, entirely outside Homey:

- verifies the expected existing PBTH `prices_json(next_hours)` action exists;
- identifies its existing immediate buffer-setter successor;
- clones those exact live cards rather than guessing their Homey card schema;
- rewrites the cloned PBTH droptoken source to the new event PBTH node;
- injects the source-derived PBTH `new_prices(period=next_hours)` trigger;
- injects the complete eligibility and semantic-processor HomeyScript conditions;
- uses fixed, pre-generated node UUIDs;
- leaves all existing scheduled cards and connections unchanged;
- validates basic static invariants;
- emits the **complete patched Advanced Flow JSON** for one atomic update.

Usage:

```bash
node src/homey/context/build-contract-price-event-refresh-v0.11-patch.mjs \
  current-contract-price-adapter.json \
  <EVENT_STATE_ID> \
  contract-price-adapter-v0.11.patched.json
```

This design intentionally avoids trying to reconstruct the complete production Advanced Flow from stale documentation. One fresh current-flow read is required immediately before an atomic full-flow update because Homey's update API replaces the whole Advanced Flow object. That read is therefore mutation-safety-critical, not exploratory discovery.

## GitHub-first deployment order

1. **DONE:** exact PBTH trigger resolved from upstream source; no Homey card enumeration required.
2. **DONE:** provisioning script prepared.
3. **DONE:** eligibility and post-fetch processors prepared.
4. **DONE:** deterministic full-flow patch builder prepared.
5. Run the one-shot state provisioning only when Homey is not rate-limited; capture `EVENT_STATE_ID` directly from its return value.
6. Commit/substitute that ID in GitHub before touching the production flow.
7. Read production flow `69648157-892b-49d2-bc4d-e61a1a4d78ab` exactly once.
8. Run the patch builder offline against that read.
9. Review generated diff/invariants outside Homey.
10. Perform one atomic Advanced Flow update.
11. Do only targeted post-update validation; stop immediately on HTTP 429 and do not retry in the same round.

## Homey call budget for the actual deployment

Expected minimum:

```text
1  one-shot provisioning execution          -> returns EVENT_STATE_ID
1  get current production Advanced Flow      -> required to preserve full current graph
1  atomic update of production Advanced Flow -> event branch only
1  targeted post-update verification         -> only if Homey remains healthy
```

No `list_devices`, no Logic enumeration, no trigger/action card enumeration, no TEMP-flow inspection, and no repeated production-flow reads are part of this plan.

## Acceptance matrix

| Case | PBTH calls | Context publication | Cooldown | Planner fan-out |
|---|---:|---|---|---|
| FIXED | 0 | none | unchanged | none |
| DYNAMIC, horizon >=12h | 0 | none | unchanged | none |
| DYNAMIC, <12h, cooldown active | 0 | none | unchanged | none |
| DYNAMIC, <12h, degraded | 1 | none | 60 min | none |
| DYNAMIC, <12h, unchanged | 1 | none | 60 min | none |
| DYNAMIC, <12h, changed/extended | 1 | once | cleared | once |

## Rollback

Remove/disable only the six fixed-ID event-branch nodes generated by the patch builder. Retain the existing scheduled 15-minute v0.10 route and validated `priceSeries` field. No actuator rollback is required.

## Definition of done

Live branch exists; scheduled fallback unchanged; DYNAMIC/<12h/cooldown gate enforced; max one PBTH call per admitted event; unchanged data causes no canonical republish; successful semantic update reaches Planner once; exact state ID committed to GitHub; Homey and GitHub topology match.

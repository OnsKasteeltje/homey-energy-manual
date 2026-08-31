# Contract Price Adapter v0.10 — Event Refresh Deployment Pack

Status: **READY OUTSIDE HOMEY / ONLY EVENT STATE ID REMAINS TO PROVISION**

Purpose: prepare and validate everything possible outside Homey first. Homey is used only for runtime-specific state provisioning and the final controlled flow mutation.

## Live baseline

- Flow: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Existing schedule: every 15 minutes + manual start
- DYNAMIC action: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`, `period=next_hours`
- Canonical DYNAMIC context already includes validated `priceSeries: prices`
- No actuator/device writes
- Remaining functional gap: PBTH event branch only

## PBTH trigger resolved from upstream source — no Homey discovery needed

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

Our branch uses device `d28cdd44-ab8c-4f4c-8ea7-279f444ecd81` and `period=next_hours`. Expected device-scoped Homey representation: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:new_prices`. Only verify this representation once if the Homey mutation API rejects the source-derived form; do not run broad/repeated trigger-card discovery.

PBTH community evidence also confirms that a `New prices received` event can occur around a calendar boundary without the useful future horizon being complete. Therefore the event is only a wake-up signal; semantic comparison remains mandatory.

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

## Only remaining runtime identifier

`EVENT_STATE_ID` = exact ID of Text Logic variable `EM2_ContractPrice_EventRefresh_State` after one-time provisioning.

Initial payload:

```json
{"schema":"EM2_PRICE_EVENT_REFRESH_STATE_V0.1","lastAttemptAt":null,"cooldownUntil":null,"lastResult":"NEVER","lastReason":null}
```

Capture it by exact-name targeted lookup. Never enumerate Logic variables broadly.

## Exact remaining mutation delta

```text
PBTH new_prices(period=next_hours)
  -> EVENT ELIGIBILITY GATE
      false -> stop
      true  -> PBTH prices_json(next_hours) exactly once
             -> TEMP_PBTH_JSON_BUFFER
             -> EVENT POST-FETCH PROCESSOR
                 false -> stop; no canonical publish
                 true  -> canonical context update -> normal downstream semantic chain
```

Eligibility: DYNAMIC + horizonHours<12 + cooldown expired. Degraded/unchanged starts 60-minute cooldown; semantic extension/change clears it.

## GitHub-first deployment order

1. Keep candidate, exact scripts, topology, acceptance matrix and rollback current in GitHub.
2. Provision exactly one `EM2_ContractPrice_EventRefresh_State` variable.
3. Obtain its ID via exact-name autocomplete lookup only.
4. Commit the ID into GitHub and replace both script placeholders.
5. Read live production flow exactly once to verify baseline.
6. Prepare one atomic patch preserving all existing cards/connections and adding only the event branch.
7. No change to scheduled v0.10 path or `priceSeries`.
8. Stop immediately on HTTP 429; no same-round retry.

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

Remove/disable only the event branch. Retain existing scheduled 15-minute v0.10 route and validated `priceSeries` field. No actuator rollback is required.

## Definition of done

Live branch exists; scheduled fallback unchanged; DYNAMIC/<12h/cooldown gate enforced; max one PBTH call per admitted event; unchanged data causes no canonical republish; successful semantic update reaches Planner once; exact state ID committed to GitHub; Homey and GitHub topology match.

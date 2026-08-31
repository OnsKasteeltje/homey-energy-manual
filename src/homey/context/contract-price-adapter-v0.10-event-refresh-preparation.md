# Contract Price Adapter v0.10 — Event-driven horizon refresh preparation

Status: **PREPARED IN GITHUB / LIVE v0.10 BASELINE VERIFIED / EVENT REFRESH NOT YET DEPLOYED**

This change now targets the existing live Homey flow `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD` (flow ID `69648157-892b-49d2-bc4d-e61a1a4d78ab`). The live flow already carries the v0.10 name, but its current topology is still scheduled/manual only and does not yet implement the PBTH event-refresh branch described here.

The existing 15-minute schedule remains the fallback and must not be removed.

## Goal

When the currently known dynamic-price horizon is shorter than 12 hours, react quickly when PBTH announces newly received prices, while preventing repeated unsuccessful refreshes from adding Homey load.

## Runtime policy

1. Keep the existing scheduled live v0.10 path every 15 minutes.
2. Add a PBTH `New prices received for period` event path.
3. Event path is eligible only when contract is DYNAMIC and the last known `horizonHours < 12`.
4. Event path requests `prices_json(next_hours)` once.
5. Compare the resulting price series semantically with the previously accepted series.
6. If the series grows or changes, publish the new price context immediately. Downstream Planner refresh is then allowed through the normal semantic-change chain.
7. If the event produces no new information, record a failed-event-refresh timestamp and suppress further event refresh attempts for 60 minutes.
8. Maximum unsuccessful event-driven horizon refresh rate: **1 per hour**.
9. A successful semantic price update clears the failed-refresh cooldown.
10. Never loop/retry inside one run.
11. No `Homey.logic.getVariables()`, no `Homey.devices.getDevices()`, no actuator/device writes.
12. Add `priceSeries: prices` to the normal scheduled DYNAMIC context so exact value-level semantic comparison is possible.

## Proposed state

Use one dedicated Logic text variable when deployed:

`EM2_ContractPrice_EventRefresh_State`

Proposed JSON schema:

```json
{
  "schema": "EM2_PRICE_EVENT_REFRESH_STATE_V0.1",
  "lastAttemptAt": null,
  "cooldownUntil": null,
  "lastResult": "NEVER",
  "lastReason": null
}
```

The variable ID must be captured once after provisioning. Do not invent or broadly rediscover other known IDs.

## Semantic fingerprint / comparison

The event path should compare the actual accepted PBTH price array, not only slot count. The canonical DYNAMIC context therefore gains:

```js
priceSeries: prices,
```

A refresh counts as successful when either:

- `newPrices.length > previousPrices.length`; or
- the effective horizon extends; or
- any overlapping accepted price differs materially.

A degraded array (`<4` contiguous valid slots) must fail closed and keep the prior accepted context.

## Important Homey Flow topology

The PBTH trigger must **not** directly run the existing scheduled chain unconditionally. Put an eligibility/cooldown gate before the PBTH `prices_json(next_hours)` action.

Preferred topology:

```text
PBTH New prices received for period
        |
        v
Targeted eligibility gate
(contract=DYNAMIC, horizon<12h,
 cooldown expired)
        |
        +-- SKIP --> stop
        |
        v
PBTH prices_json(next_hours)   [exactly once]
        |
        v
TEMP_PBTH_JSON_BUFFER
        |
        v
Targeted semantic processor
        |
        +-- unchanged/degraded --> record cooldown; stop
        |
        +-- changed/extended ----> publish context --> normal semantic downstream chain
```

The existing every-15-minute v0.10 schedule remains independent and is the recovery/fallback path.

## Known stable IDs

- Live Contract Price Adapter flow: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- PBTH device: `d28cdd44-ab8c-4f4c-8ea7-279f444ecd81`
- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EM2_Contract_Type`: `211e5846-aada-4607-8d52-01b2ef578866`
- `TEMP_PBTH_JSON_BUFFER`: `29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b`
- `EM2_ContractPrice_Context`: `93e41221-6b4d-4f5f-83dc-997c9620f758`
- `EM2_ContractPrice_Source`: `3e5a182d-2479-479a-bb58-42a27f4a4e23`
- `EM2_ContractPrice_Quality`: `abedc6f4-cfee-4496-9b3c-418f1f3ad2bc`
- `EM2_ContractPrice_Horizon`: `587ea957-f9e9-44c7-b975-3bed53bd9ab8`
- `EM2_ContractPrice_UpdatedAt`: `77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb`

Only two runtime identifiers remain to be captured on Homey: the new event-state Logic ID and the exact PBTH `New prices received for period` trigger-card ID/args.

## Deployment prerequisites

Before any Homey mutation:

- confirm no other ChatGPT/Homey call sequence is active;
- perform only the two remaining targeted discoveries;
- provision exactly one new Logic state variable if still absent;
- use known stable IDs for all existing variables/cards;
- patch the existing live flow rather than creating a competing production adapter;
- deploy event branch disabled/SHADOW first;
- no physical writes;
- stop immediately on HTTP 429, with no retry.

## Acceptance tests

A. `horizonHours >= 12`: PBTH event causes zero `prices_json` request.

B. `horizonHours < 12`, cooldown clear, new prices available: exactly one PBTH request; price horizon/series changes; context publishes once; Planner may refresh once.

C. `horizonHours < 12`, cooldown clear, no new prices: exactly one PBTH request; no context/Planner publication; cooldown starts.

D. Repeated PBTH events during cooldown: zero PBTH price requests.

E. After 60 minutes with horizon still <12: next PBTH event may perform exactly one new request.

F. Successful update: cooldown clears.

G. Existing scheduled 15-minute path continues to work independently.

H. Scheduled DYNAMIC context contains `priceSeries` with length equal to `slots`.

## Non-goals

- No polling faster than the existing schedule.
- No fabricated price slots after the known horizon.
- No actuator behavior changes.
- No second production Contract Price Adapter.
- No broad Homey discovery.

For the exact scripts and controlled deployment sequence, use `contract-price-adapter-v0.10-event-refresh.candidate.md` and `contract-price-adapter-v0.10-event-refresh-deployment-pack.md`.

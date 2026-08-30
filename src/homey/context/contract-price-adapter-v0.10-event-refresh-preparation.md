# Contract Price Adapter v0.10 — Event-driven horizon refresh preparation

Status: **PREPARED / NOT DEPLOYED TO HOMEY**

This change extends v0.9 DYNAMIC LOW-LOAD without changing its normal 15-minute schedule.

## Goal

When the currently known dynamic-price horizon is shorter than 12 hours, react quickly when PBTH announces newly received prices, while preventing repeated unsuccessful refreshes from adding Homey load.

## Runtime policy

1. Keep the existing scheduled v0.9 path every 15 minutes.
2. Add a PBTH `new prices received` event path.
3. Event path is eligible only when the last known `horizonHours < 12`.
4. Event path requests `prices_json(next_hours)` once.
5. Compare the resulting price series semantically with the previously accepted series.
6. If the series grows or changes, publish the new price context immediately. Downstream Planner refresh is then allowed through the normal semantic-change chain.
7. If the event produces no new information, record a failed-event-refresh timestamp and suppress further event refresh attempts for 60 minutes.
8. Maximum unsuccessful event-driven horizon refresh rate: **1 per hour**.
9. A successful semantic price update clears the failed-refresh cooldown.
10. Never loop/retry inside one run.
11. No `Homey.logic.getVariables()`, no `Homey.devices.getDevices()`, no actuator/device writes.

## Proposed state

Use one dedicated Logic text variable when deployed:

`EM2_ContractPrice_EventRefresh_State`

Proposed JSON schema:

```json
{
  "schema": "EM2_PRICE_EVENT_REFRESH_STATE_V0.1",
  "lastAttemptAt": null,
  "lastNoChangeAt": null,
  "lastSuccessAt": null,
  "lastAcceptedSlots": null,
  "lastAcceptedFingerprint": null
}
```

The variable ID must be discovered/provisioned only during the controlled Homey deployment. Do not invent or rediscover other known IDs.

## Semantic fingerprint

The event path should compare the actual accepted PBTH price array, not only slot count. Suggested deterministic fingerprint without external crypto dependency:

```js
function priceFingerprint(prices) {
  return prices.map(v => Number(v).toFixed(6)).join('|');
}
```

A refresh counts as successful when either:

- `newPrices.length > previousPrices.length`; or
- the fingerprint differs from the previously accepted fingerprint.

A shorter but changed array should be accepted only if it passes the existing validity guards; otherwise fail closed and keep the prior accepted context.

## Event eligibility pseudocode

```js
const HORIZON_THRESHOLD_HOURS = 12;
const FAILED_REFRESH_COOLDOWN_MS = 60 * 60 * 1000;

if (contract !== 'DYNAMIC') return 'SKIP_NOT_DYNAMIC';
if (currentContext.horizonHours >= HORIZON_THRESHOLD_HOURS) return 'SKIP_HORIZON_OK';

const state = readEventRefreshState();
if (state.lastNoChangeAt && Date.now() - Date.parse(state.lastNoChangeAt) < FAILED_REFRESH_COOLDOWN_MS) {
  return 'SKIP_COOLDOWN';
}

// Only now invoke PBTH prices_json(next_hours), once.
// Parse with the same validity guards as v0.9.

if (!semanticPriceChange(previousPrices, newPrices)) {
  state.lastAttemptAt = now;
  state.lastNoChangeAt = now;
  writeEventRefreshState(state);
  return 'NO_CHANGE_COOLDOWN_STARTED';
}

publishPriceContext(newPrices);
state.lastAttemptAt = now;
state.lastSuccessAt = now;
state.lastNoChangeAt = null;
state.lastAcceptedSlots = newPrices.length;
state.lastAcceptedFingerprint = priceFingerprint(newPrices);
writeEventRefreshState(state);
return 'UPDATED';
```

## Important Homey Flow topology

The PBTH trigger must **not** directly run the existing v0.9 scheduled chain unconditionally. Put an eligibility/cooldown gate before the expensive PBTH `prices_json(next_hours)` action.

Preferred topology:

```text
PBTH new-prices event
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
        +-- unchanged --> record cooldown; stop
        |
        +-- changed ----> publish context --> normal semantic downstream chain
```

The existing every-15-minute v0.9 schedule remains independent and is the recovery/fallback path.

## Deployment prerequisites

Before any Homey mutation:

- confirm no other ChatGPT/Homey call sequence is active;
- perform only connector-required card discovery;
- provision exactly one new Logic state variable if still required by final implementation;
- use known stable IDs for all existing variables/cards;
- deploy disabled/SHADOW first;
- no physical writes;
- stop immediately on HTTP 429, with no retry.

## Acceptance tests

A. `horizonHours >= 12`: PBTH event causes zero `prices_json` request.

B. `horizonHours < 12`, cooldown clear, new prices available: exactly one PBTH request; price horizon/fingerprint changes; context publishes once; Planner may refresh once.

C. `horizonHours < 12`, cooldown clear, no new prices: exactly one PBTH request; no context/Planner publication; cooldown starts.

D. Repeated PBTH events during cooldown: zero PBTH price requests.

E. After 60 minutes with horizon still <12: next PBTH event may perform exactly one new request.

F. Successful update: cooldown clears.

G. Existing scheduled 15-minute path continues to work independently.

## Non-goals

- No polling faster than the existing schedule.
- No fabricated price slots after the known horizon.
- No Planner changes required.
- No actuator behavior changes.
- No Homey deployment as part of this preparation commit.

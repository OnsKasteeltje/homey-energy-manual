# Contract Price Adapter v0.10 — deployment gate

Status: **PREPARED OUTSIDE HOMEY / NOT DEPLOYED**

## Prepared artifacts

- `contract-price-refresh-v0.10-logic.js` — pure eligibility, cooldown, normalization and semantic-change logic.
- `contract-price-refresh-v0.10-tests.js` — offline acceptance suite for the agreed A–G scenarios plus degraded-response protection.
- Existing design baseline: `contract-price-adapter-v0.10-event-refresh-preparation.md`.

## Required deployment topology

```text
PBTH new-prices event
        |
        v
eligibility gate
DYNAMIC && horizonHours < 12 && cooldown clear
        |
        +-- no --> stop (zero prices_json calls)
        |
        v
PBTH prices_json(next_hours) exactly once
        |
        v
TEMP_PBTH_JSON_BUFFER
        |
        v
semantic processor
        |
        +-- degraded/unchanged --> keep prior context + cooldown
        |
        +-- changed/extended ---> publish price context
                                  |
                                  v
                         normal semantic downstream chain
                                  |
                                  v
                              Planner
```

## Homey deployment prerequisites

Do not deploy until all are true:

1. No other ChatGPT/Homey call sequence is active.
2. Homey is not rate-limited.
3. Exact PBTH native `new prices received` trigger card is discovered once.
4. Existing v0.9 flow ID and targeted Logic IDs are reused; no broad rediscovery.
5. Provision exactly one new Logic text variable only if the event-state variable is still required:
   `EM2_ContractPrice_EventRefresh_State`.
6. Initial deployment is disabled/SHADOW.
7. Existing scheduled 15-minute v0.9 path remains unchanged as fallback.
8. No physical actuator/device writes are introduced.
9. Stop immediately on HTTP 429; no retry.

## Acceptance gate before enablement

- A: horizon >= 12 h -> zero PBTH request.
- B: horizon < 12 h + new prices -> exactly one PBTH request, one useful context update.
- C: horizon < 12 h + unchanged -> exactly one PBTH request, no downstream publish, cooldown starts.
- D: repeated event during cooldown -> zero PBTH requests.
- E: after 60 min -> one attempt allowed again.
- F: successful update -> cooldown cleared.
- G: normal scheduled 15-minute refresh remains independent.
- Degraded response (<4 valid contiguous slots) -> prior accepted context retained.

## Explicit non-goals

- Planner never calls PBTH directly.
- No faster polling schedule.
- No retry loop.
- No broad `getVariables()` / `getDevices()` calls.
- No Homey mutation as part of this preparation.

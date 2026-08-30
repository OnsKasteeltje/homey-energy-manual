# Planner / Contract Price Adapter — short-horizon price refresh integration v0.1

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

## Purpose

Ensure the 24h Planner can obtain newly available dynamic forecast prices promptly when its known price horizon is shorter than 12 hours, without turning the Planner into a polling source and without increasing normal Homey load.

## Architecture decision

The Planner **does not directly call PBTH**.

The responsibility boundary is:

```text
Planner consumes normalized price context
          ^
          |
semantic price-context update
          |
Contract Price Adapter v0.10
          ^
          |
PBTH "new prices received" event
```

This keeps price acquisition in the Context layer and preserves the Planner as a consumer of already-normalized inputs.

The prepared Context-side implementation is documented in:

`src/homey/context/contract-price-adapter-v0.10-event-refresh-preparation.md`

## Trigger condition

The additional event-driven refresh is armed only when all of the following are true:

- contract type is `DYNAMIC`;
- current normalized `horizonHours < 12`;
- PBTH emits its native **new prices received** event;
- the failed-refresh cooldown is not active.

When admitted, exactly one `prices_json(next_hours)` request is allowed.

## Low-load rules

1. Keep the existing scheduled Contract Price Adapter path every 15 minutes as fallback/recovery.
2. Do not add a faster Planner schedule.
3. Do not let every Planner run request prices.
4. Do not poll PBTH while waiting for tomorrow's prices.
5. An admitted PBTH event may execute `prices_json(next_hours)` exactly once.
6. An unchanged result starts a 60-minute event-refresh cooldown.
7. Repeated PBTH events during cooldown cause zero additional PBTH price requests.
8. A successful semantic price update clears the cooldown.
9. No loop or immediate retry is permitted.
10. No broad `Homey.logic.getVariables()` or `Homey.devices.getDevices()` calls.
11. No actuator/device writes.

## Semantic-change contract

A Context refresh is propagated only when the accepted price series changes semantically. A change is useful when at least one of these is true:

- valid slot count increases;
- effective horizon extends;
- one or more accepted price values changes.

An identical price response must not fan out to Planner/publication.

## Planner behavior

The Planner remains read-only with respect to price acquisition:

- reads `contractPriceContext` and `priceBuffer` from its canonical Planner input;
- exposes null/unknown price slots beyond the currently known horizon;
- never fabricates missing future prices;
- recalculates after a genuine upstream semantic price-context change through the normal downstream chain;
- continues to work with the existing scheduled price refresh if no PBTH event arrives.

No dedicated Planner-side PBTH call is required.

## Diagnostics to expose after deployment

The Context layer should make the following traceable:

- `horizonHours`;
- `horizon` (`FULL` / `INTRADAY` / `DIAGNOSTIC`);
- last event refresh attempt;
- last event refresh result (`UPDATED`, `NO_CHANGE`, `SKIP_HORIZON_OK`, `SKIP_COOLDOWN`, `SKIP_NOT_DYNAMIC`);
- last successful semantic update;
- accepted slot count / deterministic price fingerprint.

Planner diagnostics should continue to expose price freshness/usability and the actual number of usable price slots.

## Acceptance tests before Homey deployment

### A — horizon sufficient

Given `DYNAMIC` and `horizonHours >= 12`, a PBTH new-price event must cause **zero** `prices_json(next_hours)` calls.

### B — new prices available

Given `DYNAMIC`, `horizonHours < 12`, cooldown clear and a PBTH event, perform exactly one price request. If the accepted series grows or changes, publish Context exactly once and allow one normal Planner recalculation.

### C — no new information

Given `DYNAMIC`, `horizonHours < 12`, cooldown clear and an unchanged PBTH response, perform exactly one request, do not republish Context/Planner, and start the 60-minute cooldown.

### D — repeated PBTH events

During cooldown, repeated PBTH events must cause **zero** PBTH price requests.

### E — cooldown expiry

After 60 minutes, if the horizon is still below 12 hours, the next PBTH event may perform exactly one request.

### F — fixed contract

For `FIXED`, the event path is always skipped and no PBTH request occurs.

### G — fallback remains intact

The normal 15-minute Contract Price Adapter schedule remains functional and independent.

## Deployment gate

This preparation deliberately performs **no Homey mutation**. Before deployment:

1. confirm no parallel ChatGPT/Homey call sequence is active;
2. provision/discover only the one event-refresh state variable required by the v0.10 preparation;
3. wire the PBTH native new-price event to the eligibility gate;
4. deploy disabled/SHADOW first;
5. execute tests A–G with strict call-count observation;
6. stop immediately on HTTP 429; do not retry;
7. only then enable the event path.

## Result

Desired behavior is prepared as an **event-driven Context-layer refresh**, not as a Planner polling feature. This gives the Planner fresh prices quickly below a 12-hour horizon while preserving the low-load architecture.
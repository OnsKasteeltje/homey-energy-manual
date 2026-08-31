# Contract Price Adapter v0.10 — Event Refresh Deployment Pack

Status: **READY OUTSIDE HOMEY**

Purpose: minimize the eventual Homey mutation/discovery round. This file contains every known stable identifier, the exact intended delta, acceptance criteria, rollback rule, and the only remaining Homey-specific unknowns.

## Live baseline

Existing live flow:

- Name: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- Flow ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Schedule: every 15 minutes plus manual start
- DYNAMIC PBTH action: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`
- PBTH argument: `period=next_hours`
- Buffer: `TEMP_PBTH_JSON_BUFFER`
- No actuator/device writes in this context flow

Verified gap in live v0.10: no event trigger branch and no `priceSeries` in canonical price context.

## Stable IDs — no rediscovery required

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

## Only remaining Homey-specific unknowns

```text
EVENT_STATE_ID   = ID of EM2_ContractPrice_EventRefresh_State after one-time provisioning
PBTH_EVENT_CARD  = exact trigger card ID/args for "New prices received for period"
```

Do not perform broad variable/device discovery to obtain these.

## Exact mutation delta

### Delta A — scheduled DYNAMIC path

Keep all current schedule/conditions/actions intact. Add only the accepted series to the canonical context:

```js
priceSeries: prices,
```

Do not change `quality`, `horizon`, `slots`, `slotMinutes`, PBTH card, contract routing, or schedule in this mutation.

### Delta B — event branch

```text
PBTH New prices received for period
  -> HomeyScript boolean: EVENT ELIGIBILITY GATE
      false -> stop
      true  -> prices_json(next_hours) exactly once
             -> write result token to TEMP_PBTH_JSON_BUFFER
             -> HomeyScript boolean: EVENT POST-FETCH PROCESSOR
                 false -> stop; no canonical context publication/fan-out
                 true  -> canonical price context changed; normal downstream semantics apply
```

Eligibility:

```text
contract == DYNAMIC
AND horizonHours < 12
AND cooldown expired
```

No-change/degraded result starts 60-minute cooldown. Successful semantic change clears cooldown.

## Event state initialization

Create exactly one Text Logic variable:

`EM2_ContractPrice_EventRefresh_State`

Initial value:

```json
{"schema":"EM2_PRICE_EVENT_REFRESH_STATE_V0.1","lastAttemptAt":null,"cooldownUntil":null,"lastResult":"NEVER","lastReason":null}
```

After creation, capture its ID once and replace `__CAPTURE_ONCE_AFTER_PROVISIONING__` in both scripts in `contract-price-adapter-v0.10-event-refresh.candidate.md`.

## Deployment safety order

1. Confirm no parallel Homey diagnostic run is active.
2. Provision only the event-state variable.
3. Capture only its exact Logic ID.
4. Capture only the PBTH event trigger card ID/args.
5. Read the current flow once to verify it still matches the documented live baseline.
6. Prepare one atomic flow patch preserving every existing card and connection.
7. Add scheduled-path `priceSeries` field.
8. Add event branch disabled/SHADOW first.
9. Validate graph integrity: no duplicate production adapter; scheduled route preserved; no actuator cards.
10. Enable event branch for controlled semantic test only when Homey is not rate-limited.

## Acceptance matrix

| Case | Expected PBTH action calls | Context publication | Cooldown | Planner fan-out |
|---|---:|---|---|---|
| FIXED contract | 0 | none | unchanged | none |
| DYNAMIC, horizon >=12h | 0 | none | unchanged | none |
| DYNAMIC, horizon <12h, cooldown active | 0 | none | unchanged | none |
| DYNAMIC, horizon <12h, degraded result | 1 | none | 60 min | none |
| DYNAMIC, horizon <12h, unchanged result | 1 | none | 60 min | none |
| DYNAMIC, horizon <12h, extended/changed result | 1 | once | cleared | once via normal chain |

## Rollback

Rollback is intentionally simple:

- disable/remove the event branch;
- retain the existing scheduled 15-minute v0.10 route;
- retaining `priceSeries` in the canonical context is safe and backward-compatible, but it can also be removed if an exact pre-change rollback is desired.

No actuator rollback is required because this change never writes devices.

## Validation evidence to capture

For the controlled test, record only:

```text
before: contractType, horizonHours, slots, updatedAt, event state
trigger: one PBTH new-prices event
actual PBTH action count: 0 or 1
result: lastResult / lastReason / cooldownUntil
after: horizonHours, slots, priceSeries length, updatedAt
planner: sourceRevision before/after only when semantic update=true
```

Avoid broad Homey device/variable dumps.

## Definition of done

Event-refresh is complete only when all are true:

- live flow contains the PBTH event branch;
- scheduled 15-minute fallback remains intact;
- event branch is gated by DYNAMIC + `<12h` + cooldown;
- one admitted event performs at most one `prices_json(next_hours)` call;
- unchanged result does not republish price context;
- successful update reaches Planner once through the normal semantic chain;
- canonical DYNAMIC context carries `priceSeries`;
- exact state-variable and PBTH trigger IDs are committed back to GitHub;
- live Homey and GitHub documentation describe the same topology.

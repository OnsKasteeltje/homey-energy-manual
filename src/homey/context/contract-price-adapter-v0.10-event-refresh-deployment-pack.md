# Contract Price Adapter v0.10 — Event Refresh Deployment Pack

Status: **READY OUTSIDE HOMEY / MINIMAL HOMEY DISCOVERY REMAINS**

Purpose: minimize the eventual Homey mutation/discovery round. Prepare and validate everything possible in GitHub first; Homey is used only for the runtime-specific identifiers and the final controlled mutation that cannot be resolved outside Homey.

## Live baseline

Existing live flow:

- Name: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- Flow ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Schedule: every 15 minutes plus manual start
- DYNAMIC PBTH action: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`
- PBTH argument: `period=next_hours`
- Buffer: `TEMP_PBTH_JSON_BUFFER`
- Canonical DYNAMIC context now includes `priceSeries: prices`
- `priceSeries` additive extension was validated through Adapter -> Planner -> Publisher without downstream regression
- No actuator/device writes in this context flow

Verified remaining gap in live v0.10: **no PBTH event trigger branch** for `New prices received for period`.

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

Do not perform broad variable/device discovery to obtain these. A single targeted card discovery and one-shot state provisioning are the intended maximum discovery footprint.

## Exact mutation delta

### Delta A — scheduled DYNAMIC path — COMPLETE

The scheduled DYNAMIC path already publishes:

```js
priceSeries: prices,
```

This has been validated. **Do not modify the scheduled path again as part of event-refresh deployment.** Keep `quality`, `horizon`, `slots`, `slotMinutes`, PBTH card, contract routing, schedule and existing connections unchanged.

### Delta B — event branch — REMAINING

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

1. Prepare/update GitHub first; do not use Homey for work that can be resolved statically.
2. Confirm no parallel Homey diagnostic run is active.
3. Capture only the exact PBTH event trigger card ID/args using one targeted discovery call if not already available.
4. Provision only `EM2_ContractPrice_EventRefresh_State` with the documented initial payload.
5. Capture only its exact Logic ID; do not enumerate Logic variables broadly.
6. Commit both runtime-specific identifiers back to GitHub and substitute them into the candidate scripts.
7. Read the current production flow once to verify it still matches this documented baseline.
8. Prepare one atomic flow patch preserving every existing scheduled card and connection.
9. Add only the event branch, disabled/SHADOW first where the Homey flow model permits it.
10. Validate graph integrity: no duplicate production adapter, scheduled route preserved, no actuator cards.
11. Enable the event branch for controlled semantic testing only when Homey is not rate-limited.
12. Stop immediately on HTTP 429; do not retry in the same round.

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

- disable/remove only the event branch;
- retain the existing scheduled 15-minute v0.10 route;
- retain the already validated `priceSeries` field in the canonical context.

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
- scheduled 15-minute fallback remains intact and unchanged;
- event branch is gated by DYNAMIC + `<12h` + cooldown;
- one admitted event performs at most one `prices_json(next_hours)` call;
- unchanged result does not republish price context;
- successful update reaches Planner once through the normal semantic chain;
- canonical DYNAMIC context continues to carry `priceSeries`;
- exact state-variable and PBTH trigger IDs are committed back to GitHub;
- live Homey and GitHub documentation describe the same topology.

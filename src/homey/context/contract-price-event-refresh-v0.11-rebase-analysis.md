# Contract Price Event Refresh v0.11 — rebase analysis

Status: **GITHUB BASELINE ONLY / NOT DEPLOYED TO HOMEY**

Date: 2026-08-31

## Current production baseline

The event-refresh work must be based on the actual Homey production runtime, not on the older v0.9 baseline.

Current production flow:

- Flow ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Name: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- Runtime state observed on 2026-08-31: `enabled=true`, `broken=false`, `triggerable=true`
- Normal triggers: every 15 minutes plus manual start
- FIXED branch: targeted configured-price context; PBTH is bypassed
- DYNAMIC branch: one PBTH `prices_json(next_hours)` call, token to `TEMP_PBTH_JSON_BUFFER`, then targeted context publication
- No `Homey.logic.getVariables()`
- No `Homey.devices.getDevices()`
- No actuator/device writes

The separate PBTH trigger `New prices received for period` is **not** present in the production flow and therefore remains undeployed.

## Why this is now v0.11 work

Two different artifacts were previously called v0.10:

1. deployed `FIXED+DYNAMIC LOW-LOAD` runtime;
2. undeployed `EVENT REFRESH CANDIDATE` based on v0.9.

To remove ambiguity, the event-refresh extension is rebased and tracked as **Contract Price Event Refresh v0.11**. This does not imply a Homey deployment yet.

## Compatibility findings

### PASS — ownership boundary

The event refresh belongs in the Context/Contract Price Adapter layer. The Planner remains a consumer and must not call PBTH directly.

### PASS — FIXED isolation

The existing v0.10 FIXED branch already bypasses PBTH. The new event branch must keep the same invariant: `contractType != DYNAMIC` means zero PBTH action calls.

### PASS — low-load fallback

The existing 15-minute scheduled v0.10 path can remain unchanged as fallback/recovery. The event path is additive and must never replace that cadence during validation.

### PASS — target PBTH cards

The intended event path still uses:

- WHEN: `New prices received for period`
- ACTION: `prices_json(next_hours)`

The event is only an opportunity signal; it does not prove that the horizon changed.

### BLOCKER 1 — scheduled v0.10 does not publish `priceSeries`

The deployed DYNAMIC context currently publishes slot count and horizon metadata but not the accepted normalized price array itself.

That means an event processor can reliably detect horizon growth (`slots` / `horizonHours`) but cannot reliably detect a material price-value change when slot count and horizon stay unchanged.

Before enabling semantic event refresh, the regular scheduled DYNAMIC path must publish:

```js
priceSeries: prices
```

This is an additive field within `EM2_UNIFORM_PRICE_CONTEXT_V0.4`; existing consumers may ignore it.

### BLOCKER 2 — no event-state variable in the current production topology

The proposed event branch requires one targeted Logic text variable:

`EM2_ContractPrice_EventRefresh_State`

No broad Logic-variable discovery may be introduced. The variable should be provisioned once, its ID captured once, and that fixed ID used by the eligibility and post-fetch scripts.

### BLOCKER 3 — candidate scripts are based on v0.9 terminology

The existing `contract-price-adapter-v0.10-event-refresh.candidate.md` refers to v0.9 as the base runtime. Its topology and scripts must not be deployed verbatim. The implementation must be rebased onto the current v0.10 FIXED+DYNAMIC flow and preserve the current FIXED branch.

## Required v0.11 topology

```text
existing scheduled v0.10 FIXED+DYNAMIC path --------------------+
                                                                  |
PBTH: New prices received for period                              |
        |                                                         |
        v                                                         |
DYNAMIC? -------------------------------------------------> STOP   |
        |                                                         |
        v                                                         |
read current Contract Price Context                               |
        |                                                         |
        +-- horizonHours >= 12 ---------------------------> STOP   |
        |                                                         |
        +-- cooldown active -----------------------------> STOP   |
        |                                                         |
        v                                                         |
PBTH prices_json(next_hours) exactly once                         |
        |                                                         |
        v                                                         |
existing TEMP_PBTH_JSON_BUFFER                                    |
        |                                                         |
        v                                                         |
normalize + semantic compare using priceSeries                    |
        |                                                         |
        +-- degraded/unchanged -> no Context republish            |
        |                         60-minute cooldown               |
        |                                                         |
        +-- extended/changed ---> publish Context once -----------+
                                   clear cooldown
                                   normal downstream recalculation
```

## Admission invariant

An event-driven PBTH fetch is admitted only when all are true:

```text
contractType == DYNAMIC
AND horizonHours < 12
AND cooldown is not active
```

Otherwise the event branch performs zero PBTH price-action calls.

## Semantic-change invariant

Republish the DYNAMIC Context only when at least one of these is true:

- valid slot count increases;
- effective horizon extends;
- one or more overlapping accepted price values changes materially.

An identical response must not fan out to Core/Planner/publication.

## Cooldown invariant

When an admitted event produces no semantic improvement or a degraded response:

- record the attempt/result;
- start a 60-minute event cooldown;
- repeated PBTH events during cooldown cause zero PBTH action calls;
- keep the normal 15-minute scheduled v0.10 route intact;
- no loop and no immediate retry.

A successful semantic update clears the cooldown.

## Current evidence motivating the rebase

On 2026-08-31 the live DYNAMIC path was manually refreshed and the Planner republished with only 21 dynamic 15-minute slots. PBTH device next-day summary capabilities were still `null`. This confirms that the website was reflecting the currently available PBTH horizon and provides a real short-horizon state in which the future event path can later be validated.

## Deployment gate

No Homey mutation is authorized by this rebase document. Before deployment:

1. update the scheduled v0.10 DYNAMIC context to include `priceSeries` and validate that downstream consumers remain unaffected;
2. provision exactly one `EM2_ContractPrice_EventRefresh_State` variable and capture its ID;
3. integrate the event branch into the current v0.10 FIXED+DYNAMIC topology, initially disabled/SHADOW;
4. validate `FIXED` and `horizon >= 12h` each produce zero event PBTH calls;
5. validate `<12h` admits at most one PBTH action per eligible event;
6. validate unchanged/degraded results do not republish Context and start cooldown;
7. validate extended/changed results publish Context once and cause the normal downstream Planner recalculation;
8. stop immediately on HTTP 429 and do not retry;
9. only after these tests may the event path be enabled.

## Result

Compatibility with the current architecture is **PASS WITH TWO IMPLEMENTATION BLOCKERS**: `priceSeries` must first be added to the scheduled DYNAMIC context and the single event-state variable must be provisioned. No Planner-side PBTH polling or faster schedule is required.
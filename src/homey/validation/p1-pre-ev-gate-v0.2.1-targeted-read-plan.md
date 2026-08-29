---
component: validation
flow: EM v2 | 80 Validation | P1 Pre-EV Gate v0.2
flow_id: 557ed7e8-9efe-4173-bc06-8e629214e172
candidate_version: v0.2.1 TARGETED-READ LOW-LOAD
status: candidate-not-deployed
verified: 2026-08-29
---

# P1 Pre-EV Gate v0.2.1 — targeted-read low-load plan

## Runtime evidence

A single targeted `get_advanced_flow` inspection on 2026-08-29 showed:

- flow ID `557ed7e8-9efe-4173-bc06-8e629214e172`;
- runtime name `EM v2 | 80 Validation | P1 Pre-EV Gate v0.2`;
- `enabled=false`;
- `broken=false`;
- trigger remains `EM2_Power_Intent` changed (`04b57041-dd7f-41f7-a00a-f023afb1ccee`);
- the HomeyScript currently calls `Homey.logic.getVariables()` and resolves both `EM2_Power_Intent` and `EM2_P1_PreEV_Gate` by name;
- no device reads, device writes, network calls or actuator cards are present in this Gate.

This runtime OFF state differs from the current `homey-api-load-map.md`, which still lists the flow as ON. The canonical load map should be corrected in the next load-map maintenance commit.

## Optimization target

Replace the collection-wide Logic enumeration with exactly two stable targeted reads:

```js
const IDS = {
  EM2_Power_Intent: '04b57041-dd7f-41f7-a00a-f023afb1ccee',
  EM2_P1_PreEV_Gate: '<bind stable Logic ID before deployment>'
};

const [intentVar, prevVar] = await Promise.all([
  Homey.logic.getVariable({ id: IDS.EM2_Power_Intent }),
  Homey.logic.getVariable({ id: IDS.EM2_P1_PreEV_Gate })
]);
```

The remainder of the v0.2 gate semantics must remain unchanged: `EM2_POWER_INTENT_V0.2` contract validation, SHADOW/read-only safety checks, EV/WW/battery invariants, duplicate-mutation detection, compact `EM2_P1_PRE_EV_GATE_V0.2` output, and no physical writes.

## Expected load effect

When enabled, each `EM2_Power_Intent` semantic event changes from one full Logic-variable enumeration to two targeted Logic reads plus at most one compact Gate output write. While the flow remains disabled, the immediate runtime load reduction is already maximal: zero executions from this Gate.

## Deployment gate

Do not deploy or enable v0.2.1 until all of the following are true:

1. the stable Logic ID of `EM2_P1_PreEV_Gate` is bound using one controlled autocomplete/read operation;
2. the exact current v0.2 validation/output semantics are preserved byte-for-byte where contract-sensitive;
3. Homey is not rate-limited at deployment time;
4. deployment keeps the flow disabled unless there is an explicit decision to re-enable runtime-health validation;
5. if later enabled, perform one SHADOW/manual start-smoke only; stop immediately on `Too many requests` and do not retry.

## Safety

This optimization is Logic-only. It must not enable Watchdog, LIVE EV control, Easee writes, device writes, network publication or broader polling.

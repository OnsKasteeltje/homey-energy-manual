# Core v0.10.18 — semantic EV control signal candidate

Status: **IMPLEMENTATION-READY / NOT DEPLOYED**

Date: 2026-08-29

Baseline: active Homey Core v0.10.17 plus the semantic-fan-out helper captured in `core-v0.10.16-runtime.patch.md` and the Planner Input delta in `core-v0.10.17-planner-input.patch.md`.

## Purpose

Add one narrow Core-owned EV control commit signal, `EM2_Control_EV`, so Tesla-only semantic changes can later wake Power Intent without restoring `EM2_Public_State` as a control bus.

This step intentionally adds **only the producer**. Power Intent v0.2.3 remains unchanged during the initial soak; therefore this Core change cannot yet cause any new Adapter/Gate/Actuator fan-out.

## Semantic suppression

Extend the active semantic JSON set with `EM2_Control_EV`:

```js
const SEMANTIC_JSON_VARS=new Set([
  'EM2_State',
  'EM2_Decision',
  'EM2_Shadow',
  'EM2_Control_WW',
  'EM2_Publisher_Status',
  'EM2_Planner_Input',
  'EM2_Control_EV'
]);
```

The existing `VOLATILE_KEYS` set already excludes `generatedAt` and other freshness-only fields from semantic equality. No change to the generic `set()` helper is required.

## EV semantic mapping

Create the EV control payload after the authoritative `state`, `decision` and WW-control objects for the current Core run have been calculated, and publish it **after** the normal State/Decision/WW-control writes.

Implementation helper:

```js
const decisionMode=String(
  decision?.decision ||
  decision?.mode ||
  decision?.action ||
  'HOLD'
).toUpperCase();

const evMode =
  decisionMode === 'TESLA_CHARGE_DEADLINE' ? 'DEADLINE' :
  decisionMode === 'TESLA_CHARGE_OPPORTUNITY' ? 'OPPORTUNITY' :
  decisionMode === 'TESLA_BUFFER_EXPORT' ? 'BUFFER_EXPORT' :
  'HOLD';

const chargerAvailable = Boolean(
  state?.tesla?.chargerAvailable ??
  state?.ev?.chargerAvailable ??
  state?.tesla?.plugged ??
  state?.ev?.plugged ??
  false
);

const deadlineActive = Boolean(
  state?.tesla?.deadline?.active ??
  state?.ev?.deadline?.active ??
  false
);

const flexW = Math.max(0, Number(
  decision?.flexExportBudgetW ??
  decision?.ev?.targetW ??
  decision?.targets?.ev?.target_W ??
  0
) || 0);

// Semantic bucket only. Final W→A translation remains EV Adapter ownership.
// 690 W corresponds to 1 A at fixed 3×230 V; 4140 W is 3×6 A minimum.
const requestedPowerClass =
  evMode === 'HOLD' ? 0 :
  flexW < 4140 ? 1 :
  Math.min(16, Math.floor(flexW / 690));

const coreRevision = Number(
  state?.revision ??
  decision?.sourceRevision ??
  decision?.revision ??
  0
) || 0;

const evControl={
  schema:'EM2_CONTROL_EV_V0.1',
  semanticRevision: coreRevision,
  coreRevision,
  mode: evMode,
  requestedPowerClass,
  chargerAvailable,
  deadlineActive,
  safetyState: chargerAvailable ? 'OK' : 'BLOCKED',
  generatedAt: now.toISOString()
};
```

The runtime implementation MUST map the field reads above to the exact existing v0.10.17 object shape seen in Homey. The fallback chain is deliberately defensive for source preparation; do not invent a parallel source of truth if the active object shape differs.

## Publication ordering

Required ordering inside one Core run:

```text
calculate state / decision / WW semantics
        ↓
write EM2_State
        ↓
write EM2_Decision
        ↓
write EM2_Control_WW
        ↓
write EM2_Control_EV   ← new post-control commit signal
        ↓
other observability/publication outputs
```

Candidate write:

```js
await set('EM2_Control_EV','string',JSON.stringify(evControl));
```

Because `EM2_Control_EV` is in `SEMANTIC_JSON_VARS`, a Core tick that changes only timestamps/freshness will not rewrite it.

## First-run provisioning

`EM2_Control_EV` does not exist in the current runtime baseline. On the first controlled Core v0.10.18 run, Core may create it through the existing `set()` helper because Core already owns the one broad Logic collection read and its in-memory `byName` map.

No extra `getVariables()` or `getDevices()` call is permitted for provisioning.

After the first successful run, capture the stable Logic variable ID for the later Power Intent v0.2.4 trigger binding.

## Load impact

Incremental steady-state cost of this Core producer:

- broad `Homey.devices.getDevices()` reads: **+0/hour**;
- broad `Homey.logic.getVariables()` reads: **+0/hour**;
- recurring pollers: **+0**;
- external HTTP/GitHub calls: **+0/hour**;
- physical device writes: **+0**;
- Logic writes: **only when EV control semantics materially change**.

A first-run variable creation is a one-time provisioning action and not recurring load.

## Safety boundary

This version is intentionally producer-only:

- Power Intent remains v0.2.3 during soak;
- no trigger is added to Power Intent yet;
- EV Adapter, EV Gate and EV Actuator remain unchanged;
- `EM2_Public_State` remains excluded from the control path;
- Easee receives no new write as a consequence of this patch;
- existing fail-closed and LIVE ownership rules remain unchanged.

## Deployment / smoke gate

Deploy only when exact Homey flow access is available.

For the controlled deployment:

1. exact-ID read Core `227f8d3b-7551-46dd-837d-1b8c69add824`;
2. apply the producer-only delta while preserving all v0.10.17 functional logic;
3. run one Core smoke only;
4. verify `enabled=true`, `broken=false`;
5. verify `EM2_Control_EV` was created/updated without any new broad read;
6. do **not** manually start EV Actuator;
7. stop immediately on any `Too many requests` / 429.

## Soak acceptance

Before Power Intent v0.2.4 is deployed, observe natural Core cycles and record:

- number of Core ticks;
- number of `EM2_Control_EV` semantic writes;
- Tesla decision transitions represented by those writes;
- no writes caused only by timestamp/freshness changes;
- no Homey 429;
- no unintended downstream control wake-up.

PASS requires at least one natural unchanged-semantic Core tick producing no EV-control rewrite, plus one natural EV-semantic change producing exactly one EV-control rewrite when such a change occurs during the soak window.

## Rollback

Rollback is low risk because no production consumer exists yet:

- restore Core v0.10.17;
- leave `EM2_Control_EV` orphaned if already provisioned;
- do not delete the variable during incident recovery;
- Power Intent v0.2.3 continues its current WW-only trigger behavior until the separate v0.2.4 promotion.

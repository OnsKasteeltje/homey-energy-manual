# Planner Shadow publisher v0.5 — daily slot history prep

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Baseline: `src/homey/publisher/planner-shadow-publisher-v0.4.js`.

## Problem

`docs/data/energy-planner-shadow.json` is rolling. Once a quarter has passed, the Planner decision that was active for that quarter disappears from the current 24-hour snapshot. That prevents a deterministic realized-vs-plan comparison later in the day.

Git commit history can recover old snapshots retrospectively, but that is an audit fallback, not the desired runtime observability contract.

## Proposed companion publication

Maintain:

`docs/data/energy-planner-slot-history.json`

with compact records for the current slot at each successful Planner Shadow publication.

Schema:

```json
{
  "schema": "EM2_PLANNER_SLOT_HISTORY_V0.1",
  "dateLocal": "2026-08-31",
  "slotMinutes": 15,
  "records": [
    {
      "generatedAt": "...",
      "sourceRevision": 3750,
      "start": "...",
      "end": "...",
      "warmWater": "HOLD",
      "WW_target_W": null,
      "pvForecastW": 0,
      "baseLoadForecastW": 887,
      "pvSurplusBeforeFlexW": 0,
      "price_eur_kwh": 0.1984,
      "priceQuality": "GOOD",
      "allocationReason": null
    }
  ]
}
```

## No extra Homey reads

The v0.4 publisher already reads the complete canonical Planner snapshot. Derive the compact current-slot record from that in-memory snapshot. Do not add any `Homey.logic.getVariable()` call for this feature.

Current-slot selection:

```js
const actions=Array.isArray(plan?.plan?.actions)?plan.plan.actions:[];
const current=actions[0]??null;
```

The Planner horizon is quarter-aligned; the first action is the decision for the current quarter at publication time.

## Retention / idempotency

- Keep only the local calendar day represented by the current record.
- Key records by `start`.
- If a later Planner run revises the same slot before it ends, replace that slot record with the latest decision and retain `firstGeneratedAt` plus `lastGeneratedAt` if change history is needed.
- Maximum 96 records/day.
- Do not append duplicate records for the same `start` + `sourceRevision`.

## Load impact

- +0 Homey Logic reads.
- +0 device reads.
- +0 physical writes.
- +0 trigger events.
- One additional compact GitHub file GET/PUT on an already-triggered Planner publication; this can later be combined with the rolling snapshot publication if desired.

## Required fields for WW validation

Keep enough information to compare:

`Planner slot -> Power Intent -> adapter output -> realized measurement`.

For v0.4.9, retain `warmWater`. Once Planner v0.5 numeric targets are introduced, add `WW_target_W` as canonical and retain `warmWater` only as a compatibility label.

## Safety

Observability only. No plan mutation and no adapter/device invocation.

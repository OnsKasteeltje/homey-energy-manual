# Planner Shadow Publisher v0.4 smoke — 2026-08-28

Result: **PASS**

Migrated Homey flow:
- `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD`
- Flow ID: `5b3b80fe-96d1-406d-91ef-cf75a4e65d45`

## Controlled event-chain smoke

A one-shot test enabled Planner v0.4.4, started it once, and allowed its fresh `EM2_Energy_Planner_Snapshot` update to trigger Publisher v0.4. The publisher was not manually started, so this validates the new event trigger.

Observed public artifact `docs/data/energy-planner-shadow.json`:
- schema: `EM2_PLANNER_SHADOW_PUBLISH_V0.4`
- publishedAt: `2026-08-28T20:53:12.017Z`
- generatedAt: `2026-08-28T20:53:09.744Z`
- sourceRevision: `3011`
- plan schema: `EM2_ENERGY_PLAN_24H_V0.4.4`
- plan generatedAt matches publisher generatedAt
- plan controlMode: `SHADOW`
- plan readOnly: `true`
- plan physicalWritePerformed: `false`
- observabilityOnly: `true`
- controlImpact: `NONE`

## Load characteristics

Publisher v0.4 uses four targeted `Homey.logic.getVariable({id})` reads in parallel and no `Homey.logic.getVariables()` collection scan. It is idempotent on `generatedAt|sourceRevision`, uses the cached GitHub SHA, and performs one GitHub PUT in steady state (GET only on cache miss/conflict).

## Safety / cleanup

- No physical actuator writes were introduced or intentionally triggered.
- No Homey `Too many requests` occurred during migration, event-chain smoke, verification, or cleanup.
- Planner returned to `enabled=false`, `broken=false`.
- Planner Shadow Publisher returned to `enabled=false`, `broken=false`.
- Temporary event-smoke driver was renamed `[DONE]` and disabled.

Migration gate: **PASS — next flow migration may proceed.**

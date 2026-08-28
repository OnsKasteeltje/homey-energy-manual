# Planner v0.4.4 LOW-LOAD smoke — 2026-08-28

Result: **PASS (Planner flow boundary)**

Flow: `EM v2 | 45 Planner | 24h Energy Plan v0.4.4 SHADOW LOW-LOAD`  
Homey Advanced Flow ID: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`

## Change under test

- Canonical targeted input: `EM2_Planner_Input` (`39c7c169-34d7-4e14-a27b-520aca255032`)
- Canonical targeted output: `EM2_Energy_Planner_Snapshot` (`b9f1232c-ac01-45fa-9453-ef95d998b138`)
- Planner runtime performs no `Homey.logic.getVariables()` collection scan.
- Planner runtime performs one targeted `Homey.logic.getVariable({id})` and one targeted `Homey.logic.updateVariable({id,...})`.
- Legacy `EM2_Energy_Plan_24h` and `EM2_Energy_Planner_Status` are no longer written by Planner v0.4.4.
- No physical actuator writes are present.

## Controlled smoke

1. Planner v0.4.4 was deployed to the existing Planner flow and enabled only for the controlled smoke.
2. Exactly one manual Planner run was started.
3. A one-shot targeted snapshot validator waited 12 seconds, then read only `EM2_Energy_Planner_Snapshot` by its fixed Logic ID.
4. Validation required:
   - snapshot schema `EM2_ENERGY_PLANNER_SNAPSHOT_V0.1`;
   - plan schema `EM2_ENERGY_PLAN_24H_V0.4.4`;
   - `controlMode === SHADOW`;
   - `readOnly === true`;
   - `physicalWritePerformed === false`;
   - status version `EM2_ENERGY_PLAN_24H_V0.4.4`;
   - `noActuatorWrites === true`;
   - exactly 96 plan actions.
5. Validator created the PASS marker `TEMP_PLANNER_V044_PASS_R3010_T20260828204830`.
6. Planner was returned to `enabled=false`, `broken=false` immediately after the smoke.
7. The one-shot validator was also disabled.
8. No Homey `Too many requests` response occurred during deploy, Planner run, validation, or shutdown verification.

## Result

**PASS** for the Planner flow boundary: `EM2_Planner_Input -> Planner v0.4.4 -> EM2_Energy_Planner_Snapshot`.

The downstream Planner Shadow Publisher remains a separate flow and was deliberately not modified before this PASS, preserving the project rule: one flow migration = one change-set = one targeted smoke = PASS before the next flow migration.

The next dependent migration may now update `EM v2 | 46 Publish | Planner Shadow v0.3 event-driven` to consume the canonical snapshot and remove its broad Logic scan. Its own smoke must prove `snapshot -> docs/data/energy-planner-shadow.json` publication exactly once before any later flow migration.

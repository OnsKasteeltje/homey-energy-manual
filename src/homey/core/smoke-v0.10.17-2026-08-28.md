# Core v0.10.17 targeted smoke — 2026-08-28

Result: **PASS**

Flow: `EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)`  
Homey Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`

## Observations

- Deployment to the existing Core Advanced Flow succeeded with `enabled=true`, `broken=false`, `triggerable=true`.
- One controlled manual Core start succeeded.
- The new canonical Logic variable `EM2_Planner_Input` was created by the Core single-reader path.
- Stable Homey Logic ID captured: `39c7c169-34d7-4e14-a27b-520aca255032`.
- No additional `Homey.logic.getVariables()` collection scan was introduced; the Planner-input snapshot is built from Core's already-loaded Logic collection and current in-memory WW state.
- `EM2_Planner_Input` is included in semantic JSON suppression, so timestamp-only differences do not create downstream Logic change events.
- No physical device/actuator write path was added.
- No `Too many requests` / Homey throttling error occurred during deployment, controlled start, or targeted variable-ID readback.
- Immediate GitHub public-state read still showed the prior published revision 2997; this is not a failure of this Core smoke because publication is independently cadence/throttle controlled and the purpose of this change-set is the canonical Planner input path. The Planner-input output itself was positively observed on Homey.

## Gate

Core v0.10.17 migration gate: **PASS**.

The next low-load step may proceed, but the Planner v0.4.4 migration itself still requires its own chain smoke PASS before any later EMS flow migration.

# WW v0.5 → Core → Power Intent compatibility gate

Status: **PREPARED / SHADOW-ONLY / NOT DEPLOYED**

## Why this gate exists

Planner v0.5.0 is live in SHADOW and publishes explicit per-slot `targets.wwTargetW` (0 or 1900 W), but the current Core WW policy still identifies its planner contract as `PLANNER_V0.4.9_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY`.

Current published runtime evidence on 2026-09-01 shows:

- Planner schema: `EM2_ENERGY_PLAN_24H_V0.5.0`
- `plannerFresh=true`
- `plannerCompatible=false`
- `plannerGridAllowed=false`
- `plannerPvConfirmed=false`

Therefore the strong physical WW result on 2026-09-01 must **not** be interpreted as v0.5 driving Core/Power Intent. Core is currently failing the planner compatibility gate and is falling back to its existing realtime/export logic.

## Required architecture

```text
Planner v0.5 SHADOW
  targets.wwTargetW = 0 | 1900
          ↓
Core WW compatibility + realtime safety gate
          ↓
EM2_Control_WW
          ↓
Power Intent P1 v0.2.4
          ↓
EM2_Power_Intent.targets.ww
          ↓
WW Power Adapter SHADOW
```

No direct Planner → actuator path is allowed.

## Minimal compatibility change

The next Core candidate should accept both the existing v0.4.9 slot schema and v0.5.0 **only when** the v0.5 current slot satisfies all of the following:

1. planner object is fresh under the existing Core freshness rule;
2. planner schema is exactly `EM2_ENERGY_PLAN_24H_V0.5.0`;
3. current slot belongs to `CURRENT_DAY`;
4. `targets.wwTargetW` is numeric and exactly `0` or `1900`;
5. `warmWater` is consistent with the numeric target (`HOLD` ↔ 0, planned WW ↔ 1900);
6. local WW mode, goal latch, 19:00 deadline, state freshness and realtime import/P1-export guards remain authoritative in Core;
7. Planner may request ON, but Core may always reject/delay it for safety; Planner may never override Core MUST-OFF conditions.

## Interpretation

For v0.5 the numeric target becomes the canonical Planner-side WW request:

- `wwTargetW=1900` → Planner requests boiler ON for that quarter;
- `wwTargetW=0` → Planner does not request boiler heating in that quarter.

The Core still owns realtime feasibility. In particular, a `PV_PREFERRED` slot should continue to require actual export when the existing Core policy requires it. A deadline/grid slot remains subject to the existing import-budget gate.

## Homey-load rule

This compatibility change must **not** add:

- a new trigger;
- a new poller;
- a device read;
- a Logic collection scan;
- an additional planner variable read if the current Core already reads the Planner snapshot;
- any physical write.

It is a parser/compatibility change inside the existing Core execution only.

## Validation before any Power Intent cut-over

A Core candidate is acceptable only when GitHub evidence demonstrates all of the following in SHADOW:

- `plannerCompatible=true` for v0.5;
- at a `wwTargetW=1900` PV slot with sufficient actual export, Core produces the expected WW ON intent;
- at a `wwTargetW=1900` slot without sufficient realtime safety budget, Core remains fail-closed / delays ON;
- `wwTargetW=0` never creates a new discretionary start;
- after `goalReachedToday=true`, Core remains HOLD/OFF regardless of future v0.5 forecast slots;
- after 19:00, Core remains MUST/HOLD as today;
- no new Homey reads, writes or triggers are introduced;
- Power Intent and WW Adapter remain SHADOW and `deviceWrites=false`.

## Do not do yet

- Do not enable the old WW Power Adapter runtime as-is: its captured v0.1 implementation uses `Homey.logic.getVariables()` and was disabled at capture.
- Do not let Power Intent read Planner directly as a shortcut.
- Do not bypass `EM2_Control_WW` or the existing Core safety state machine.
- Do not deploy a Core change until the exact current Core runtime source has been captured into GitHub and diffed.

## Next concrete step

Capture/recover the exact current Core runtime source and create a minimal v0.5-compatible SHADOW candidate whose diff is limited to Planner schema/slot parsing plus observability. Test offline first; only then consider one targeted Homey Core update.

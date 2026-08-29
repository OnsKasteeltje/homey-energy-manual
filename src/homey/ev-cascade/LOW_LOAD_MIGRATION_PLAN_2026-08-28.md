# EV cascade LOW-LOAD migration — closed 2026-08-29

Status: **ACTIVE RUNTIME MIGRATION COMPLETE**

## Scope

The active EV control cascade has been verified directly on Homey and no longer uses broad `Homey.logic.getVariables()` collection reads in its enabled control path.

```text
EM2_Control_WW
  -> Power Intent
      -> EM2_Power_Intent
          -> P1 Pre-EV Gate
          -> EV Power Adapter
          -> EV Adapter Gate (+2 s)
               -> EM2_EV_Adapter_Gate
                    -> EV Power Actuator
```

## Verified runtime

| Stage | Flow ID | Runtime | Enabled | Logic access |
|---|---|---|---:|---|
| Power Intent | `19d9d8a6-ec32-4639-be5e-71e9f034d31b` | `P1 v0.2.3 TARGETED-READ LOW-LOAD` | yes | 4 targeted `getVariable(id)` reads |
| P1 Pre-EV Gate | `557ed7e8-9efe-4173-bc06-8e629214e172` | `v0.2.1 TARGETED-READ` | yes | 2 targeted reads |
| EV Power Adapter | `953e9b18-3576-4557-b940-ed4a64eb2516` | `v0.1.1 TARGETED-READ SHADOW` | yes | 4 targeted reads |
| EV Adapter Gate | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | `v0.2.1 TARGETED-READ` | yes | 4 targeted reads |
| EV Power Actuator | `fea23193-a03f-49dd-9780-7e72ee48747d` | `v0.2.2 TARGETED-READ LIVE OWNERSHIP` | yes | 6 targeted reads; zero device reads/writes while LIVE=false |

All five enabled stages are event-driven and preserve the existing revision guards, schema checks, fail-closed behavior and SHADOW/LIVE ownership boundaries.

## Load result

The former upstream chain performed approximately four full Logic collection enumerations per normal Core revision. At a five-minute Core cadence that was approximately **48 full Logic enumerations/hour** before actuator/status fan-out.

That collection-enumeration load is now **0/hour in the enabled EV control cascade**. Individual targeted reads remain bounded by declared dependencies.

The LIVE actuator may enumerate Homey devices only when `EM2_EV_Actuator_Live_Enabled=true`; while LIVE=false it performs no charger device read or physical write.

## Observability flow

`EM v2 | 81 Observability | EV Control Status v0.1`

Flow ID: `f6edba38-ddf1-45e5-890e-c183aa2055d5`

Runtime status on verification: **disabled**.

Its legacy code still contains one broad `Homey.logic.getVariables()` per event plus GitHub publication. Because the flow is disabled it contributes **zero current runtime load** and is deliberately excluded from the active control-cascade completion gate. It should be migrated to targeted reads before any future re-enable.

## Safety confirmation

- no Insights calls in the active EV path;
- no independent polling clock added;
- no `getVariables()` in the enabled EV control cascade;
- no device access in Power Intent, Gates or Adapter;
- actuator LIVE=false path has zero device reads/writes;
- positive LIVE writes still require exact Gate/intent/adapter/state revision coherence;
- manual actuator start first normalizes LIVE to false;
- EV Power Adapter remains SHADOW and cannot physically actuate the charger.

## Completion gate

**PASS — active EV cascade LOW-LOAD migration complete.**

Remaining follow-up is separate from this migration: convert the disabled EV Control Status observability publisher to targeted reads before re-enabling it, and continue the wider Homey API-load reduction programme on the remaining non-EV flows.

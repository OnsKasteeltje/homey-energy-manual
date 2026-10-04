# Heating Pi -> Homey control-contract V0.1 SHADOW

**Status:** SHADOW proof complete; automatic publisher parked  
**Physical writes:** forbidden  
**Planner authority:** SHADOW_ONLY  
**Homey role:** translation, validation and targeted readback only

## Purpose

This increment crosses the Pi -> Homey boundary for Heating without creating a
Honeywell actuator. It transports the already-guarded V0.5 result to a dedicated
Homey Logic bus and proves that Homey can translate and validate it at the edge.

```text
Heating Control Gate V0.5 SHADOW
        |
        v
Pi publisher (commissioning/manual only; timer disabled)
EMS_HEATING_CONTROL_INTENT_V0.1
        |
        v
EM2_Heating_Control_Intent
        |
        v
Heating Adapter v0.1 SHADOW
        |
        v
EM2_Heating_Control_Adapter
        |
        v
Heating Gate v0.1 SHADOW
        |
        +--> targeted Honeywell thermostat READS for non-HOLD commands
        |
       -X-
no actuator / no Honeywell capability write
```

The intent is deliberately separate from production `EM2_POWER_INTENT_V0.2`.
Heating V0.4/V0.5 still use shadow arbitration; the active Dynamic Pi Planner
does not yet expose an authoritative production Heating grant. Therefore this
chain may not be connected to a physical writer.

## Contract

Pi schema: `EMS_HEATING_CONTROL_INTENT_V0.1`.

The contract contains four canonical preheat rooms, the V0.5 semantic action,
target when applicable, Honeywell baseline/future target, schedule change time,
opportunity ID and an idempotent semantic `controlRevision`.

V0.5 actions map as follows:

```text
HOLD                    -> HOLD
WOULD_SET_TEMP          -> SET_TEMP
WOULD_KEEP_TEMP         -> KEEP_TEMP
WOULD_RESET_TO_SCHEDULE -> RESET_TO_SCHEDULE
```

Every contract and downstream command retains `physicalWrite=false`.
`liveExecutionAllowed=false` is hard at intent, adapter and gate.

## Edge readback

The Gate performs no device read for HOLD. For SET/KEEP/RESET it performs one
targeted read of the mapped Honeywell thermostat and records current
`target_temperature` and `measure_temperature` where available. This proves
device identity/capability visibility only. It does **not** prove that EMS owns
an override, because no actuator write or acknowledgement exists yet.

Canonical thermostat IDs:

- woonkamer: `6a79bb86-8c02-43db-be22-6f51e01efc6d`
- eetkamer: `dd7ef4a3-ed9f-4e4d-92bb-090502068421`
- keuken: `b7aec05b-953f-41e1-a7b4-ad09c9bf911e`
- serre: `13625cb2-8fb5-4466-a21f-7addd8d72a88`

## Commissioning and Homey load

The Pi -> Homey SHADOW boundary has been proven end-to-end. The pinned Logic
variables and Advanced Flows remain in Homey for reference and future promotion,
but there is currently no production Heating grant and no Honeywell actuator.
Therefore the automatic publisher timer MUST remain disabled.

`--apply` creates or resyncs the pinned SHADOW Logic/Flow objects and leaves
the publisher timer disabled. `--resume` may be used only as a one-shot
commissioning validation: it performs paced targeted readback, one SHADOW
publish, validates identical revision plus all no-write/live-block invariants,
and leaves the publisher timer disabled afterwards. `--runtime-only` refreshes
Pi publisher source/systemd only and also leaves the timer disabled.

This is deliberate KISS behavior. V0.3 -> Flex -> V0.4 -> V0.5 continues
locally on the Pi. Homey receives no recurring Heating SHADOW traffic until an
authoritative production Dynamic Pi Planner Heating grant and a guarded
Honeywell actuator contract both exist. No Homey retry/cooldown mechanism is
needed for normal operation while the timer is parked; any manual publisher
failure remains fail-closed.

The active local SHADOW minute chain is phase-locked to prevent false ordering
failures: V0.3 runs at second `:00` on its five-minute refresh minute, Flex
Priority at `:10`, V0.4 at `:20`, and V0.5 at `:30`. The historical
Homey publisher slot remains defined at `:35` but its timer is disabled.
Flex MUST use calendar phase `:10`; relative `OnUnitActiveSec` scheduling is
forbidden because it can drift beyond the fresh V0.3 snapshot and race V0.4. The targeted cadence
installer is `deploy/install/install_heating_shadow_cadence_v0_1.sh`; it
replaces timer unit files and restarts only timers that were already active,
without changing enabled state or issuing a Homey/device command.

## Continuation checkpoint — 2026-10-04

Stable handoff marker: `NEXT_HEATING_STEP_PRODUCTION_DYNAMIC_PI_PLANNER_GRANT`.

Do **not** restart Heating work by rebuilding the Pi -> Homey SHADOW transport.
That proof is complete. The installed Intent -> Adapter -> Gate objects, pinned
room IDs, no-write guards and one-shot `--resume` path are retained as
commissioning evidence. The recurring publisher is deliberately parked.

The next implementation step is the production Dynamic Pi Planner Heating grant.
Start there and preserve these already-proven boundaries:

- P1/current grid exchange remains the realtime authority for actual Heating
  permission; forecast opportunity alone is never a realtime grant.
- Honeywell remains comfort/schedule authority. Heating may only advance an
  already scheduled future `UP`, never create new comfort demand, never exceed
  the future Honeywell target and never intentionally create grid import.
- V0.3 eligibility/safety, Flex arbitration, V0.4 stateful <=0.5 C progression
  and V0.5 control-boundary checks are inputs/guards to reuse, not replace.
- Missing/stale/ambiguous P1 or planner inputs fail closed.
- Heating must join the existing production Dynamic Pi Planner allocation with
  EV and WW; it must not introduce a separate PV pot or second planner.
- The production grant must be explicit, fresh/revisioned and independently
  distinguish forecast opportunity from realtime permission.
- Keep the Homey publisher timer disabled while the grant is still SHADOW or
  absent.

Only after that production grant has been implemented and validated should
Heating cross into LIVE actuation. At that point reuse the proven Homey
Intent/Adapter/Gate mapping and add exactly one Honeywell writer. The actuator
must use a temporary override bounded to the original Honeywell `UP`, prove
write acknowledgement plus Honeywell readback/ownership, and provide explicit
reset/watchdog rollback. Begin with a bounded canary; do not infer physical
ownership from the existing SHADOW chain.

Already solved and not a reason to reopen this phase unless new evidence
contradicts it: V0.3/Flex/V0.4/V0.5 cadence ordering, Pi -> Homey SHADOW
transport shape, pinned thermostat mapping, no-write/live-block guards,
commissioning pacing, CLI notifier behavior and Homey 429 suppression. The
latter two are retained as defensive code only; normal runtime does not depend
on them because the publisher is parked.

## LIVE blockers

Physical Heating control remains blocked until both are separately delivered and
validated:

1. an authoritative Heating grant inside the production Dynamic Pi Planner;
2. a sole Homey Honeywell actuator with idempotent temporary override,
   acknowledgement/readback ownership proof and bounded reset-to-schedule
   rollback.

Passing this SHADOW Gate is not LIVE approval.

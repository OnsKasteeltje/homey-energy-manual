# Heating Pi -> Homey control-contract V0.1 SHADOW

**Status:** commissioning  
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
Pi publisher :35
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

The installer is
`services/pi/commissioning/install_heating_homey_shadow_chain_v0_1.py`.
It is DRY-RUN by default. `--apply` creates or updates only the pinned
Logic/Advanced Flow objects, installs the local publisher runtime and explicitly
keeps the publisher timer disabled. Runtime activation is a separate
`--resume` step.

First commissioning performs no bulk Logic/Advanced Flow discovery. The live
Homey collection response can be truncated, so first install bootstraps only
the dedicated source-controlled SHADOW objects. Each create is preceded by an
atomic host-local `pendingOperation` marker; the returned ID is then verified
with targeted readback, persisted in
`/home/jeroen/ems/data/heating-control-homey-shadow-config.json`, and the
marker is cleared. An ambiguous interrupted create is therefore a hard stop
requiring reconciliation rather than a duplicate-prone retry. Normal runtime
thereafter uses targeted IDs only. Homey 429 is also a hard stop with no write
retry.

A READY installation is activated only through `--resume`. Resume performs
paced targeted readback of the three pinned Logic IDs and two pinned Advanced
Flow IDs, never bulk discovery. It then refreshes V0.5, performs exactly one
SHADOW intent publish, waits for the event-driven Adapter/Gate chain and reads
Intent, Adapter and Gate back with pacing. Promotion requires one identical
`controlRevision`, Intent `valid=true/status=OK`, Adapter `status=PASS`,
Gate `finalStatus=PASS/errors=[]`, and `deviceWrites=false`,
`physicalWriteAllowed=false` and top-level `liveExecutionAllowed=false` at
all three layers. Every command must still carry `physicalWrite=false`.

The publisher timer is enabled only after all resume checks pass. A 429,
revision mismatch, stale/fail-closed intent or any write-boundary mismatch stops
resume with the timer disabled. Successful resume records `validatedAt`,
`lastValidatedRevision` and `publisherTimerEnabled=true` in the host-local
config.

When the source-controlled Adapter/Gate changes after first commissioning, rerun
`--apply` as a READY resync before `--resume`. Existing Logic variables and
Advanced Flows are addressed only by their pinned IDs; their readbacks are
paced, any changed flow source is updated in place, and no new object is created
while the READY metadata is complete. The resync forces the publisher timer off,
sets `publisherTimerEnabled=false`, and clears `validatedAt` plus
`lastValidatedRevision`; this invalidates the previous activation proof until a
new successful `--resume`.

The Pi publisher runs at `:35`, after V0.5 at `:30`. It writes only the
dedicated intent Logic variable. Homey Adapter/Gate execution is event-driven by
Logic changes.

## LIVE blockers

Physical Heating control remains blocked until both are separately delivered and
validated:

1. an authoritative Heating grant inside the production Dynamic Pi Planner;
2. a sole Homey Honeywell actuator with idempotent temporary override,
   acknowledgement/readback ownership proof and bounded reset-to-schedule
   rollback.

Passing this SHADOW Gate is not LIVE approval.

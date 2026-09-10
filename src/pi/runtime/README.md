# HEMS Pi runtime

Status: **DEPLOYED / SHADOW_READ_ONLY / NO PHYSICAL PLANNER WRITES**

The Raspberry Pi 5 now hosts active EMS read-only/shadow services, including forecast acquisition, history/data preparation and planner execution. Physical actuator ownership has not been transferred to the Pi planner.

## Operational source-of-truth

For planner components already migrated to the Pi, `/home/jeroen/ems/runtime/planner/...` is the operational source of truth.

Planner changes are made and tested on the Pi first. After a successful shadow/smoke validation, the accepted source is synchronized to GitHub under `src/pi/ems-runtime/planner/...` and committed. A `git pull` into `/home/jeroen/ems/repo/homey-energy-manual` does not by itself deploy planner code into the active runtime directory.

GitHub remains the versioned repository, audit trail, documentation source and publication destination for generated observability snapshots.

## Current runtime responsibilities

The Pi currently provides, among other read-only/shadow responsibilities:

- weather, price and PV forecast acquisition;
- base-load/history preparation;
- warm-water planning inputs and shadow planning;
- quarter-hour Planner shadow execution;
- Dynamic Pi Planner shadow execution;
- publication of Planner snapshots to `docs/data/`;
- local status/observability services.

The Dynamic Pi Planner remains `PURE_SHADOW`: it produces plans and observability output but performs no physical device writes.

## Safety boundaries

- No Pi planner actuator ownership yet.
- No direct EV or WW physical writes from the Pi planner.
- Exactly one automatic writer may own each physical actuator during any future cutover.
- Easee Equalizer remains the independent hard EV load-balancing layer.
- Quatt remains observe-only unless separately validated control is introduced.
- Victron/DESS remains the intended primary future battery optimizer.
- Planner cutover requires explicit validation, rollback and ownership transfer.

## Runtime versus repository

There are two distinct trees on the Pi:

```text
/home/jeroen/ems/runtime/...                    active runtime
/home/jeroen/ems/repo/homey-energy-manual/...  Git checkout
```

They must not be treated as automatically synchronized. Planner deployment and repository synchronization are explicit operations.

The repository copies under `src/pi/ems-runtime/...` represent the last accepted/versioned Pi runtime state. Generated snapshots under `docs/data/` are runtime observability artifacts, not executable planner source.

## Service model

The installed Pi uses native systemd services/timers for the operational EMS chain. In particular, `ems-pv-forecast.service` is a oneshot pipeline that runs forecast/model/planner builders and publishes the resulting shadow planner snapshots.

A service being `inactive (dead)` after a successful run is normal for a `Type=oneshot` service. Success is determined by the individual process exit codes and the final `Finished ...` status.

## Current validation state

The Dynamic Pi Planner is running in shadow mode and publishing a 96-slot / 24-hour plan. Current EV opportunity logic uses PV windows rather than the legacy fixed instantaneous start threshold. Physical cutover remains a separate future step and must not be inferred from successful shadow publication.

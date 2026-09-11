# CURRENT EMS STATE

> **Canonical current-state document** for the Raspberry Pi / Homey EMS.
>
> This file describes the intended current operational architecture and logic. Architecture-sensitive runtime, planner, systemd, contract-policy and Homey/Pi responsibility changes must update this document in the same release range.

**Status date:** 2026-09-11  
**Repository:** `OnsKasteeltje/homey-energy-manual`  
**Primary runtime host:** Raspberry Pi `ems-pi`

## 1. Source of truth

- GitHub `main` is authoritative for Pi runtime source, deployment definitions and architecture documentation.
- Deployed runtime: `/home/jeroen/ems/runtime/`.
- Pi repository checkout: `/home/jeroen/ems/repo/homey-energy-manual`.
- SQLite `/home/jeroen/ems/data/ems-history.sqlite` is the single operational historical database.
- JSON under `/home/jeroen/ems/data/` and `docs/data/` is derived state, cache or publication output.

## 2. Control architecture

The intended production responsibility split is:

```text
Forecasts + history + live state + contract policy
                    ↓
        Pi hardened dynamic planner
                    ↓
          Pi current control command
                    ↓
       Pi → Homey intent publisher
                    ↓
         Homey executor / safety layer
                    ↓
            EV / boiler actuators
```

The Pi is the sole planner authority. Homey is the executor and local safety layer; Homey must not run a competing production planner.

Machine-readable authority is defined in `planner/control-authority.json` and requires:

- `plannerOwner = PI`;
- `executor = HOMEY`;
- `executionEnabled = true`;
- `legacyHomeyPlannerAuthority = false`;
- fixed ENGIE production contract;
- fail-closed behavior on stale, invalid or incoherent plans.

The planner itself remains read-only with respect to devices. Physical writes remain isolated in Homey actuator flows.

## 3. Contract policy

The production EMS is tied to the fixed three-year ENGIE contract.

Required invariants:

- `productionContractMode = FIXED`;
- `productionContractId = ENGIE_3Y_2026_2029`;
- `productionSupplier = ENGIE`;
- dynamic pricing is **disabled for production**;
- dynamic prices may only be used for shadow, analysis or replay while FIXED is active;
- automatic fallback to dynamic pricing is forbidden;
- automatic contract-mode switching is forbidden;
- missing or inconsistent configuration must **fail closed**.

Ordering rule:

**contract mode → permitted economic model → permitted price source → planner decision**

## 4. Pi planning chain

The regular `ems-pv-forecast.service` chain builds the planning inputs and plans in this order:

1. PV forecast;
2. clean base-load history;
3. base-load forecast;
4. warm-water input;
5. warm-water plan;
6. WW forecast import;
7. quarter-hour shadow plan;
8. hardened dynamic planner v0.3;
9. website shadow representations;
10. publication artifacts.

`ems-pv-forecast.service` is `Type=oneshot`; `inactive (dead)` after a successful run is normal.

The hardened dynamic plan schema is `EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3` and includes:

- 96 quarter-hour slots;
- `plannerOwner = PI`;
- fixed ENGIE contract metadata;
- input freshness checks;
- `validUntil`;
- WW comfort feasibility;
- Tesla deadline feasibility when active;
- fail-closed execution metadata.

## 5. Current control endpoint

The Pi status API exposes:

`GET /control/current`

A successful response uses schema `EMS_PI_CONTROL_COMMAND_V0.1` and contains only the command for the quarter-hour slot containing the current UTC time.

Current-slot semantics are authoritative and deterministic:

- slot start comes from `slot_start_utc`;
- slot end is `slot_end_utc` when explicitly present;
- for planner versions that omit `slot_end_utc`, the executor bridge derives slot end as exactly `slot_start_utc + 15 minutes`;
- a slot is current when `start <= now < end`;
- command validity is bounded by both planner `validUntil` and slot end.

The endpoint must fail closed with zero/off targets when any of the following is invalid:

- control-authority policy;
- planner schema or ownership;
- fixed-contract invariant;
- planner input freshness;
- planner `validUntil`;
- current-slot resolution.

A fail-closed response must never be interpreted as permission to run an opportunistic actuator action.

## 6. Tesla

Tesla charging remains split into planning and execution.

Pi planning:

- opportunity charging uses residual PV after WW reservation;
- stable minimum is modelled at 3×6 A;
- 3×7 A is an actuator kickstart, not an economic threshold;
- opportunity windows require at least 30 minutes and at least 50% PV coverage at stable 6 A;
- explicit deadline charging is a hard requirement and may use grid energy when necessary to meet the deadline.

Homey execution:

- validates `EM2_POWER_INTENT_V0.2` through EV adapter and validation gate;
- enforces freshness, schema, revision and charger-health constraints;
- controls Easee session start/resume and current;
- fails closed to 0 A on invalid/stale control input.

## 7. Warm water

WW comfort is a hard constraint above optimization.

Pi planning:

- schedules remaining required heating before the hard 19:00 deadline;
- prefers useful PV periods;
- may use shoulders of a PV window when a connected Tesla can better absorb the central peak;
- does not schedule unnecessary repeat heating after the daily goal is reached.

Homey execution:

- remains the sole boiler physical writer;
- validates adapter/gate/freshness/mode before a physical write;
- preserves local safety and manual source-mode controls.

## 8. Homey/Pi cutover boundary

Production intent is pushed from the Pi to the existing Homey compatibility bus by:

`homey-deploy/publish_pi_control_intent.py`

The publisher:

- reads the local Pi `/control/current` endpoint;
- performs one Homey read per run to obtain the current `EM2_State` revision required by the downstream exact-revision safety contract;
- validates PI ownership and FIXED ENGIE control metadata;
- maps the current Pi command to `EM2_POWER_INTENT_V0.2`;
- suppresses the Homey write when the semantic command plus source revision is unchanged;
- writes only the Homey Logic `EM2_Power_Intent` variable when an update is required;
- performs no device writes itself;
- uses bounded retry/backoff only for Homey `Too many requests` responses;
- fails closed on any non-rate-limit Homey error or unavailable Pi control command;
- relies on the existing Homey EV/WW adapters, gates and actuators for physical execution and local safety.

It is scheduled by `ems-pi-control-publish.timer` at one-minute cadence. The one-minute timer is intentionally more frequent than the 15-minute planner slot so a newly generated slot is propagated promptly, while semantic no-op suppression minimizes Homey writes. If Homey is temporarily rate limited, retries are delayed and bounded; the publisher never introduces a competing planner fallback.

After live cutover, legacy Homey planner/decision flows that independently decide WW or Tesla scheduling must be disabled.

The following classes remain enabled:

- state/input aggregation needed by Pi;
- device-health and validation gates;
- EV/WW adapters;
- EV/WW actuator flows;
- monitoring, history and diagnostics;
- local hard safety/failsafe flows that do not compete as planners.

The architecture must never run Pi planning authority and Homey planning authority simultaneously for the same actuator.

## 9. Monitoring and validation

Deployment pattern:

**inspect → minimal change → update architecture → architecture gate → deploy → validate → monitor**

The deployment script:

- runs the architecture gate;
- backs up runtime;
- deploys version-controlled runtime and systemd units;
- runs drift validation;
- reloads systemd;
- writes the deployed Git commit marker;
- does not restart services automatically.

`validate_cutover_gate.py` remains a structural planner validation tool. Live control additionally requires a valid `/control/current` response and a coherent Homey executor bridge.

## 10. Battery boundary

The planned battery architecture is Victron AC-coupled. When commissioned, Victron/DESS remains the primary real-time battery optimizer. Pi/Homey may provide forecasts, load intent and policy constraints but must not create a competing real-time battery optimizer.

## 11. Architecture enforcement

`scripts/ems_architecture_gate.sh` enforces at least:

- valid fixed-contract invariants;
- presence of this canonical architecture document;
- documentation of FIXED mode;
- dynamic-production prohibition;
- fail-closed behavior;
- same-release documentation updates for architecture-sensitive runtime/systemd/deployment changes.

A failed architecture gate is a hard deployment stop and must not be bypassed in normal operation.

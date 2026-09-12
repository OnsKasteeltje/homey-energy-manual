# CURRENT EMS STATE

> **Canonical current-state document** for the Raspberry Pi / Homey EMS.
>
> This file describes the intended current operational architecture and logic. Architecture-sensitive runtime, planner, systemd, contract-policy and Homey/Pi responsibility changes must update this document in the same release range.

**Status date:** 2026-09-12  
**Repository:** `OnsKasteeltje/homey-energy-manual`  
**Primary runtime host:** Raspberry Pi `ems-pi`

## 1. Source of truth

- GitHub `main` is authoritative for Pi runtime source, deployment definitions and architecture documentation.
- Deployed runtime: `/home/jeroen/ems/runtime/`.
- Pi repository checkout: `/home/jeroen/ems/repo/homey-energy-manual`.
- SQLite `/home/jeroen/ems/data/ems-history.sqlite` is the single operational historical database.
- JSON under `/home/jeroen/ems/data/` and `docs/data/` is derived state, cache or publication output.
- Homey Logic variable `EM2_Planner_Authority` is the sole runtime selector between Homey and Pi planner authority.

## 2. Control architecture

The current production responsibility split is:

```text
Forecasts + history + live state + contract policy
                    ↓
        Pi hardened dynamic planner
                    ↓
          Pi /control/current
                    ↓
 Homey PI Dynamic Planner Bridge v1.2.6
                    ↓
          EM2_Power_Intent
                    ↓
         Homey executor / safety layer
                    ↓
            EV / boiler actuators
```

The Pi is the active planner authority. Homey is the executor and local safety layer; Homey must not run a competing production planner while `EM2_Planner_Authority = PI`.

### Runtime authority selector

`EM2_Planner_Authority` is the **single actual HOMEY↔PI authority gate**.

- `PI` -> the Pi bridge may publish the Pi command into `EM2_Power_Intent`.
- `HOMEY` -> the Pi bridge remains inert and the guarded Homey producer may own the canonical intent.
- The active Pi bridge is `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]`.
- The guarded Homey producer remains available as rollback path.

`planner/control-authority.json` remains configuration and diagnostic context. Its historical `plannerOwner` / cutover-state fields do **not** form a second runtime authority gate and must not conflict with the Homey selector architecture.

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

The regular planning chain builds the planning inputs and plans in this order:

1. PV forecast;
2. clean base-load history;
3. base-load forecast;
4. warm-water input;
5. warm-water plan;
6. WW forecast import;
7. quarter-hour shadow plan;
8. hardened dynamic planner v0.3 with START6 / 15-minute EV policy;
9. website shadow representations;
10. publication artifacts.

The forecast chain is executed by `ems-forecast-chain.service` (`Type=oneshot`). `inactive (dead)` after a successful run is normal.

The hardened dynamic plan schema is `EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3` and includes:

- 96 quarter-hour action slots / 24-hour action horizon;
- `plannerOwner = PI` in the plan itself;
- fixed ENGIE contract metadata;
- input freshness checks;
- `validUntil`;
- WW comfort feasibility;
- Tesla deadline feasibility when active;
- fail-closed execution metadata;
- multiday lookahead for WW feasibility beyond the 24-hour action horizon.

## 5. Current control endpoint

The Pi status API exposes:

`GET /control/current`

A successful response uses schema `EMS_PI_CONTROL_COMMAND_V0.1`, returns `status = READY` and `readyForCutover = true`, and contains only the command for the quarter-hour slot containing the current UTC time.

Current-slot semantics are authoritative and deterministic:

- slot start comes from `slot_start_utc`;
- slot end is `slot_end_utc` when explicitly present;
- when omitted, slot end is derived as exactly `slot_start_utc + 15 minutes`;
- a slot is current when `start <= now < end`;
- command validity is bounded by both planner `validUntil` and slot end.

The endpoint is a **technical readiness and command endpoint**, not the runtime authority selector. It validates at least:

- control-policy schema/context;
- `executor = HOMEY` and execution enabled;
- Pi planner schema and ownership;
- fixed-contract invariant;
- planner input freshness;
- planner `validUntil`;
- current-slot resolution.

It does **not** require `planner/control-authority.json` to say `plannerOwner = PI` before it can report Pi readiness. That former dual-gate design created a circular cutover dependency and was removed on 2026-09-12.

Invalid or stale planner input still fails closed with zero/off targets.

## 6. Tesla

Tesla charging remains split into Pi planning and Homey execution.

Pi planning:

- opportunity charging uses residual PV after WW reservation;
- validated minimum start and stable run current are both 3×6 A;
- nominal minimum executable power is modelled as 4140 W at 3×230 V, while actual measured power may be slightly higher with real line voltage;
- opportunity start requires at least one profitable 15-minute planner slot;
- after start, every following 15-minute slot is evaluated independently and charging continues only while that slot remains a positive PV opportunity;
- short real-time anti-flap/session protection remains an executor concern and is separate from the 15-minute planner opportunity window;
- explicit deadline charging is a hard requirement and may use grid energy when necessary to meet the deadline;
- deadline-forced grid charging may **not** be introduced before the published `latest_start_at`; before `latest_start_at`, only normal PV-opportunity charging may create an EV target.

Homey execution:

- validates `EM2_POWER_INTENT_V0.2` through EV adapter and EV gate;
- enforces schema, source/state revision alignment, freshness and electrical/translation semantics;
- controls Easee session start/resume and current through the single EV actuator;
- uses START6/RUN6 semantics: 6 A may start a paused session and may maintain an already-running session;
- mapping contract is `FLOOR_3P230_START6_RUN6_FAIL_CLOSED`;
- fails closed to 0 A on invalid/stale control input.

Current Homey EV chain:

- adapter: `EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6`;
- gate: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6`;
- actuator: `EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION` when live-enabled.

### Easee device health

`EM2_EV_Telemetry_Health` is **observability-only for the EV gate** as of 2026-09-12.

The previous gate treated stale Easee capability timestamps as a hard control veto. Live testing showed that unchanged-but-valid paused telemetry could remain numerically stable long enough to be classified `STALE`, even while the device was reachable and controllable. That produced a false veto.

Health is still published for diagnostics, but `STALE` / `CONTROL_UNAVAILABLE` from the health observer alone cannot block a coherent positive EV command. The gate continues to enforce the independent intent/adapter/state, revision, electrical and translation safety checks.

## 7. Warm water

WW comfort is a hard constraint above optimization.

Pi planning:

- schedules remaining required heating before the hard 19:00 deadline;
- prefers useful PV periods;
- may use shoulders of a PV window when a connected Tesla can better absorb the central peak;
- does not schedule unnecessary repeat heating after the daily goal is reached.

Homey execution:

- remains the sole boiler physical writer;
- translates `targets.ww.target_on` through the WW adapter;
- requires an exact WW gate PASS with aligned revision and fresh intent before a physical write;
- preserves local source-mode and actuator safety controls.

## 8. Homey/Pi cutover boundary

The active production cutover path is the Homey Pi bridge, not a second autonomous planner publisher.

Active bridge:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]`

The bridge:

- is enabled but remains inert unless `EM2_Planner_Authority = PI`;
- reads `http://192.168.1.42:3100/control/current`;
- requires `readyForCutover = true` and a fresh valid Pi command;
- validates Pi owner/executor and fixed ENGIE contract metadata;
- maps the current Pi command into `EM2_POWER_INTENT_V0.2`;
- retains an executor-side hard Tesla deadline guard as a final safety layer;
- writes no physical devices directly;
- preserves persistent cutover diagnostics;
- relies on the existing EV/WW adapters, gates and actuators for physical execution and local safety.

The Homey selector is the sole authority boundary. There must never be two simultaneous planner authorities for the same actuator.

The older `homey-deploy/publish_pi_control_intent.py` / timer path may remain in source history or tooling, but it is **not the currently active production authority path** and must not be documented as such.

## 9. Live cutover validation — 2026-09-12

The controlled cutover self-test switched `EM2_Planner_Authority` from HOMEY to PI only after `/control/current` reported readiness and zero EV/WW targets. The selector remained PI only after the canonical `EM2_POWER_INTENT_V0.2` takeover was observed; otherwise the test would have rolled back to HOMEY.

### Tesla end-to-end validation

A controlled current-slot Pi target of 4830 W / 7 A was injected during the original cutover validation.

Observed physical result:

- Easee status `Charging`;
- offered/target current 7 A;
- physical power approximately 4.9 kW;
- EV gate PASS;
- actuator physical write succeeded;
- later Pi target return to 0 A physically paused the charger again.

Result: **Pi → Homey → Easee/Tesla ON and OFF both PASS.**

On 2026-09-12 a separate controlled Easee/Tesla test proved that a paused session can also start directly at 3×6 A. Observed values were approximately 6.01/6.03/6.05 A on the three phases and 4.235 kW total. This is the evidence for the production START6/RUN6 mapping.

### Warm-water end-to-end validation

A controlled current-slot Pi WW target ON was injected.

Observed physical result:

- boiler `onoff = true`;
- power approximately 2.03 kW;
- current approximately 8.97 A;
- after restore to the normal Pi target, boiler returned to `onoff = false`, 0 W.

Result: **Pi → Homey → boiler ON and OFF both PASS.**

These tests validate the complete active command path for the two primary flexible loads.

## 10. Monitoring and validation

Deployment pattern:

**inspect → minimal change → update architecture → architecture gate → deploy → validate → monitor**

For Homey Advanced Flow changes:

- inspect the exact live flow by stable ID;
- create a pre-change backup where practical;
- apply the smallest reviewed change;
- perform a targeted read-back;
- verify the physical/semantic runtime evidence before declaring PASS.

For Pi runtime source changes:

- GitHub `main` remains authoritative;
- deployed runtime must be checked for drift against the intended Git commit;
- a clean local working tree alone is not proof that the checkout is on `main` or contains all `main` changes.

## 11. Battery boundary

The planned battery architecture is Victron AC-coupled. When commissioned, Victron/DESS remains the primary real-time battery optimizer. Pi/Homey may provide forecasts, load intent and policy constraints but must not create a competing real-time battery optimizer.

## 12. Architecture enforcement

`scripts/ems_architecture_gate.sh` enforces at least:

- valid fixed-contract invariants;
- presence of this canonical architecture document;
- documentation of FIXED mode;
- dynamic-production prohibition;
- fail-closed behavior;
- same-release documentation updates for architecture-sensitive runtime/systemd/deployment changes.

A failed architecture gate is a hard deployment stop and must not be bypassed in normal operation.

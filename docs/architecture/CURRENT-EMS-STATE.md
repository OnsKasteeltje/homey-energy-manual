# CURRENT EMS STATE

> **Canonical current-state document** for the Raspberry Pi / Homey EMS.
>
> This file describes the intended current operational architecture and logic. Architecture-sensitive runtime, planner, systemd, contract-policy and Homey/Pi responsibility changes must update this document in the same release range.

**Status date:** 2026-09-13  
**Verified against:** GitHub `main`, current Pi control architecture and targeted live Homey flow reads on 2026-09-13  
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

```text
Homey devices / P1 / PV / Easee / boiler / Quatt
                    ↓
             Homey Core / state
                    ↓
        direct Pi state interface
                    ↓
 Forecasts + history + fixed-contract policy
                    ↓
        Pi hardened dynamic planner
                    ↓
          Pi /control/current
                    ↓
 Homey PI Dynamic Planner Bridge v1.2.6
                    ↓
          EM2_Power_Intent
             ↙             ↘
       EV chain          WW chain
 adapter → gate       adapter → gate
       ↓                  ↓
 EV actuator LIVE    WW actuator v0.9 LIVE
       ↓                  ↓
     Easee              boiler
```

The Pi is the active planner authority. Homey is the realtime state, executor and local safety layer. The planner itself never writes physical devices.

### Runtime authority selector

`EM2_Planner_Authority` is the **single HOMEY↔PI authority gate**.

- `PI` → the Pi bridge may publish the current Pi command into `EM2_Power_Intent`.
- `HOMEY` → the Pi bridge remains inert and guarded Homey producer `P1 v0.2.6 AUTHORITY-GUARD` is the rollback producer.
- Active Pi bridge: `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]`.

There must never be two simultaneous planner authorities for the same actuator.

## 3. Production contract policy

The production EMS is locked to the fixed three-year ENGIE contract.

Required invariants:

- `productionContractMode = FIXED`;
- `productionContractId = ENGIE_3Y_2026_2029`;
- `productionSupplier = ENGIE`;
- dynamic pricing is disabled for production;
- dynamic prices may only be used for shadow, analysis or replay;
- automatic fallback to DYNAMIC is forbidden;
- automatic contract-mode switching is forbidden;
- invalid or inconsistent configuration must fail closed.

Ordering rule:

**contract mode → permitted economic model → permitted price source → planner decision**

## 4. Pi planning chain

The regular chain builds planning inputs in this order:

1. PV forecast;
2. clean base-load history;
3. base-load forecast;
4. warm-water input;
5. warm-water plan;
6. WW forecast import;
7. quarter-hour planning inputs;
8. hardened dynamic planner v0.3 with START6 / 15-minute EV policy;
9. website shadow representations;
10. publication artifacts.

The forecast chain is executed by `ems-forecast-chain.service` (`Type=oneshot`). `inactive (dead)` after a successful run is normal.

The current plan schema is `EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3` and includes:

- 96 quarter-hour action slots / 24-hour action horizon;
- `plannerOwner = PI`;
- fixed ENGIE contract metadata;
- input freshness checks;
- `validUntil`;
- WW comfort feasibility;
- Tesla deadline feasibility;
- fail-closed execution metadata;
- multiday lookahead for WW feasibility.

The term **dynamic planner** refers to rolling optimization of flexible loads; it does not imply a dynamic electricity contract.

## 5. Current control endpoint

The Pi exposes:

`GET /control/current`

A valid production response uses schema `EMS_PI_CONTROL_COMMAND_V0.1`, returns `status = READY` and `readyForCutover = true`, and contains only the command for the current quarter-hour slot.

Current-slot semantics:

- start from `slot_start_utc`;
- end from `slot_end_utc`, or exactly start + 15 minutes when absent;
- current slot when `start <= now < end`;
- command validity bounded by both slot end and planner `validUntil`.

The endpoint validates at least owner/executor, fixed-contract invariants, planner freshness, planner validity and current-slot resolution. It is a readiness/command endpoint, not a second authority selector.

Invalid or stale planner input fails closed with zero/off targets.

## 6. Tesla production chain

Tesla charging is split into Pi planning and Homey execution.

### Pi planning

- opportunity charging uses residual PV after WW reservation;
- validated start and stable run minimum are both 3×6 A;
- nominal minimum executable power is 4140 W at 3×230 V;
- **opportunity start requires at least one positive 15-minute planner slot**;
- every following quarter-hour is evaluated independently;
- short realtime anti-flap/session protection remains an executor concern;
- explicit deadline charging is a hard requirement and may use grid energy when required;
- forced grid charging may not be introduced before published `latest_start_at`.

### Homey execution

Current chain:

- adapter: `EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6`;
- gate: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6`;
- actuator: `EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION`.

Homey validates schema, revision alignment, freshness and electrical mapping. Mapping contract is `FLOOR_3P230_START6_RUN6_FAIL_CLOSED`. The actuator is the sole automatic physical Easee writer in this production chain.

The Pi bridge retains an executor-side hard deadline guard as a final safety layer. Before the earliest safe latest-start the Pi PV target is preserved; at/after that point an active connected Tesla deadline may be projected at the configured deadline maximum.

## 7. Warm-water production chain

WW comfort is a hard constraint above optimization.

Pi planning:

- schedules remaining required heating before 19:00;
- prefers useful PV periods;
- can use PV-window shoulders so Tesla can absorb the central peak;
- avoids unnecessary repeat heating after the daily goal is reached.

Homey execution:

- Power Intent publishes `targets.ww.target_on`;
- WW Power Adapter translates the binary target;
- WW Gate requires exact schema/revision/mapping agreement;
- `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE` is the guarded physical boiler writer;
- source mode, kill switch, freshness and current device state are checked before a write.

## 8. Live cutover validation

The controlled cutover on 2026-09-12 validated the full Pi → Homey physical path.

Tesla:

- Pi target 4830 W / 7 A was executed;
- Easee reported charging at approximately 4.9 kW;
- EV gate passed;
- actuator physical write succeeded;
- return to 0 A physically paused the charger.

A separate 2026-09-12 test proved direct START6 from a paused session at approximately 4.235 kW.

Warm water:

- controlled Pi WW target ON produced boiler `onoff = true` and approximately 2.03 kW;
- return to normal target switched the boiler back OFF.

Result: **Pi → Homey → Tesla and Pi → Homey → boiler both validated end-to-end.**

## 9. Runtime / repository discipline

Deployment pattern:

**inspect → minimal change → update architecture → architecture gate → deploy → validate → monitor**

For Pi runtime changes:

- GitHub `main` remains authoritative;
- deployed runtime must be checked for drift against the intended Git commit;
- a clean working tree alone is not proof that the runtime checkout is current.

For Homey flow changes:

- inspect the exact live flow by stable ID;
- apply the smallest reviewed change;
- perform targeted read-back;
- verify semantic and physical evidence before declaring PASS.

## 10. Battery boundary

The planned battery architecture is Victron AC-coupled. When commissioned, Victron/DESS remains the primary realtime battery optimizer. Pi/Homey may provide forecasts, load intent and policy constraints but must not create a competing realtime battery optimizer.

## 11. Known technical debt

- The hardened planner still contains historical compatibility code in `deadline_requirement()` with a local `max_a = 16`. Current planning authority uses `deadline_max_a` from runtime state, so this fragment is considered cleanup debt rather than the active deadline allocator.
- WW ownership remains more distributed than EV ownership because Homey still carries substantial realtime WW state/safety policy in addition to Pi strategic planning.

## 12. Architecture enforcement

`scripts/ems_architecture_gate.sh` must continue to enforce at least:

- valid fixed-contract invariants;
- presence of this canonical document;
- FIXED production mode;
- dynamic-production prohibition;
- fail-closed behavior;
- same-release documentation updates for architecture-sensitive runtime/systemd/deployment changes.

A failed architecture gate is a hard deployment stop and must not be bypassed in normal operation.

# CURRENT EMS STATE

> **Canonical current-state document** for the Raspberry Pi / Homey EMS.
>
> This file describes the intended current operational architecture and logic. Architecture-sensitive runtime, planner, systemd, contract-policy and Homey/Pi responsibility changes must update this document in the same release range.

**Status date:** 2026-09-13  
**Verified against:** GitHub `main`, current Pi control architecture and targeted live Homey flow reads on 2026-09-13  
**Repository:** `OnsKasteeltje/homey-energy-manual`  
**Primary runtime host:** Raspberry Pi `ems-pi`

Detailed bidirectional runtime chain: `docs/architecture/homey-pi-runtime-dataflow.md`.

## 1. Source of truth

- GitHub `main` is authoritative for Pi runtime source, deployment definitions and architecture documentation.
- Deployed runtime: `/home/jeroen/ems/runtime/`.
- Pi repository checkout: `/home/jeroen/ems/repo/homey-energy-manual`.
- SQLite `/home/jeroen/ems/data/ems-history.sqlite` is the single operational historical database.
- JSON under `/home/jeroen/ems/data/` and `docs/data/` is derived state, cache or publication output.
- Homey Logic variable `EM2_Planner_Authority` is the sole runtime selector between Homey and Pi planner authority.
- GitHub is **not** a runtime transport dependency for live Homey ↔ Pi state or control.

## 2. Control architecture

There are two deliberately separate runtime directions.

### 2.1 State direction — Homey → Pi

```text
Homey devices / P1 / PV / Easee / boiler / Quatt
                    ↓
        Homey Core v0.11n
                    ↓
            EM2_Public_State
                    ↓
EM v2 | 05 Transport | Homey→Pi State Push v0.1
                    ↓
 POST /state/energy over trusted LAN
                    ↓
         ems-status-api.service
                    ↓
 state_ingest validation / anti-replay
                    ↓
/home/jeroen/ems/data/energy-state-v2.json
                    ↓
        Pi forecast/planner chain
```

The state path is push-based. The Pi must not poll Homey merely to reconstruct the canonical Core state. The Homey publisher must reuse the already-built Core state snapshot and must not introduce extra device reads solely for publication.

The Pi write endpoint is authenticated with a Bearer token loaded from `EMS_STATE_INGEST_TOKEN` through `/etc/ems/state-ingest.env`. The secret remains outside GitHub.

Accepted state is written atomically to `/home/jeroen/ems/data/energy-state-v2.json`. Required blocks are `meta`, `grid`, `tesla` and `hot_water`. Current schema is `2.12` and publisher versions must start with `EM2_CORE_STATE_`.

Freshness and ordering use `source_sample_at`, `generated_at`, `heartbeat_at` and monotonic `state_revision`. Stale, future-skewed, replayed or malformed payloads fail closed and do not replace the existing runtime state.

### 2.2 Control direction — Pi → Homey

```text
Pi forecasts + history + fixed-contract policy
                    ↓
        Pi hardened dynamic planner
                    ↓
          Pi /control/current
                    ↓
 Homey PI Dynamic Planner Bridge v1.3.0
                    ↓
          EM2_Power_Intent
             ↙             ↘
       EV chain          WW chain
 adapter → gate       adapter → gate
       ↓                  ↓
 EV actuator LIVE    WW actuator LIVE
       ↓                  ↓
     Easee              boiler
```

The Pi is the active planner authority. Homey is the realtime state, executor and local safety layer. The planner itself never writes physical devices.

### Runtime authority selector

`EM2_Planner_Authority` is the **single HOMEY↔PI authority gate**.

- `PI` → the Pi bridge may publish the current Pi command into `EM2_Power_Intent`.
- `HOMEY` → the Pi bridge remains inert and the guarded Homey producer remains the rollback producer.
- Active Pi bridge source: `src/homey/ev/pi-dynamic-planner-bridge-v1.3.0.homeyscript.js`.

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

1. planner axis / weather / Quatt forecast inputs;
2. PV forecast;
3. clean base-load history;
4. base-load forecast;
5. warm-water input;
6. warm-water plan;
7. WW forecast import;
8. quarter-hour planning inputs / shadow load plan;
9. hardened dynamic planner;
10. website shadow representations;
11. publication artifacts.

The forecast chain is executed by `ems-forecast-chain.service` (`Type=oneshot`), normally triggered by `ems-forecast-chain.timer`. `inactive (dead)` after a successful run is normal.

A second independent planner-generation timer is forbidden. Freshness guards are intentional fail-closed boundaries and must not be weakened to mask a broken upstream state producer.

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

## 6. Current state ingest endpoint

The Pi also exposes:

`POST /state/energy`

Implementation:

- `src/pi/ems-runtime/status-api/server.py`;
- `src/pi/ems-runtime/status-api/state_ingest.py`.

Runtime direction:

**Homey Core v0.11n → `EM2_Public_State` → dedicated Homey transport flow → authenticated LAN POST → Pi status API → validated atomic local state → Pi planners**.

Important invariants:

- no GitHub/cloud dependency in the live state path;
- no Pi polling of Homey for canonical Core state;
- no additional Homey device reads caused by the push itself;
- physical freshness determined by `source_sample_at`;
- monotonic anti-replay based on `state_revision`, with same-revision acceptance only for a newer heartbeat;
- maximum accepted physical sample age currently 20 minutes;
- successful persistence is atomic;
- missing/incorrect auth, malformed state, stale state and replayed state fail closed.

The Homey publication cadence should be event-driven on meaningful Core state changes plus a heartbeat no slower than the existing Core publication interval. Current Core metadata advertises `min_publish_interval_sec = 300`.

## 7. Tesla production chain

Tesla charging is split into Pi planning and Homey execution.

### Pi planning

- opportunity charging uses residual PV after WW reservation;
- validated start and stable run minimum are both 3×6 A;
- nominal minimum executable power is 4140 W at 3×230 V;
- opportunity start requires at least one positive 15-minute planner slot;
- every following quarter-hour is evaluated independently;
- short realtime anti-flap/session protection remains an executor concern;
- explicit deadline charging is a hard requirement and may use grid energy when required;
- forced grid charging may not be introduced before published `latest_start_at`.

### Homey execution

Current chain:

- PI bridge reads the strategic Pi command and bounded realtime envelope;
- adapter: `EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6`;
- gate: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6`;
- actuator: `EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION`.

Homey validates schema, revision alignment, freshness and electrical mapping. Mapping contract is `FLOOR_3P230_START6_RUN6_FAIL_CLOSED`. The actuator is the sole automatic physical Easee writer in this production chain.

For realtime opportunity execution within the Pi envelope:

`available_pre_ev_w = max(0, -P1_W + EV_actual_W)`

WW is not added back. Deadline-required charging overrides opportunity trimming when required. Homey must not become a second independent planner.

## 8. Warm-water production chain

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

## 9. Live cutover validation

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

The Homey → Pi state direction was validated end-to-end in production on 2026-09-13 using genuinely fresh Homey Core v0.11n state. The dedicated transport flow published `EM2_Public_State` over the LAN to `/state/energy`; the Pi accepted the genuine state and the canonical planner chain subsequently completed successfully. Synthetic freshness must not be used as production evidence.

## 10. Failure behavior

### State direction

If Homey Core publication stops:

- the local Pi state ages;
- stale ingest is rejected;
- hardened planner freshness checks eventually fail closed;
- freshness limits must not be relaxed merely to keep planning alive.

### Control direction

If the Pi plan or `/control/current` becomes stale or invalid:

- the PI bridge must reject production readiness;
- downstream adapter/gate/actuator logic remains fail-closed.

### GitHub

Loss of GitHub availability must not interrupt the live Homey ↔ Pi runtime transport. GitHub publication remains versioning/observability output, not the runtime bus.

## 11. Runtime / repository discipline

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

For Homey ↔ Pi boundary changes, documentation must cover both the state direction and control direction in the same release range.

## 12. Battery boundary

The planned battery architecture is Victron AC-coupled. When commissioned, Victron/DESS remains the primary realtime battery optimizer. Pi/Homey may provide forecasts, load intent and policy constraints but must not create a competing realtime battery optimizer.

## 13. Known technical debt

- The hardened planner still contains historical compatibility code in `deadline_requirement()` with a local `max_a = 16`. Current planning authority uses `deadline_max_a` from runtime state, so this fragment is considered cleanup debt rather than the active deadline allocator.
- WW ownership remains more distributed than EV ownership because Homey still carries substantial realtime WW state/safety policy in addition to Pi strategic planning.
- PV forecast quality still requires follow-up: successful planner runs can currently contain 96 fallback PV slots and zero historical slots. This is a forecast-quality issue, not a runtime-chain failure.

## 14. Architecture enforcement

`scripts/ems_architecture_gate.sh` must continue to enforce at least:

- valid fixed-contract invariants;
- presence of this canonical document;
- FIXED production mode;
- dynamic-production prohibition;
- fail-closed behavior;
- same-release documentation updates for architecture-sensitive runtime/systemd/deployment changes;
- no second independent planner-generation owner;
- no GitHub dependency in the live Homey ↔ Pi runtime state/control path.

A failed architecture gate is a hard deployment stop and must not be bypassed in normal operation.

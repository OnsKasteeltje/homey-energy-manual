# Pi EMS Migration v0.1

Status: PREPARATION ONLY — no Pi LIVE ownership changes

## Objective
Move EMS compute/orchestration from Homey to Raspberry Pi 5 incrementally while preserving the existing layered safety architecture. Homey remains LIVE until each Pi module passes SHADOW comparison and ownership transfer criteria.

## Target architecture

```text
Homey -> bounded canonical snapshot/read boundary -> Pi Central State -> Core -> Planner -> Power Intent
                                                                     |             |
                                                                     v             v
                                                                 Publisher     EV / WW adapters
                                                                                   |
                                                                                Gates
                                                                                   |
                                                                          validated commands
                                                                                   |
                                                                                Homey
                                                                          EV / WW actuators

Pi <-> Modbus TCP <-> Cerbo GX <-> Victron/DESS
```

Victron DESS remains the primary battery optimizer. The Pi EMS orchestrates household flexibility and must not become a competing real-time battery optimizer.

## Migration principles

1. No big-bang migration.
2. No Pi LIVE device writes during initial migration.
3. Migrate functionality/contracts, not literal Homey Advanced Flow card structure.
4. One central observation/snapshot boundary must fan out data to Core, Planner, Publisher and adapters.
5. Every state value carries value, timestamp, source and quality/staleness metadata.
6. Preserve SHADOW/LIVE, idempotency, run leases, stale-input checks and fail-closed behavior.
7. Ownership transfers only after deterministic comparison against the Homey implementation.
8. After each ownership transfer, disable only the superseded Homey flow and update the Homey API/load map.
9. Homey is a scarce runtime resource: all migration/commissioning reads are targeted, bounded, cached and fail-fast.
10. No brute-force discovery, broad collection scans, polling loops or repeated retry probes are permitted in the normal Pi/Homey path.
11. Known stable IDs and captured contracts are used directly; discovery-by-name is diagnostic-only and must never become steady-state behavior.
12. A Homey 429/rate-limit signal ends the current read attempt; there is no immediate same-run retry storm.
13. Publication/website work remains strictly downstream and may never wake or influence the control chain.
14. Quooker is outside the Core/snapshot critical path until a separately adapted semantic interface is designed and validated.

## 2026-08-30 Homey low-load baseline incorporated into Pi design

Today's Homey work materially sharpens the Pi migration target:

- Core v0.11a Targeted Device Reads remains the active reference pattern: broad device collection reads are eliminated from Core.
- Fan-out reduction is an explicit architecture requirement: read once, normalize once, reuse many times.
- Publisher v1.0.11 SCHEDULED LOW-LOAD remains the active publication baseline; publication is scheduled rather than driven by high-frequency state-change fan-out.
- Homey Logic has been cleaned up; unused variables were removed. Pi must not recreate legacy/unused Logic state merely for compatibility.
- Quooker has now been deliberately removed from the Core critical path and from the snapshot-aggregator runtime contract. This is stronger than the earlier 'adapt later' note: Pi Core/Central State commissioning must not depend on Quooker.
- The former `Core Snapshot Aggregator v0.1 SHADOW` candidate has advanced to a source-managed `Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER` design/runtime payload.
- Aggregator v0.2 has a canonical snapshot variable (`EM2_CORE_INPUT_V0.1`) and a short ownership lease (`EM2_CORE_INPUT_LEASE_V0.1`) to prevent concurrent full reconciliation work.
- The v0.2 full reconciliation path is intentionally low-frequency (hourly) and SHADOW-only; semantic source changes provide targeted incremental refresh paths.
- The Aggregator source explicitly says: no device writes, no retries, Quooker deliberately excluded.
- The snapshot source is now an explicit allow-list of required Homey Logic inputs instead of a broad `getVariables()` collection scan.
- Rolling energy-state and Planner Shadow publication continue independently; Pi migration must preserve this publication/control separation.
- Homey load/throttling is a first-class non-functional requirement. Every Pi migration step must demonstrate that it does not increase Homey read amplification.

### Current Aggregator v0.2 snapshot groups

The Pi snapshot parser should model the source groups rather than Homey card structure:

- `context`: context timestamp, PV top-4h and price semantic flags;
- `teslaGoal`: deadline-active/deadline/latest-start/remaining-kWh/status;
- `hotWater`: boiler mode and post-goal opportunity;
- `planner`: contract-price context, day history, contract type and PBTH price buffer;
- `publication`: last publish, last published revision and last Publisher version;
- `legacy`: compatibility placeholder only; no new Pi dependency should be built on it.

Quooker is intentionally absent.

### Homey read-budget rule

Before any Pi commissioning read is added, document:

1. exact source/device/Logic ID;
2. exact fields/capabilities required;
3. intended cadence or event trigger;
4. cache/fan-out consumers;
5. freshness/stale threshold;
6. failure behavior;
7. expected Homey calls per hour;
8. whether the same observation already exists in the canonical Core snapshot or another cache.

A new direct Homey read is rejected when an equivalent sufficiently fresh observation is already available through the canonical snapshot/cache.

## Current active-flow disposition

| Homey flow | Pi target | Initial action |
|---|---|---|
| EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads) | Core + central state | Keep LIVE on Homey; reference low-load contract |
| EM v2 | 12 Input | Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER | Canonical migration snapshot boundary | Use as preferred Homey→Pi commissioning candidate after runtime validation |
| EM v2 | 40 Data | Publisher v1.0.11 SCHEDULED LOW-LOAD | Publisher | First production migration candidate |
| EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD | Power Intent | Shadow after state/core |
| EM v2 | 10 Input | EV Deadline Goal Adapter v0.1 | Input/API contract | Keep until input path is replaced |
| EM v2 | 80 Validation | P1 Pre-EV Gate v0.2.1 TARGETED-READ | Safety gate | Migrate after Power Intent |
| EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW | EV adapter | Shadow on Pi |
| EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ | EV safety gate | Migrate after adapter |
| EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP | Homey actuator | Keep on Homey longest |
| EM v2 | 15 State | Warm Water Observer v0.2 | Central state / WW observer | Migrate after reader |
| EM v2 | 70 Planner | WW Scheduling SHADOW v0.2 | Planner | Early shadow candidate |
| EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW | Decision module | Early shadow candidate |
| EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent | Decision module | Early shadow candidate |
| EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW | WW adapter | Early shadow candidate |
| EM v2 | 80 Validation | WW Power Adapter Gate v0.2 TARGETED-READ | WW safety gate | Migrate after adapter |
| EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE | Homey actuator | Keep on Homey longest |

## Planned phases

### P0 — Contract capture
Document inputs, outputs, side effects, cadence, state dependencies and fail-closed rules for every active flow. Capture only missing contracts using targeted Homey reads; do not rediscover already-known resources.

Priority captures still required:
- exact Publisher v1.0.11 runtime contract;
- exact WW Power v0.2 contract;
- exact WW Power Adapter Gate v0.2 contract;
- exact Warm Water Actuator v0.9 contract;
- current EV gate/actuator details only where the source-managed contract is incomplete;
- runtime validation of Aggregator v0.2 NO-QUOOKER snapshot behavior/freshness/lease semantics;
- verify the explicit Aggregator allow-list against actual Core consumers without a broad Homey Logic scan.

### P1 — Pi bootstrap
Raspberry Pi OS Lite 64-bit; NVMe runtime storage; recovery microSD; SSH keys; NTP; fixed DHCP reservation; security updates; watchdog; Docker/Compose; health checks; backups; read-only Management API.

### P2 — Homey Gateway + Central State
Use Aggregator v0.2 NO-QUOOKER as the preferred commissioning boundary if runtime validation confirms completeness and acceptable freshness. Pi should consume the canonical snapshot once, validate schema/revision/generatedAt, normalize it into Central State and fan out locally. Only add targeted per-device/per-variable reads for fields proven absent from or too stale in the snapshot. Initial metrics: `homey_reads_total`, `homey_reads_per_minute`, `read_latency_ms`, `read_failures`, `homey_429_total`, `state_age_seconds`, `snapshot_revision`, `snapshot_age_seconds`, plus expected-versus-actual Homey calls/hour.

The Pi must not reproduce the Aggregator's Homey-side fan-in by independently reading every source on every Pi cycle. The purpose of the snapshot boundary is to collapse Homey fan-out/fan-in before Pi commissioning.

### P3 — Publisher
Run Pi Publisher in SHADOW, compare output, then transfer publication ownership. This is the first intended Homey-flow retirement because it has no actuator safety impact. Preserve the scheduled low-load model and strict publication/control separation.

### P4 — WW SHADOW modules
Port WW Scheduling, Post-Goal Opportunity, Seasonal Source Advisor and WW Power Adapter. Persist timestamp, input snapshot, Homey result, Pi result, delta/reason and revision for each comparison. Quooker is not part of this migration slice.

### P5 — Central State + Core
Port Core Tick semantics to Pi. Staleness becomes a first-class property of central state rather than repeated per-flow reads/checks. Do not port Homey's broad Logic collection behavior; consume the explicit snapshot contract plus narrowly justified supplemental observations.

### P6 — Power Intent
Port P1 and publish numerical EV/WW targets while Homey still owns physical actuation.

### P7 — Adapters + Gates
Move EV/WW adapters and safety gates to Pi. Pi produces validated commands; Homey remains the thin actuator layer.

### P8 — Thin Homey
Target remaining EMS flows: EV Power Actuator and Warm Water Actuator, plus only input/manual controls that still add value.

### P9 — Victron
Connect Pi directly to Cerbo GX over local IP/Modbus TCP. Keep DESS as battery optimizer.

## Promotion gate per module

```text
IMPLEMENT -> UNIT TEST -> PI SHADOW -> COMPARE HOMEY/PI -> OBSERVE -> PASS?
PASS -> TRANSFER OWNERSHIP -> HOMEY FLOW OFF -> LOAD MAP UPDATE
FAIL -> FIX -> repeat SHADOW
```

No positive physical write may be promoted on stale input, failed comparison, missing gate evidence or ambiguous ownership.

For Homey-dependent modules, promotion additionally requires:
- measured Homey call rate at or below the documented read budget;
- zero broad discovery/collection scans in the steady-state path;
- no retry storm after 429;
- proof that central cache/snapshot fan-out prevents duplicate reads;
- no publication-to-control dependency;
- no hidden Quooker dependency in Core/Central State;
- deterministic handling of snapshot revision/freshness and Aggregator lease behavior.

## Hardware baseline
Ordered for the Pi EMS runtime:
- Raspberry Pi 5, 8 GB
- official 27 W PSU
- official Active Cooler
- Geekworm X1001 NVMe adapter
- PNY CS1030 500 GB NVMe
- Geekworm P579 case
- SanDisk Extreme 128 GB microSDXC UHS-I A2/U3/V30 (Amazon ASIN B09X7BK27V) for installation/bootstrap/recovery; the 500 GB NVMe remains the primary 24/7 EMS runtime and database/history storage

## Immediate preparation backlog

- [ ] Capture only the missing exact active Homey contracts using the bounded targeted-read procedure.
- [x] Define canonical Central State schema v0.1.
- [x] Define initial Homey Gateway boundary.
- [x] Define deterministic replay/shadow comparison foundation.
- [x] Define Docker service layout and configuration/secrets strategy.
- [x] Define Pi health/backup/recovery requirements.
- [x] Add SHADOW-only read-only Management API baseline.
- [x] Define a machine-valid Aggregator v0.2 NO-QUOOKER source/payload and explicit snapshot allow-list.
- [x] Remove Quooker from the Core/snapshot critical path.
- [ ] Runtime-validate Aggregator v0.2 NO-QUOOKER with minimal targeted Homey reads only; do not brute-force probe.
- [ ] Add Pi parser/fixture for `EM2_CORE_INPUT_V0.1`, including revision/generatedAt and missing/stale handling.
- [ ] Capture exact Publisher v1.0.11 and update Publisher acceptance tests from the exact active source.
- [ ] Capture WW v0.2/Gate v0.2/Actuator v0.9 exact active contracts and update replay coverage.
- [ ] Establish and record the Pi commissioning Homey read budget before real Pi polling is enabled.
- [ ] Add representative runtime fixtures (idle/night, PV production, EV connected-paused, EV charging, WW ON/OFF). Quooker fixtures are excluded until a separate semantic adapter exists.
- [ ] Update Homey API/load map after each later ownership transfer.

## Hard constraint
This preparation document does not authorize any Homey flow disablement, actuator ownership change, or LIVE Pi device write. Homey contract capture and commissioning must follow the targeted, bounded, cached and fail-fast read policy; no brute-force Homey access is permitted. Quooker is explicitly outside the Core/snapshot commissioning path.

# Pi EMS Migration v0.1

Status: PREPARATION ONLY — no Homey runtime changes

## Objective
Move EMS compute/orchestration from Homey to Raspberry Pi 5 incrementally while preserving the existing layered safety architecture. Homey remains LIVE until each Pi module passes SHADOW comparison and ownership transfer criteria.

## Target architecture

```text
Homey devices -> bounded Homey read boundary -> Central State -> Core -> Planner -> Power Intent
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
4. One central device reader/state cache must fan out data to Core, Planner, Publisher and adapters.
5. Every state value carries value, timestamp, source and quality/staleness metadata.
6. Preserve SHADOW/LIVE, idempotency, run leases, stale-input checks and fail-closed behavior.
7. Ownership transfers only after deterministic comparison against the Homey implementation.
8. After each ownership transfer, disable the superseded Homey flow and update the Homey API/load map.
9. Homey is a scarce runtime resource: all migration/commissioning reads are targeted, bounded, cached and fail-fast.
10. No brute-force discovery, broad collection scans, polling loops or repeated retry probes are permitted in the normal Pi/Homey path.
11. Known stable IDs and captured contracts are used directly; discovery-by-name is diagnostic-only and must never become steady-state behavior.
12. A Homey 429/rate-limit signal ends the current read attempt; there is no immediate same-run retry storm.
13. Publication/website work remains strictly downstream and may never wake or influence the control chain.

## 2026-08-30 Homey low-load baseline incorporated into Pi design

The latest Homey work materially sharpens the Pi migration target:

- Core v0.11a Targeted Device Reads is the active reference pattern: broad device collection reads are eliminated from Core.
- Fan-out reduction is an explicit architecture requirement: read once, normalize once, reuse many times.
- Publisher v1.0.11 SCHEDULED LOW-LOAD is the active publication baseline; publication is scheduled rather than driven by high-frequency state-change fan-out.
- Homey Logic has been cleaned up; unused variables were removed. Pi must not recreate legacy/unused Logic state merely for compatibility.
- Remaining Homey Logic dependencies must be captured as an explicit allow-list and mapped into canonical Pi state rather than fetched through a broad Logic collection scan.
- `EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW` is a candidate migration bridge and must be evaluated before enabling Pi device-by-device Homey reads. If its contract is complete, fresh and low-load, the preferred commissioning path is one bounded snapshot read followed by Pi-local fan-out.
- Quooker is not assumed to be safely reusable as a normal controlled load. Its semantics/interface must be adapted and validated separately before inclusion in Pi control.
- Homey load/throttling is a first-class non-functional requirement. Every Pi migration step must demonstrate that it does not increase Homey read amplification.

### Homey read-budget rule

Before any Pi commissioning read is added, document:

1. exact source/device/Logic ID;
2. exact fields/capabilities required;
3. intended cadence or event trigger;
4. cache/fan-out consumers;
5. freshness/stale threshold;
6. failure behavior;
7. expected Homey calls per hour;
8. whether the same observation already exists in the Core Snapshot Aggregator or another canonical snapshot.

A new direct Homey read is rejected when an equivalent sufficiently fresh observation is already available through the central snapshot/cache.

## Current active-flow disposition

| Homey flow | Pi target | Initial action |
|---|---|---|
| EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads) | Core + central state | Keep LIVE on Homey; reference low-load contract |
| EM v2 | 12 Input | Core Snapshot Aggregator v0.1 SHADOW | Migration snapshot boundary | Evaluate as preferred low-load Homey→Pi commissioning feed |
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
- Core Snapshot Aggregator v0.1 SHADOW input/output/freshness contract;
- remaining Core Logic dependencies as an explicit allow-list.

### P1 — Pi bootstrap
Raspberry Pi OS Lite 64-bit; NVMe runtime storage; recovery microSD; SSH keys; NTP; fixed DHCP reservation; security updates; watchdog; Docker/Compose; health checks; backups; read-only Management API.

### P2 — Homey Gateway + Central State
Prefer the lowest-load validated source boundary. First evaluate Core Snapshot Aggregator as commissioning input. Only add targeted per-device/per-variable reads for fields not safely available in the snapshot. Cache centrally and expose observations to all Pi modules. Initial metrics: `homey_reads_total`, `homey_reads_per_minute`, `read_latency_ms`, `read_failures`, `homey_429_total`, `state_age_seconds`, plus expected-versus-actual Homey calls/hour.

### P3 — Publisher
Run Pi Publisher in SHADOW, compare output, then transfer publication ownership. This is the first intended Homey-flow retirement because it has no actuator safety impact. Preserve the scheduled low-load model and strict publication/control separation.

### P4 — WW SHADOW modules
Port WW Scheduling, Post-Goal Opportunity, Seasonal Source Advisor and WW Power Adapter. Persist timestamp, input snapshot, Homey result, Pi result, delta/reason and revision for each comparison. Quooker is excluded from automatic reuse until its low-load semantic interface is separately adapted and validated.

### P5 — Central State + Core
Port Core Tick semantics to Pi. Staleness becomes a first-class property of central state rather than repeated per-flow reads/checks. Do not port Homey's broad Logic collection behavior; replace it with explicit state inputs.

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
- proof that central cache/fan-out prevents duplicate reads;
- no publication-to-control dependency.

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
- [ ] Capture exact Publisher v1.0.11 and update Publisher acceptance tests from the exact active source.
- [ ] Capture WW v0.2/Gate v0.2/Actuator v0.9 exact active contracts and update replay coverage.
- [ ] Evaluate Core Snapshot Aggregator v0.1 SHADOW as the preferred Homey→Pi commissioning feed.
- [ ] Replace remaining broad Logic assumptions with an explicit minimal Logic allow-list.
- [ ] Establish and record the Pi commissioning Homey read budget before real Pi polling is enabled.
- [ ] Add representative runtime fixtures (idle/night, PV production, EV connected-paused, EV charging, WW ON/OFF; Quooker only after adaptation).
- [ ] Update Homey API/load map after each later ownership transfer.

## Hard constraint
This preparation document does not authorize any Homey flow disablement, actuator ownership change, or LIVE Pi device write. Homey contract capture and commissioning must follow the targeted, bounded, cached and fail-fast read policy; no brute-force Homey access is permitted.

# Pi EMS Migration v0.1

Status: PREPARATION ONLY — no Homey runtime changes

## Objective
Move EMS compute/orchestration from Homey to Raspberry Pi 5 incrementally while preserving the existing layered safety architecture. Homey remains LIVE until each Pi module passes SHADOW comparison and ownership transfer criteria.

## Target architecture

```text
Homey devices -> Pi Homey Gateway -> Central State -> Core -> Planner -> Power Intent
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

## Current active-flow disposition

| Homey flow | Pi target | Initial action |
|---|---|---|
| EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads) | Core + central state | Keep LIVE on Homey |
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
Document inputs, outputs, side effects, cadence, state dependencies and fail-closed rules for every active flow.

### P1 — Pi bootstrap
Raspberry Pi OS Lite 64-bit on NVMe; SSH keys; NTP; fixed DHCP reservation; security updates; watchdog; Docker/Compose; health checks; backups.

### P2 — Homey Gateway + Central State
Implement targeted reads once and cache centrally. Initial metrics: `homey_reads_total`, `homey_reads_per_minute`, `read_latency_ms`, `read_failures`, `state_age_seconds`.

### P3 — Publisher
Run Pi Publisher in SHADOW, compare output, then transfer publication ownership. This is the first intended Homey-flow retirement because it has no actuator safety impact.

### P4 — WW SHADOW modules
Port WW Scheduling, Post-Goal Opportunity, Seasonal Source Advisor and WW Power Adapter. Persist timestamp, input snapshot, Homey result, Pi result, delta/reason and revision for each comparison.

### P5 — Central State + Core
Port Core Tick semantics to Pi. Staleness becomes a first-class property of central state rather than repeated per-flow reads/checks.

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

## Hardware baseline
Ordered for the Pi EMS runtime:
- Raspberry Pi 5, 8 GB
- official 27 W PSU
- official Active Cooler
- Geekworm X1001 NVMe adapter
- PNY CS1030 500 GB NVMe
- Geekworm P579 case

## Immediate preparation backlog

- [ ] Capture exact contracts for the active Homey flows.
- [ ] Define canonical Central State schema.
- [ ] Define Homey Gateway read/write API boundary.
- [ ] Define SHADOW comparison record schema and tolerances.
- [ ] Define Docker service layout and configuration/secrets strategy.
- [ ] Define Pi health/backup/recovery requirements.
- [ ] Define Publisher v1 Pi acceptance test.
- [ ] Update Homey API load map after each later ownership transfer.

## Hard constraint
This preparation document does not authorize any Homey flow disablement, actuator ownership change, or LIVE Pi device write.

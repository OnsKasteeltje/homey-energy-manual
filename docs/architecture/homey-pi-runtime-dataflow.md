# Homey ↔ Pi runtime dataflow

> Detailed companion to `docs/architecture/CURRENT-EMS-STATE.md`.
>
> This document defines the two one-way runtime chains between Homey and the Raspberry Pi. The chains are deliberately asymmetric: Homey publishes observed state to the Pi; the Pi publishes bounded control commands back to Homey. Neither side may bypass the defined ownership boundary.

**Status date:** 2026-09-13  
**Repository:** `OnsKasteeltje/homey-energy-manual`

## 1. Architectural rule

There are two separate directions:

1. **State direction — Homey → Pi**: realtime observed state and Homey-owned operational facts.
2. **Control direction — Pi → Homey**: planner output for the current slot, executed and safety-checked by Homey.

They must not be collapsed into one bidirectional writer or polling loop.

GitHub is source of truth for code and documentation, but **is not a runtime transport dependency** for either direction.

## 2. State chain: Homey → Pi

Canonical chain:

```text
Homey devices / P1 / PV / Easee / boiler / Quatt
                    ↓
          Homey Core v0.11n
                    ↓
            EM2_Public_State
                    ↓
EM v2 | 05 Transport | Homey→Pi State Push v0.1
                    ↓
   HTTP POST /state/energy on Pi LAN
     Authorization: Bearer <secret>
                    ↓
       ems-status-api.service
                    ↓
 state_ingest.py validation / anti-replay
                    ↓
 atomic write: /home/jeroen/ems/data/energy-state-v2.json
                    ↓
         Pi forecast/planner chain
```

### 2.1 Ownership

- Homey owns acquisition of live device state and construction of the canonical Core state snapshot.
- The Pi does **not** poll Homey to reconstruct this state.
- Homey Core publishes the canonical snapshot to `EM2_Public_State`.
- The dedicated transport flow `EM v2 | 05 Transport | Homey→Pi State Push v0.1` forwards that exact state to the Pi.
- The transport component performs no device reads, planning decisions or physical writes; it reads only the canonical state and ingest token.
- The Pi owns validation, persistence and subsequent planner consumption.

### 2.2 Endpoint

Pi write endpoint:

`POST /state/energy`

Implemented by:

- `src/pi/ems-runtime/status-api/server.py`
- `src/pi/ems-runtime/status-api/state_ingest.py`

Runtime service:

- `ems-status-api.service`
- working directory `/home/jeroen/ems/runtime/status-api`

### 2.3 Authentication

The write endpoint is authenticated with a shared Bearer token.

Pi token source:

- environment variable `EMS_STATE_INGEST_TOKEN`;
- loaded through systemd `EnvironmentFile=/etc/ems/state-ingest.env`;
- secret file is outside GitHub and must not be committed.

A missing token configuration fails closed. An absent or incorrect Authorization header is rejected.

The endpoint currently uses plain HTTP on the trusted LAN. The Bearer token therefore authenticates the sender but does not encrypt LAN traffic.

### 2.4 State contract

Required top-level objects:

- `meta`
- `grid`
- `tesla`
- `hot_water`

Current required schema:

- `meta.schema_version = 2.12`
- `meta.publisher_version` starts with `EM2_CORE_STATE_`

Freshness and ordering use:

- `source_sample_at` for physical sample freshness;
- `generated_at` for state generation time;
- `heartbeat_at` for publication liveness;
- `state_revision` for monotonic state ordering.

Acceptance rules include:

- physical source sample not older than 20 minutes;
- future source skew no more than 60 seconds;
- lower `state_revision` is rejected;
- equal revision is accepted only when `heartbeat_at` is newer;
- invalid or replayed input leaves the existing runtime state untouched.

### 2.5 Atomic persistence

Accepted input is written atomically to:

`/home/jeroen/ems/data/energy-state-v2.json`

The ingest writes a temporary file in the same directory, flushes/fsyncs it, replaces the target with `os.replace()`, then fsyncs the directory. Planners therefore see either the previous complete state or the new complete state, never a partially-written JSON document.

### 2.6 Publication cadence

The state path is push-based, not poll-based.

Desired Homey behavior:

- push on a semantic Core state/revision change;
- also provide a heartbeat within the existing Core publication interval;
- current Core metadata advertises `min_publish_interval_sec = 300`;
- avoid aggressive periodic publication and avoid new Homey device polling.

## 3. Planning chain inside the Pi

After accepted state persistence, the canonical forecast/planning chain remains owned by the Pi:

```text
energy-state-v2.json
        ↓
planner axis / weather / Quatt forecast
        ↓
PV forecast
        ↓
clean base-load history
        ↓
base-load forecast
        ↓
WW input → WW plan → WW datastore import
        ↓
quarter-hour shadow load plan
        ↓
hardened dynamic planner
        ↓
website shadow builders
        ↓
publication artifacts
        ↓
/control/current projection
```

The regular generation owner is `ems-forecast-chain.service`, triggered by `ems-forecast-chain.timer`. A second independent planner-generation timer is forbidden.

Freshness guards are intentional fail-closed boundaries. They must not be weakened to hide a broken state producer.

## 4. Control chain: Pi → Homey

Canonical chain:

```text
Pi hardened dynamic planner
           ↓
current validated plan
           ↓
GET /control/current
           ↓
Homey PI Dynamic Planner Bridge
           ↓
canonical EM2_Power_Intent
        ↙                 ↘
   EV adapter          WW adapter
       ↓                  ↓
    EV gate             WW gate
       ↓                  ↓
  EV actuator         WW actuator
       ↓                  ↓
     Easee              boiler
```

### 4.1 Pi responsibility

The Pi:

- chooses strategic flexible-load actions within planner constraints;
- applies fixed-contract policy;
- checks state/input freshness;
- exposes only a bounded current-slot command;
- never directly writes Easee, Tesla, boiler or other physical Homey devices.

### 4.2 Control endpoint

Pi read endpoint:

`GET /control/current`

Current schema:

`EMS_PI_CONTROL_COMMAND_V0.1`

A production-ready response must be `READY`, fresh, within `validUntil`, owned by the Pi planner, compatible with the fixed ENGIE contract, and resolvable to the current quarter-hour slot.

Invalid/stale planner state fails closed.

### 4.3 Homey responsibility

Homey remains the execution and local safety layer.

The PI Dynamic Planner Bridge:

- reads `/control/current` over the LAN;
- validates schema, ownership, contract invariants, freshness and cutover state;
- combines the Pi strategic envelope with permitted realtime execution data;
- publishes only the canonical `EM2_Power_Intent`;
- does not write physical devices directly.

Downstream adapters, gates and actuators remain the only permitted route to physical writes.

## 5. EV bounded realtime execution

For Tesla opportunity charging the current responsibility split is:

- Pi = strategic planner and bounded realtime envelope;
- Homey = realtime executor within that Pi envelope using live P1/Easee state.

Surplus calculation uses the pre-EV balance:

`available_pre_ev_w = max(0, -P1_W + EV_actual_W)`

WW is not added back into this calculation.

Deadline-required charging overrides opportunity trimming when required. Realtime execution must not become a second independent planner.

## 6. Failure behavior

### Homey → Pi state direction

If state publication stops or becomes stale:

- ingest stops accepting stale/replayed payloads;
- `energy-state-v2.json` ages;
- hardened planner freshness checks eventually fail closed;
- no freshness threshold may be relaxed merely to keep planning running.

### Pi → Homey control direction

If the plan or `/control/current` is invalid/stale:

- the bridge must not treat the command as production-ready;
- downstream intent must fail closed according to the existing bridge/gate/actuator contracts.

### GitHub availability

Loss of GitHub availability must not interrupt the live Homey ↔ Pi runtime state/control transport. GitHub publication is observability/versioning output, not the runtime bus.

## 7. Deployment discipline

Any change to either direction must update, in the same release range:

1. implementation source;
2. `CURRENT-EMS-STATE.md`;
3. this runtime-dataflow document;
4. architecture gate rules when a new invariant is introduced;
5. Pi runtime deployment where applicable;
6. validation evidence.

Required validation order:

**GitHub source → Pi deployed runtime → endpoint behavior → Homey bridge/executor behavior → physical evidence when a physical actuator is involved.**

## 8. Commissioning rule for state ingest

Do not validate successful ingest by making old physical values appear fresh in the production state file. A synthetic payload must use an isolated test target/test harness, or the planner generation chain must be isolated and the production state restored before re-enabling it.

Production planner generation should resume only after a genuinely fresh Homey Core state has been accepted.


## 9. Production validation — 2026-09-13

The Homey → Pi state direction is production-validated with genuine Core state:

```text
Homey Core v0.11n
  → EM2_Public_State
  → EM v2 | 05 Transport | Homey→Pi State Push v0.1
  → POST /state/energy
  → authenticated ingest accepted
  → atomic energy-state-v2.json
  → canonical forecast/planner chain
  → /control/current READY
```

The canonical `ems-forecast-chain.timer` is active on its single `:03,:18,:33,:48` cadence. The automatic 19:18 CEST run refreshed PV, weather, Quatt and WW inputs successfully and `/health` returned `ok`.

The status API health contract validates the current planner schemas:

- `EMS_PI_PV_FORECAST_V0.2`
- `EMS_PI_WW_PLAN_V0.7.0`

Schema drift in observability must not be mistaken for planner failure.

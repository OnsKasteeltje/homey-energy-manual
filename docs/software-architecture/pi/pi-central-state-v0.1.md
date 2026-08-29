# Pi EMS Canonical Central State v0.1

Status: DESIGN / SHADOW PREPARATION

This schema is derived from the active Homey Core v0.11a baseline and is intentionally independent of Homey Advanced Flow card structure.

## State envelope

Every externally observed value MUST be represented with provenance/freshness metadata:

```json
{
  "value": null,
  "observed_at": null,
  "received_at": null,
  "source": null,
  "quality": "UNKNOWN",
  "stale_after_s": null
}
```

Allowed initial quality states: `GOOD`, `STALE`, `MISSING`, `DEGRADED`, `UNKNOWN`.

A missing or stale safety-relevant value MUST NOT silently coerce to zero.

## Canonical top-level state

```text
ems
├── meta
│   ├── schema_version
│   ├── generated_at
│   └── source_revision
├── health
│   ├── homey_gateway
│   ├── last_successful_refresh
│   ├── read_failures
│   └── degraded_reasons[]
├── grid
│   ├── power_W
│   ├── phase_power_W[]
│   └── phase_current_A[]
├── pv
│   ├── total_W
│   ├── solaredge_W
│   ├── goodwe4200_W
│   └── goodwe2000_W
├── house
│   └── derived_power_W
├── ev
│   ├── charger
│   │   ├── power_W
│   │   ├── current_A
│   │   ├── voltage_V
│   │   ├── state
│   │   └── meter
│   ├── equalizer
│   │   ├── power_W
│   │   └── phase_current_A[]
│   ├── deadline
│   ├── goal
│   └── availability
├── ww
│   ├── boiler_power_W
│   ├── boiler_on
│   ├── observer_state
│   ├── goal_reached_today
│   └── seasonal_source
├── heating
│   └── quatt
│       ├── electrical_power_W
│       ├── thermal_power_W
│       ├── cop
│       ├── mode
│       ├── thermostat
│       └── cv_state
├── appliances
│   ├── washer
│   └── dryer
├── contract
├── prices
├── forecast
├── planner
├── decision
└── power_intent
    ├── ev_target_W
    └── ww_target_W
```

## Homey Gateway device registry — active Core baseline

| Role | Stable Homey device ID |
|---|---|
| P1 meter | `7a696d77-15fb-4b68-9bce-f1e39bff5045` |
| Easee charger | `65ee9fda-9535-44ab-8037-809587bc8f1c` |
| Easee Equalizer | `7dd35f8f-1dca-42f5-9b41-9b69bd14c611` |
| Boiler | `8238b270-21a2-4284-aa78-6b9b58d254ab` |
| Quatt | `1e5dcde5-c1cf-4c32-9141-33e00ce36de9` |
| SolarEdge | `c52c1c1d-9080-4a3b-b2e0-acc1eed7bf20` |
| GoodWe 4200 | `9f55af14-a080-4129-8887-c81b95f649bb` |
| GoodWe 2000 | `cbb98288-1c44-4718-9a66-13709b9d0172` |
| Washer | `921c9604-b06e-43df-b903-2294a971c525` |
| Dryer | `dfce2ff9-3d90-4721-9865-2a7bcc6d7100` |

No discovery-by-name is permitted in the normal Pi gateway path.

## Core v0.11a functional contract — first capture

### Trigger/cadence
- Every 5 minutes.

### Device inputs
- P1: grid power, phase power/current, capability timestamps.
- Easee: EV power/current/voltage/state/meter.
- Equalizer: power and phase currents.
- Boiler: power and on/off.
- Quatt: electrical/thermal/COP/mode/thermostat/CV state.
- SolarEdge + both GoodWe inverters: production power and timestamps.
- Washer + dryer: direct appliance status fields consumed by Core.

### Logic inputs
The active v0.11a baseline still consumes Homey Logic through a broad `getVariables()` call. Exact variable contract is to be captured separately. Pi migration MUST NOT reproduce the broad collection scan as its steady-state design.

### Outputs/contracts to preserve
- existing state/decision schemas until explicitly versioned;
- producer-only `EM2_Control_EV` semantic behavior;
- downstream Power Intent semantics;
- semantic-write suppression behavior.

### Side effects
- no physical device writes;
- no change to EV/WW control ownership;
- no change to Publisher/Planner ownership.

### Fail-closed requirements
- failed/stale P1 => flex decisions invalid/fail closed;
- missing PV source => house balance invalid/degraded according to policy, never silently valid zero;
- unreadable Easee/Equalizer => EV availability/measurement cannot be promoted to valid;
- no immediate retry loop after Homey 429;
- freshness/skew validation must be preserved.

## Homey Gateway initial boundary

The gateway owns Homey communication. Domain modules MUST consume Central State, not call Homey directly.

```text
Homey API
   |
   v
homey-gateway
   |
   +--> device registry / targeted reads
   +--> raw observations
   +--> quality + timestamps
   v
central-state
   |
   +--> Core
   +--> Planner
   +--> Publisher
   +--> Power Intent
   +--> adapters/gates
```

Initial gateway metrics:
- `homey_reads_total`
- `homey_reads_per_minute`
- `homey_read_latency_ms`
- `homey_read_failures_total`
- `homey_429_total`
- `state_age_seconds`

## Next contract-capture work

1. Capture exact Homey Logic variables consumed by Core and map them to canonical state fields.
2. Capture Publisher v1.0.11 contract as first production migration candidate.
3. Capture WW SHADOW module contracts.
4. Capture Power Intent and EV/WW adapter/gate contracts.
5. Define comparison tolerances per output type (exact semantic vs numeric tolerance).

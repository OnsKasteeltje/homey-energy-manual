# Heating Room Model

Status: **MODEL / READ-ONLY / SHADOW**  
Schema: `EMS_HEATING_ROOM_MODEL_V0.1`

## Purpose

The Heating Room Model is the canonical EMS interpretation layer between the read-only Honeywell/Resideo source models and any future room-heating optimisation.

It does **not** replace the Honeywell schedule and does **not** write to Honeywell, Homey, OpenTherm, Quatt or another physical device.

Honeywell remains the baseline authority for room comfort schedules.

## Architectural position

```text
RESIDEO / HONEYWELL
        |
        +--> EMS_HONEYWELL_SCHEDULE_V0.2  (low-frequency schedule source)
        |
        +--> EMS_HONEYWELL_STATE_V0.2     (higher-frequency room state)
                         |
                         v
              EMS_HEATING_ROOM_MODEL_V0.1
                    READ_ONLY / SHADOW
                         |
                         v
             future heating planner model
                         |
                         v
             future validated control chain
```

The source collectors remain operational Pi runtime tooling. Deployment definitions remain under `deploy/systemd/`. This document defines the domain model only and does not move or duplicate runtime collectors.

## Source models

### Schedule

`EMS_HONEYWELL_SCHEDULE_V0.2` is the canonical Honeywell schedule baseline. Per mapped room it provides the weekly schedule plus current and next switchpoints.

### State

`EMS_HONEYWELL_STATE_V0.2` is the canonical current Honeywell room-state source. Per mapped room it provides at least:

- measured room temperature;
- current target temperature;
- setpoint mode.

### Room identity

Schedule and state are joined using the canonical room `key` from `EMS_HONEYWELL_ZONE_MAP_V0.1`.

The current mapping contains eight rooms. Honeywell IDs and Homey device IDs are integration metadata; planner logic must use the canonical room key rather than vendor identifiers.

## Time semantics

All EMS-facing room-heating planning timestamps use the home timezone:

`Europe/Amsterdam`

A source switchpoint may contain a weekday/time representation, but once resolved into the Heating Room Model it becomes an offset-aware absolute timestamp.

Example:

```json
"nextChangeAt": "2026-09-15T17:00:00+02:00"
```

This prevents UTC/local-time ambiguity at the planner boundary.

## V0.1 model

Illustrative shape:

```json
{
  "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
  "mode": "READ_ONLY",
  "controlMode": "SHADOW",
  "generatedAt": "2026-09-15T15:00:00Z",
  "timezone": "Europe/Amsterdam",
  "baselineAuthority": "HONEYWELL",
  "rooms": [
    {
      "key": "woonkamer",
      "displayName": "Woonkamer",
      "current": {
        "temperature_C": 18.4,
        "targetTemperature_C": 18.0,
        "setpointMode": "FOLLOW_SCHEDULE"
      },
      "baseline": {
        "currentTarget_C": 18.0,
        "nextChangeAt": "2026-09-15T17:00:00+02:00",
        "nextTarget_C": 20.0,
        "direction": "UP"
      }
    }
  ]
}
```

The values above are illustrative, not runtime defaults.

## Transition classification

For every room, the next baseline transition is classified only from the Honeywell baseline:

```text
nextTarget > currentTarget  -> UP
nextTarget < currentTarget  -> DOWN
nextTarget = currentTarget  -> NONE
```

No PV, tariff or actuator information is needed for this classification.

## Comfort invariant

Honeywell remains the comfort authority.

Future EMS optimisation may only consider advancing a scheduled temperature **increase** (`UP`) when an energy opportunity exists.

The following invariants apply:

1. A scheduled temperature reduction (`DOWN`) is never advanced for energy optimisation.
2. EMS optimisation never raises the target above the later Honeywell scheduled target.
3. The original Honeywell transition time and target remain retained as the baseline for audit and visualisation.
4. Absence, stale data, invalid schedule data or unresolved time semantics must fail safe to the unmodified Honeywell baseline.
5. V0.1 performs no physical writes and contains no actuator command.

## Future PV-preheat layer

PV-aware preheating is deliberately **not** part of V0.1.

The future planner may consume an `UP` transition together with PV forecast, current room state and other constraints to create a shadow candidate that advances the start of the upcoming Honeywell comfort target.

Conceptually:

```text
Honeywell UP transition
        +
PV opportunity / planner constraints
        |
        v
preheat candidate (SHADOW)
        |
        v
baseline vs candidate visualisation
        |
        v
future control only after validation
```

This keeps source acquisition, canonical interpretation, planning and physical execution separated.

## Website / visualisation

The existing `EMS_PUBLIC_HEATING_SCHEDULE_V0.1` remains a privacy-safe derived publication of the raw Honeywell weekly schedule. It is not a second source of truth.

A later planner visualisation may combine the baseline room curve with a shadow preheat candidate. The original Honeywell curve must remain visually distinguishable from any EMS-advanced segment.

## Safety and rollout

`EMS_HEATING_ROOM_MODEL_V0.1` starts read-only and shadow-only.

A future Honeywell write/override path requires its own adapter, validation gate and actuator boundary and must follow the existing EMS rule: model -> shadow validation -> guarded execution. No such physical Honeywell control path is defined by V0.1.

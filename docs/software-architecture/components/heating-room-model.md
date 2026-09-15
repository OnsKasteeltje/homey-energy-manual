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

Repository ownership follows the target structure:

- vendor acquisition: `services/pi/integrations/honeywell/`;
- canonical EMS interpretation: `services/pi/state/heating/`;
- future optimisation: `services/pi/planner/heating/`;
- future guarded control, only after explicit validation: `services/pi/control/heating/`.

Deployment definitions remain under `deploy/systemd/`. The room model must not be implemented in the Honeywell integration or in a legacy `src/pi/` location.

## Source models

### Schedule

`EMS_HONEYWELL_SCHEDULE_V0.2` is the canonical Honeywell schedule baseline. Per mapped room it provides the weekly schedule plus current and next switchpoints.

A live read-only collection on 2026-09-15 validated the exact representation for all eight mapped rooms:

```json
{
  "currentSwitchpoint": {
    "time": "2026-09-15T19:30:00+02:00",
    "targetTemperature_C": 19.0
  },
  "nextSwitchpoint": {
    "time": "2026-09-15T22:00:00+02:00",
    "targetTemperature_C": 15.5
  },
  "weeklySchedule": [
    {
      "day_of_week": "monday",
      "switchpoints": [
        {
          "heat_setpoint": 18.0,
          "time_of_day": "17:30:00"
        }
      ]
    }
  ]
}
```

The values above are a validated `woonkamer` excerpt, not global defaults.

### State

`EMS_HONEYWELL_STATE_V0.2` is the canonical current Honeywell room-state source. Per mapped room it provides at least:

- measured room temperature;
- current target temperature;
- setpoint mode.

The current Honeywell target is **observed state**, and may differ from the scheduled baseline because of a manual or temporary override. The room model therefore keeps actual current target and scheduled baseline target separate.

### Room identity

Schedule and state are joined using the canonical room `key` from `EMS_HONEYWELL_ZONE_MAP_V0.1`.

The current mapping contains eight rooms. Honeywell IDs and Homey device IDs are integration metadata; planner logic must use the canonical room key rather than vendor identifiers.

## Freshness and validity

The room model must retain source provenance and must not hide stale or incomplete source data.

At minimum the generated model records:

- `scheduleGeneratedAt` from `EMS_HONEYWELL_SCHEDULE_V0.2.generatedAt`;
- `stateGeneratedAt` from `EMS_HONEYWELL_STATE_V0.2.generatedAt`;
- per-room/source validity sufficient to fail closed when schedule or state cannot be trusted.

A model builder must reject schema mismatch, missing room keys, duplicate room keys, non-OK schedule status, malformed switchpoints or unresolved timestamps rather than inventing values.

## Time semantics

All EMS-facing room-heating planning timestamps use the home timezone:

`Europe/Amsterdam`

The Honeywell collector already exposes `currentSwitchpoint.time` and `nextSwitchpoint.time` as offset-aware absolute local timestamps. The room model must preserve those resolved timestamps and must not reinterpret them through UTC or the host's incidental timezone.

The raw `weeklySchedule` uses weekday plus local `time_of_day`. If the room model needs to project a later weekly switchpoint beyond the already-resolved next switchpoint, it must resolve that schedule in `Europe/Amsterdam`, including DST, and emit an offset-aware absolute timestamp.

## V0.1 model

Illustrative shape:

```json
{
  "schema": "EMS_HEATING_ROOM_MODEL_V0.1",
  "mode": "READ_ONLY",
  "controlMode": "SHADOW",
  "generatedAt": "2026-09-15T19:50:00Z",
  "timezone": "Europe/Amsterdam",
  "baselineAuthority": "HONEYWELL",
  "sources": {
    "scheduleGeneratedAt": "2026-09-15T19:49:03.104492Z",
    "stateGeneratedAt": "2026-09-15T19:48:00Z"
  },
  "rooms": [
    {
      "key": "woonkamer",
      "displayName": "Woonkamer",
      "current": {
        "temperature_C": 18.4,
        "targetTemperature_C": 19.0,
        "setpointMode": "FOLLOW_SCHEDULE"
      },
      "baseline": {
        "currentTarget_C": 19.0,
        "nextChangeAt": "2026-09-15T22:00:00+02:00",
        "nextTarget_C": 15.5,
        "direction": "DOWN"
      }
    }
  ]
}
```

Only the baseline transition values in this example reflect the validated 2026-09-15 `woonkamer` schedule snapshot. Current measured temperature/state values remain illustrative until a matching state snapshot is supplied to the model builder.

## Transition classification

For every room, the next baseline transition is classified only from the Honeywell scheduled baseline:

```text
nextTarget > currentTarget  -> UP
nextTarget < currentTarget  -> DOWN
nextTarget = currentTarget  -> NONE
```

The actual Honeywell `current.targetTemperature_C` is not substituted for `baseline.currentTarget_C` when classifying the schedule transition, because a temporary override must not rewrite the comfort baseline.

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

## V0.1 implementation boundary

The first implementation belongs under `services/pi/state/heating/` and is a pure read-only model builder. It consumes the two canonical Honeywell JSON outputs and emits `EMS_HEATING_ROOM_MODEL_V0.1`.

It must not:

- call Honeywell/Resideo directly;
- call Homey;
- use PV forecast or tariff data;
- create a preheat decision;
- write an actuator or setpoint;
- mutate either source JSON.

This keeps vendor acquisition and EMS interpretation independently testable.

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

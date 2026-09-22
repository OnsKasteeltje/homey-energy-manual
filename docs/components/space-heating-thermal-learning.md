# Ruimteverwarming — Thermal Learning boundary

Status: **READ_ONLY / SHADOW**  
Parent domain: `docs/components/space-heating.md`

## Legacy thermal consolidation

The former `src/pi/ems-runtime/thermal/` directory contained two different responsibilities and is not retained as a second thermal subsystem.

`build_thermal_observer.py` is retired rather than copied. Its Honeywell schedule/room-state interpretation overlaps with the canonical chain introduced for Ruimteverwarming and still expected the obsolete `EMS_HONEYWELL_SCHEDULE_V0.1` runtime contract. The canonical room interpretation is now exclusively:

```text
services/pi/integrations/honeywell/
  -> services/pi/state/heating/build_heating_room_model.py
  -> EMS_HEATING_ROOM_MODEL_V0.1
```

There must not be a parallel `EMS_THERMAL_OBSERVER_V0.1` model describing the same room/setpoint reality.

The useful non-duplicated part of the old observer is the Quatt context used for later empirical thermal learning: electrical power, outside temperature, thermal power, COP and heating activity. Acquisition of that data is an integration responsibility and is therefore moved to:

`services/pi/integrations/quatt/collect_quatt_current.py`

The collector keeps the existing read-only `EMS_QUATT_CURRENT_STATE_V0.1` artifact and canonical SQLite metric writes. It performs no Quatt, Homey, Honeywell or OpenTherm control writes.

## Thermal Learning

Thermal Learning is not a second room model and is not a control layer. It will derive empirical observations from canonical history by correlating:

- `EMS_HEATING_ROOM_MODEL_V0.1` / Honeywell baseline and measured room state;
- Quatt telemetry archived in `ems-history.sqlite`;
- target-UP timing and magnitude;
- outside temperature and energy context;
- later rebound around the original Honeywell comfort moment.

Its purpose is to learn/validate room response to an advanced `+0.5 °C` target step and to test the provisional circa-three-hour preheat horizon. Until sufficient fine-grained data exists, no heat-up duration, COP, building-loss coefficient, room-response curve or `heatingPlanW` may be invented.

## Optimization objective

Heating Thermal Learning exists to determine whether the house can be used as
a useful thermal buffer for otherwise exported own PV energy.

The learning objective is not to maximize heating, preheat duration or
self-consumption in isolation. It is to establish empirically whether already
scheduled Honeywell heat demand can be advanced so that:

- otherwise exported own PV is absorbed as useful heat;
- Honeywell comfort remains the authority;
- useful temperature advantage remains around the original comfort moment;
- later heating demand is reduced or avoided;
- no material additional grid import is caused over the relevant thermal
  episode.

A reduction in PV export is therefore not by itself evidence of successful
thermal buffering. Earlier heating followed by comparable or greater
additional grid import later must not be learned as beneficial.

Episode evaluation must distinguish at least:

- room-temperature response;
- captured PV-export opportunity;
- retained useful heat around the original Honeywell comfort moment;
- later heating demand;
- grid import/export consequence over the complete evaluation window.

Honeywell room state and schedule are the core thermal evidence. Quatt
telemetry, P1/grid measurements, PV production and outside temperature are
contextual evidence. Missing or stale Quatt telemetry must not invalidate an
otherwise valid Honeywell thermal episode.

Thermal Learning remains READ_ONLY / SHADOW. It may derive empirical evidence
for later planner use, but it does not become a comfort authority, physical
writer or second energy planner.

## Thermal Learning Episodes V0.1

`services/pi/planner/heating/build_thermal_learning_episodes.py` builds
`EMS_HEATING_THERMAL_LEARNING_EPISODES_V0.1`.

This artifact is READ_ONLY / SHADOW empirical evidence for future heating
optimization. It is not a control plan and may not write Honeywell, Homey,
Quatt or any other physical device.

Architectural invariants:

- Honeywell `weeklySchedule` is the sole baseline transition authority.
- Historical `room_setpoint_c` is evidence only and must not create planned
  heating transitions.
- V0.1 creates episodes only for planned Honeywell target-UP transitions in
  the explicitly scoped rooms.
- Equal or downward target transitions do not create target-UP episodes.
- Honeywell room temperature and setpoint history are core thermal evidence.
- P1 import/export and PV production provide the energy consequence.
- Quatt telemetry is contextual evidence only; missing or stale Quatt data
  must not invalidate an otherwise valid Honeywell episode.
- Episode construction does not prove useful thermal buffering. New episodes
  remain `UNASSESSED` / `RAW_EPISODE_EVIDENCE_ONLY`.
- Reduced PV export alone is not success. Later heating demand, retained useful
  heat and grid import/export over the complete thermal episode must eventually
  be evaluated together.
- Intentional additional grid import is not an optimization objective and is
  explicitly disallowed by the V0.1 policy.
- Physical writes are explicitly disallowed.
- The artifact supplies evidence to future planner logic; it must not become a
  second comfort authority, control layer or energy planner.

The initial evidence window is three hours before through three hours after the
planned Honeywell UP transition. This is an observation window, not a learned
or fixed optimal preheat duration.

## Boundary with Heating Preheat V0.2

Heating Preheat V0.2 may use the canonical Heating Room Model for eligibility. Quatt telemetry is observational context for validation and future learning; it does not by itself make a room eligible and does not create new heat demand.

The Dynamic Pi Planner remains outside this migration. No files under `src/pi/ems-runtime/planner/` are moved or changed as part of the thermal consolidation.

## Repository migration rule

This migration applies the repository rule **“Touch it, place it correctly.”** The legacy `src/pi/ems-runtime/thermal/` source directory is removed after its responsibilities are either moved to their canonical integration location or explicitly superseded by the Heating Room Model.

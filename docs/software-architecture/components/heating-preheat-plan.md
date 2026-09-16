# Heating Preheat Plan

Status: **PLANNER / READ-ONLY / SHADOW**  
Schema: `EMS_HEATING_PREHEAT_PLAN_V0.1`

## Purpose

This planner models whether an upcoming Honeywell comfort-temperature increase could be advanced for shadow validation and visualisation. Honeywell remains the baseline comfort authority. The planner never writes Honeywell, Homey, OpenTherm, Quatt or another physical device.

## Baseline versus flexible heating

**Heating is baseline comfort unless forecast PV-export potential exists.**

The normal Honeywell schedule is part of the household comfort baseline and is not itself a flexible-load optimisation decision. Heating that would occur according to the unmodified Honeywell schedule must therefore be represented as baseline demand when the dynamic energy planner determines PV-export potential.

Only the *additional / earlier* heating caused by advancing an upcoming Honeywell `UP` transition is flexible demand. The dynamic planner may consider that advancement only when forecast PV-export potential exists and the advancement can absorb some of that otherwise exported PV.

Therefore:

- no forecast PV-export potential means **no heating-preheat opportunity**;
- absence of a preheat opportunity never suppresses, delays or otherwise changes baseline Honeywell comfort heating;
- the dynamic planner must not create grid import merely to preheat a room;
- only incremental preheat demand competes with WW and EV for available PV-export potential;
- normal Honeywell heating remains baseline comfort regardless of whether PV is available.

Conceptually:

```text
PV forecast
  - baseline household demand
  - baseline heating demand from the Honeywell comfort schedule
  = forecast PV-export potential

forecast PV-export potential > 0
  -> dynamic planner may evaluate flexible WW / heating-preheat / EV allocation

forecast PV-export potential <= 0
  -> no heating-preheat allocation; Honeywell baseline remains unchanged
```

The common PV signal belongs to the existing Dynamic Pi Planner. Heating must not introduce a parallel PV-opportunity forecast/schema. The dynamic planner already derives corrected export potential from the common PV, base-load, heating/Quatt and realtime P1 context; heating-preheat is an additional flexible-load candidate for that optimiser.

## Preheat candidate contract

A valid upcoming Honeywell `UP` transition may produce a shadow preheat candidate. The candidate describes the comfort transition that *could* be advanced; it does not independently claim or select a PV slot.

The candidate preserves at least:

- canonical room identity;
- Honeywell baseline/current target context;
- the later Honeywell target;
- the normal Honeywell `changeAt` time;
- transition direction `UP`;
- the permitted advancement boundary once that constraint is validated.

The heating layer must not invent thermal power, heat-up duration, building heat loss, COP or room thermal response. Those inputs require separate validation before the joint optimiser can make a defensible WW/heating/EV allocation.

## Dynamic-planner allocation principle

There is deliberately no fixed priority chain `WW -> heating -> EV` for opportunistic PV use. Hard comfort/deadline constraints are preserved first; within the remaining flexibility the Dynamic Pi Planner should allocate forecast PV-export potential jointly between flexible WW, heating-preheat and EV demand to maximise expected PV self-consumption.

Baseline heating is outside that competition. Only advancement above/before the Honeywell baseline enters the flexible-load optimisation.

## Comfort invariants

1. Only `direction = UP` can be considered for advancement.
2. `DOWN` and `NONE` are never advanced.
3. Candidate target equals the later Honeywell baseline target and can never exceed it.
4. Honeywell baseline time and target remain unchanged for audit and visualisation.
5. Preheat is only relevant to the dynamic planner when forecast PV-export potential exists.
6. Preheat must not intentionally create grid import; without PV-export potential the candidate receives no preheat allocation.
7. Baseline Honeywell heating is comfort demand and must never be suppressed or delayed because PV-export potential is absent.
8. All schedule timestamps must be offset-aware; top-level timezone remains `Europe/Amsterdam`.
9. Invalid or ambiguous source/time semantics fail closed.
10. No actuator command or physical write exists in this increment.

## Architectural position

```text
Honeywell comfort schedule
          |
          +--> baseline heating demand -------------------+
          |                                               |
          v                                               v
EMS_HEATING_ROOM_MODEL_V0.1                    Dynamic Pi baseline/export model
          |                                               |
          v                                               |
EMS_HEATING_PREHEAT_PLAN_V0.1                  forecast PV-export potential
   (UP candidate only)                                     |
          |                                               |
          +---------------------> joint flexible optimiser |
                                   WW / heating / EV <-----+
                                            |
                                            +--> shadow allocation / visualisation
                                            |
                                            v
                                  future thermal validation /
                                  guarded heating control
```

Canonical implementation: `services/pi/planner/heating/`. Canonical tests: `tests/planner/heating/`.

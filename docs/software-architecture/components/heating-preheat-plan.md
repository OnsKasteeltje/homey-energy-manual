# Heating Preheat Plan

Status: **PLANNER / READ-ONLY / SHADOW**  
Schema: `EMS_HEATING_PREHEAT_PLAN_V0.2`

## Purpose

Heating Preheat is the PV-voorverwarming function within the **Ruimteverwarming** domain. It determines whether an already planned Honeywell comfort-temperature increase may be advanced for shadow validation and visualisation. Honeywell remains the baseline comfort authority. The planner never writes Honeywell, Homey, OpenTherm, Quatt or another physical device.

Canonical domain design: `docs/software-architecture/components/space-heating.md`.

## V0.2 scope

PV-preheat scope is deliberately limited to:

- `woonkamer`;
- `eetkamer`;
- `keuken`;
- `serre`.

`woonkamer` and `eetkamer` are tagged as the common `living_area` planning group because they are physically connected and should later be evaluated jointly at source level. This grouping does not invent a thermodynamic coupling coefficient.

All other Honeywell rooms remain normal baseline/comfort rooms but are outside PV-preheat optimisation until explicitly added.

## Baseline versus flexible heating

**All normal heating is Honeywell baseline/comfort demand.** EMS creates no new heat demand.

Only the earlier timing caused by advancing an existing future Honeywell `UP` transition is flexible. No PV opportunity means no preheat; it never suppresses or delays normal Honeywell heating.

The common PV-export opportunity belongs to the existing Dynamic Pi Planner. Heating does not own a separate PV pot or PV-opportunity schema. Flexible WW, heating-preheat and EV compete jointly for the same remaining forecast PV export while hard comfort/deadline constraints remain feasible. There is no rigid WW -> heating -> EV priority.

## V0.2 eligibility

A room is an eligible shadow candidate only when all of the following are true:

1. the room is explicitly in PV-preheat scope;
2. the next Honeywell baseline transition is `UP`;
3. that transition is not in the past and is at most **180 minutes** away;
4. measured current room temperature is below the future Honeywell target.

The 180-minute horizon is a provisional SHADOW guidance bound based on current household observations and coarse historic Homey data. It is not a learned thermal constant and is not a target to always advance by three hours.

If measured room temperature is already at or above the future Honeywell target, there is no current heat demand and the candidate fails closed with `NO_HEAT_DEMAND_AT_CURRENT_TEMPERATURE`, regardless of forecast PV export.

## 0.5 C advancement steps

Any future Honeywell `UP` may be a preheat candidate regardless of the total size of that scheduled increase. The **0.5 C limit applies to each EMS preheat increment**, not to the size of the Honeywell `UP` itself.

When a larger Honeywell `UP` is actually considered for advancement, V0.2 decomposes the rise into setpoint building blocks of at most **0.5 C**. This supports gradual heating so the Quatt can carry the additional load without unnecessarily provoking CV assistance.

The normal Honeywell schedule is never rewritten. Steps already satisfied by measured room temperature are omitted. The final candidate target never exceeds the later Honeywell baseline target.

Example: baseline target 15.5 C, actual room temperature 17.2 C, future Honeywell target 19.0 C produces shadow candidate setpoints `17.5, 18.0, 18.5, 19.0 C`.

For V0.3 and later guarded execution, the intended step semantics are stricter:

- after selecting a `+0.5 C` preheat step, the controller waits until the measured room temperature has reached that active preheat target within a small validated tolerance;
- no subsequent `+0.5 C` step is allowed before that proof exists;
- for a grouped opportunity such as Woonkamer + Eetkamer, all selected rooms must have reached their active preheat targets before a next grouped step;
- CV activity is checked on every active-preheat evaluation iteration, not only after target attainment.

V0.2 does **not** determine the time spacing between these steps. Timing must remain evidence-based and gated by measured step completion, remaining opportunity window, planner priority and safety state rather than by a guessed fixed interval.

## Baseline heating versus pure EMS preheat

Heating Preheat V0.3 must explicitly distinguish normal Honeywell comfort demand from incremental EMS-created preheat demand.

Conceptually, the planner/control layer derives a house-wide `baselineHeatingDemandPresent` signal from the current Honeywell baseline targets and measured room temperatures, using a small validated tolerance/hysteresis.

The target semantics are:

```text
baselineHeatingDemandPresent = true
  -> BASELINE_HEATING
  -> no new EMS preheat increment
  -> CV activity is normal comfort heating, not a preheat fault

baselineHeatingDemandPresent = false
+ preheatActive = true
+ CV heating active
  -> CV_ASSIST_DURING_PURE_PREHEAT
  -> block all further EMS preheat increments
  -> retain the event for Thermal Learning / validation

now >= originalHoneywellUpAt
  -> end PREHEAT state
  -> Honeywell baseline resumes full ownership
  -> later CV activity belongs to normal baseline heating
```

Preheat therefore exists only while the EMS is intentionally holding an advanced target above the currently active Honeywell baseline before the original Honeywell `UP`, with normal baseline comfort already satisfied.

This distinction is a **design objective for V0.3+**. It does not change the current V0.2 READ_ONLY/SHADOW safety boundary.

## Output and planner boundary

V0.2 emits per room at least:

- current measured temperature;
- current and future Honeywell baseline target;
- original Honeywell `changeAt`;
- `earliestStartAt = changeAt - 180 minutes`;
- scope and optional group;
- eligibility status and reason;
- candidate `steps_C`;
- `startAt = null` until the Dynamic Pi Planner evaluates common PV-export opportunity.

The heating layer does not select PV slots, estimate heating watts, invent COP, heat-up duration, building heat loss or room response. Those remain outside the model until supported by measurements.

## PV allocation invariant

A V0.2 eligible candidate means only **thermally/schedule eligible for evaluation**. It is not permission to heat.

The Dynamic Pi Planner may select advancement only from **remaining forecast PV-export potential after baseline demand**. Preheat must not intentionally create grid import. Only incremental advanced heating competes with WW and EV.

## Rebound validation

PV capture during preheat is insufficient proof of useful thermal buffering. Validation must also determine whether heating around the original Honeywell comfort time was reduced or avoided. Otherwise energy may merely be consumed both earlier and later.

Future visualisation/validation should therefore correlate:

- Honeywell baseline target;
- EMS shadow advanced target;
- measured room temperature;
- PV export absorbed during the candidate window;
- heating/Quatt behaviour near the original comfort time;
- remaining grid export/import.

## Thermal Learning

Historic Homey year exports are useful for coarse seasonal behaviour but are aggregated to multi-hour blocks and cannot establish reliable 0.5 C response times. The initial 180-minute horizon therefore remains provisional.

When active heating resumes, fine-grained observations should be retained on the Pi before Homey aggregates them. Useful learning inputs include Honeywell target, measured room temperature, Quatt activity/electrical power, outside temperature and P1 energy context.

Initial learning focus is Woonkamer/Eetkamer, followed by validation against Keuken and Serre. The objective is to learn response/retention behaviour and later replace provisional timing guidance with evidence-based parameters.

## Safety invariants

- `READ_ONLY / SHADOW` only;
- Honeywell remains baseline/comfort authority;
- only `UP` may be advanced;
- `DOWN` and `NONE` are never advanced;
- no target above the future Honeywell target;
- no intentional grid import for preheat;
- no new EMS preheat increment while normal Honeywell baseline demand is present;
- CV activity during pure EMS preheat blocks further preheat increments, while CV activity for baseline comfort is not treated as a preheat fault;
- no physical write or actuator command;
- timestamps remain offset-aware in `Europe/Amsterdam`;
- invalid/ambiguous source or time semantics fail closed.

## Architectural position

```text
Honeywell schedule + current room state
                |
                v
EMS_HEATING_ROOM_MODEL_V0.1
                |
                v
EMS_HEATING_PREHEAT_PLAN_V0.2
(scope / actual-temp / <=3h / <=0.5C candidate steps)
                |
                v
Dynamic Pi Planner
(common residual PV-export allocation: WW / heating-preheat / EV)
                |
                v
SHADOW allocation + visualisation + rebound validation
                |
                v
future guarded control only after explicit validation
```

Canonical implementation: `services/pi/planner/heating/`. Canonical tests: `tests/planner/heating/`.

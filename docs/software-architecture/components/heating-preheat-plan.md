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

## V0.3 shadow preparation

The next safe increment is implemented as a **separate read-only shadow layer** rather than changing V0.2 eligibility or adding Honeywell writes.

Canonical implementation:

- `services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py`;
- `services/pi/planner/heating/run_heating_preheat_shadow_v0_3.py`;
- derived runtime artifact: `/home/jeroen/ems/data/heating-preheat-shadow-v0.3.json`.

The runner consumes only already collected local Pi artifacts:

- canonical Honeywell schedule;
- canonical Honeywell current room state;
- Heating Room Model V0.1;
- Heating Preheat Plan V0.2;
- read-only Quatt current state.

It performs **no Homey call and no device write**. The five-minute shadow cadence is deliberately scheduled after the existing Honeywell-state and Quatt-current collectors.

For CV-assist observation V0.3 uses the existing Quatt observer-only field `observerOnly.boilerAssistOn`. Missing, invalid or stale Quatt current state blocks a new shadow preheat increment; it does not alter normal Honeywell baseline heating.

V0.3 derives house-wide `baselineHeatingDemandPresent` from all canonical Honeywell rooms, not only the four preheat rooms. Until Thermal Learning validates a suitable tolerance/hysteresis, V0.3 deliberately uses an exact/conservative comparison rather than inventing a thermal tolerance.

V0.3 does **not** grant heating opportunity itself. Each room exposes `plannerGrant = NOT_EVALUATED`, no active physical step, the next thermally legal `+0.5 C` step and `opportunityClosesAt`. Central Heating/EV/WW priority remains a later Dynamic Pi Planner responsibility.

## V0.4 stateful progression SHADOW

Heating Preheat V0.4 is a separate downstream state machine. It does **not** modify V0.3 eligibility and does not create a physical Honeywell target.

Canonical implementation:

- `services/pi/planner/heating/build_heating_preheat_progression_shadow_v0_4.py`;
- `services/pi/planner/heating/run_heating_preheat_progression_shadow_v0_4.py`;
- derived runtime artifact: `/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json`.

Inputs are deliberately limited to:

1. Heating Preheat V0.3 eligibility/safety;
2. Flex Priority Shadow V0.1 central Heating↔EV grant;
3. the previous local V0.4 shadow artifact for state persistence.

V0.4 therefore sits **after** central arbitration and cannot become a second planner.

A new shadow step starts only when V0.3 says `PREHEAT_READY_FOR_GRANT`, Flex Priority grants Heating, the room is in the granted ready-room set and both source artifacts are fresh and ordered consistently. The active step is a hypothetical/would-command target only; `physicalWritePerformed=false` is part of every room state.

Once a shadow step is active:

- its target remains fixed while measured room temperature is below that target;
- no subsequent step is allowed until the measured room temperature has reached the active target;
- a subsequent target increases by at most `+0.5 C` and never exceeds the future Honeywell target;
- loss of planner grant holds the existing progression and forbids advancement;
- CV-assist or unknown CV state inherits the V0.3 block and forbids advancement;
- normal baseline heating ends the preheat progression because it is no longer pure preheat;
- for a selected room group such as Woonkamer + Eetkamer, no member advances until all selected members with active steps have reached their current target.

V0.4 intentionally does **not** define LIVE rollback semantics when planner grant disappears or a guard trips. It records `rollbackBehavior = NOT_DEFINED_SHADOW_ONLY` rather than inventing actuator behaviour before a guarded Honeywell writer exists.

The V0.4 minute cadence is Pi-local only and performs no Homey call. It accepts V0.3 only within its bounded freshness horizon and accepts Flex Priority only when the priority artifact is fresh and was generated at or after the V0.3 state it is granting. Otherwise progression fails closed to a waiting/hold state.

## PV Flex observability

Frontend V2 PV & Flex exposes the current V0.3 shadow state through the read-only Web Data API endpoint `/web/planner/heating-preheat-shadow`.

The PV Flex page must show, per scoped room:

- current measured temperature;
- current Honeywell baseline;
- next Honeywell UP target;
- next shadow preheat step;
- advancement window;
- baseline-heating/CV guard state;
- central planner grant state and decision reason.

This is presentation only. The Web Data API remains allowlist-only and has no control route. Missing Heating Preheat shadow data must degrade only this panel and must not break PV/EV observability.

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
Flex Priority Shadow
(common residual PV opportunity: heating-preheat / EV)
                |
                v
Heating Preheat Progression V0.4 SHADOW
(stateful <=0.5C would-command steps; measured completion proof)
                |
                v
SHADOW visualisation + rebound validation
                |
                v
future guarded control only after explicit validation
```

Canonical implementation: `services/pi/planner/heating/`. Canonical tests: `tests/planner/heating/`.

# Heating Preheat Plan

Status: **PLANNER / READ-ONLY / SHADOW**  
Schema: `EMS_HEATING_PREHEAT_PLAN_V0.1`

## Purpose

The Heating Preheat Plan is the first planner layer above `EMS_HEATING_ROOM_MODEL_V0.1`. It represents a possible advancement of an upcoming Honeywell comfort-temperature increase for validation and visualisation only.

It does not write to Honeywell, Homey, OpenTherm, Quatt or another physical device.

Honeywell remains the baseline comfort authority.

## Architectural position

```text
EMS_HEATING_ROOM_MODEL_V0.1
          |
          v
EMS_HEATING_PREHEAT_PLAN_V0.1
       SHADOW ONLY
          |
          +--> future PV opportunity evaluation
          |
          +--> baseline vs candidate visualisation
          |
          v
future guarded heating control
```

Canonical implementation belongs under `services/pi/planner/heating/`. Tests belong under `tests/planner/heating/`.

## V0.1 contract

V0.1 establishes the candidate contract before PV-opportunity logic is added. A candidate may exist only for a room whose next Honeywell baseline transition is `UP`.

Illustrative shape:

```json
{
  "schema": "EMS_HEATING_PREHEAT_PLAN_V0.1",
  "mode": "READ_ONLY",
  "controlMode": "SHADOW",
  "generatedAt": "2026-09-15T21:45:00Z",
  "timezone": "Europe/Amsterdam",
  "baselineAuthority": "HONEYWELL",
  "sourceRoomModelSchema": "EMS_HEATING_ROOM_MODEL_V0.1",
  "rooms": [
    {
      "key": "woonkamer",
      "baseline": {
        "changeAt": "2026-09-16T17:30:00+02:00",
        "targetTemperature_C": 19.0,
        "direction": "UP"
      },
      "candidate": {
        "status": "ELIGIBLE_UP_TRANSITION",
        "startAt": null,
        "targetTemperature_C": 19.0,
        "reason": "AWAITING_OPPORTUNITY_EVALUATION"
      }
    }
  ]
}
```

`startAt` is deliberately `null` in this contract-only phase. Choosing an earlier start requires the later PV/opportunity planner increment.

Rooms without an upcoming `UP` transition remain represented but are not eligible for advancement.

## Comfort invariants

1. Only a Honeywell baseline transition with `direction = UP` can become a preheat candidate.
2. A `DOWN` or `NONE` transition is never advanced.
3. Candidate target temperature equals the later Honeywell baseline target; it may never exceed it.
4. The original Honeywell baseline transition time and target are retained unchanged for audit and visualisation.
5. Any future non-null candidate `startAt` must be earlier than or equal to the Honeywell baseline `changeAt` and must use an offset-aware timestamp resolved for `Europe/Amsterdam`.
6. Missing, stale, invalid or ambiguous room-model input fails closed to no actionable candidate.
7. V0.1 contains no actuator command and performs no physical write.

## Candidate states

The contract uses explicit states rather than inferring intent from missing values:

- `ELIGIBLE_UP_TRANSITION`: valid upcoming Honeywell increase; opportunity evaluation has not yet selected a start time.
- `NOT_ELIGIBLE`: baseline direction is `DOWN` or `NONE`.
- `INVALID_SOURCE`: source room model cannot be trusted; fail closed.

During this first increment an eligible candidate has:

```text
startAt = null
reason  = AWAITING_OPPORTUNITY_EVALUATION
```

No PV forecast, tariff or energy-price input is consumed yet.

## Next increment

A later shadow planner increment may combine an eligible `UP` transition with PV forecast, room state and explicit planner constraints to choose a non-null earlier `startAt`.

That increment must preserve this contract's baseline fields and comfort invariants. It remains shadow-only until its behaviour has been validated against actual room and energy data.

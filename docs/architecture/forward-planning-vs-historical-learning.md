# Forward planning versus historical learning

Status: **canonical architecture boundary**

The EMS maintains a strict architectural and presentation boundary between forward planning and historical learning.

## User-facing time perspectives

Frontend V2 distinguishes three questions:

- **Live** — what is happening now?
- **PV Flex / Planner** — what does the EMS expect and plan from NOW forward?
- **Analysis** — what actually happened, how did plan and realization differ, and what can the EMS learn from historical evidence?

PV Flex / Planner is therefore a forward-looking surface. Historical learning episodes, retrospective evidence and model-learning diagnostics do not belong on that page. Historical information may appear there only after it has been reduced to an explicitly defined and sufficiently validated parameter or state that is relevant to a future planning decision.

Analysis is the canonical retrospective surface. It may combine, over time, forecast-versus-actual PV, planner-versus-realization, EV charging, hot-water performance, space-heating response and thermal-buffer learning.

## Forward plane

```text
current state + forecast + validated learned parameters
    -> planner
    -> future plan
    -> PV Flex / Planner
```

The forward plane exists for prediction and planning. It must not expose raw historical learning episodes as if they were future planner decisions.

## Learning plane

```text
historical measurements + historical plans + realization
    -> episode/evidence construction
    -> retrospective assessment
    -> validated learned parameters
```

The learning plane exists for observation, validation and learning. Raw observations, SHADOW assessments and unvalidated conclusions do not become control inputs merely because they exist.

## Boundary between the planes

The learning plane does not directly control physical devices and does not become a second planner.

Information may cross from the learning plane into the forward plane only as an explicitly defined and sufficiently validated learned parameter or policy input. The forward planner remains responsible for applying that information together with current state, forecast, comfort constraints and energy policy.

For Heating Thermal Learning this means that historical thermal episodes belong to Analysis. A future empirically supported parameter such as a useful advancement horizon for a room may become planner input only after its validation rules are defined and satisfied.

This separation preserves the distinction between:

- **evidence** — what happened;
- **learning** — what historical evidence supports;
- **planning** — what should happen next;
- **control** — what is actually written to devices.

## Presentation invariant

The normal frontend must preserve the same time-direction distinction:

**Live = now -> PV Flex / Planner = forward -> Analysis = retrospective learning.**

Diagnostics may expose deeper evidence when explicitly requested, but diagnostic detail must not blur the normal forward-planning surface or imply that an unvalidated learning result is an active planner decision.

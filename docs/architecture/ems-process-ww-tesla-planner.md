# EMS process — Warm Water, Tesla and Planner

Status: current production architecture reference  
Date: 2026-09-12

This diagram captures the current Pi/Homey EMS process for warm water (WW), Tesla EV charging and the quarter-hour planner after the controlled Pi cutover.

```mermaid
flowchart TB
  subgraph I[1. Data & inputs]
    H[Homey real-time\nPV, grid, devices]
    HD[Homey day history\n5-min measurements]
    PVI[PV / weather forecast]
    TI[Tesla\nSoC, connected, deadline, target]
    WI[Warm water\nmode, state, requirement]
    CP[Fixed ENGIE contract policy]
  end

  DB[(SQLite\noperational historical database)]

  H --> DB
  HD --> DB
  TI --> DB
  WI --> DB

  subgraph F[2. Forecasts]
    PF[PV forecast\n15-min]
    CB[Clean base history\nfrom SQLite]
    BF[Base-load forecast]
    WWF[WW requirement / forecast]
    TIF[Tesla energy need / deadline]
  end

  PVI --> PF
  DB --> CB --> BF
  WI --> WWF
  TI --> TIF

  subgraph PL[3. Pi dynamic planner]
    QP[Hardened dynamic planner v0.3\n96 action slots / 24h\nmultiday WW lookahead\nfixed ENGIE production policy]
    CC[/Pi /control/current\ntechnical READY + current command/]
  end

  PF --> QP
  BF --> QP
  WWF --> QP
  TIF --> QP
  CP --> QP
  QP --> CC

  subgraph A[4. Single authority boundary in Homey]
    SEL{EM2_Planner_Authority}
    PIB[PI Dynamic Planner Bridge v1.2.4]
    HB[Guarded Homey producer\nrollback path]
    INT[EM2_Power_Intent v0.2]
  end

  CC --> PIB
  SEL -->|PI| PIB
  SEL -->|HOMEY| HB
  PIB --> INT
  HB --> INT

  subgraph E[5. Homey executor / safety layer]
    EVA[EV Power Adapter v0.1.4\nSTART7 / RUN6]
    EVG[EV Gate v0.2.5\nhealth observability-only]
    EVA2[EV Actuator v0.2.6\nEasee session + current]
    WWA[WW Power Adapter v0.2]
    WWG[WW Gate v0.2]
    WWA2[WW Actuator v0.9\nsole boiler writer]
    EH[Easee Device Health v0.2\nobservability]
  end

  INT --> EVA --> EVG --> EVA2
  INT --> WWA --> WWG --> WWA2
  EH -. diagnostic only .-> EVG

  subgraph D[6. Physical devices]
    TES[Easee / Tesla]
    BOI[Boiler]
  end

  EVA2 --> TES
  WWA2 --> BOI

  subgraph M[7. Monitoring & feedback]
    LOG[Logging / SQLite history]
    EVS[EV control-status evidence]
    WEB[Pi planner website\nforecast + planned windows]
    EVAL[Compare forecast / plan / reality]
  end

  TES --> LOG
  BOI --> LOG
  EVG --> EVS
  EVA2 --> EVS
  QP --> WEB
  LOG --> EVAL --> DB

  PRI[Priority principles\n1. Safety / hard device limits\n2. WW comfort and readiness\n3. Tesla explicit deadline / target\n4. Maximise useful PV self-consumption\n5. Avoid unnecessary grid import/export\n6. No competing battery optimiser]
  PRI -. governs .-> QP
```

## Operational principles

- **Pi is the active planner authority** while `EM2_Planner_Authority = PI`.
- **Homey is executor and local safety layer.** The Pi planner does not write devices directly.
- **There is one authority selector.** `EM2_Planner_Authority` is the sole HOMEY↔PI planner gate; `control-authority.json` is configuration/diagnostic context, not a second cutover gate.
- **`/control/current` is readiness + command.** It validates the Pi plan and fixed-contract boundary and returns only the current slot command.
- **SQLite is the operational historical database on the Pi.** JSON/GitHub publication files are derived state or evidence.
- **WW:** comfort/readiness requirements win. The planner prefers useful PV and avoids unnecessary repeat heating after the daily goal.
- **Tesla:** deadline/target requirements are hard constraints. Opportunity charging uses residual PV. The active actuator uses START7/RUN6 semantics.
- **Easee health:** the current capability-timestamp health heuristic is observability-only at EV Gate v0.2.5 and does not independently veto a coherent positive command.
- **Execution is fail-safe.** EV/WW adapters and gates require coherent schemas/revisions and the actuators remain the only physical writers.
- **Future battery:** Victron DESS remains the primary real-time battery optimiser; Pi/Homey must not create a competing real-time battery optimiser.

## Validated live command paths — 2026-09-12

Tesla:

`Pi 4830 W / 7 A → PI bridge → Power Intent → EV adapter → Gate PASS → EV actuator → Easee ~4.9 kW`, followed by Pi return to `0 A` and physical pause.

Result: **ON/OFF PASS.**

Warm water:

`Pi WW ON → PI bridge → Power Intent → WW adapter → Gate PASS → WW actuator → boiler ~2.03 kW`, followed by restore to normal Pi target and physical `0 W`.

Result: **ON/OFF PASS.**

## Data flow summary

`Homey/history → SQLite → forecasts/requirements → Pi dynamic planner → /control/current → Homey authority selector + PI bridge → canonical Power Intent → adapters/gates → physical actuators → logging/website/evidence → feedback`

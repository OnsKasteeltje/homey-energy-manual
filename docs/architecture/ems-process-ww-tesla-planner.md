# EMS process — Warm Water, Tesla and Planner

Status: project architecture reference  
Date: 2026-09-06

This diagram captures the current Pi/Homey EMS process for warm water (WW), Tesla EV charging and the quarter-hour planner. It is intended as the maintainable source-of-truth diagram for the project.

```mermaid
flowchart TB
  %% INPUTS
  subgraph I[1. Data & inputs]
    H[Homey real-time\nPV, grid, devices]
    HD[Homey day history\n5-min measurements]
    PVI[PV / weather forecast]
    TI[Tesla\nSoC, connected, deadline, target]
    WI[Warm water\nmode, state, requirement]
    PR[Tariff / price input\noptional]
  end

  DB[(SQLite\noperational historical database)]

  H --> DB
  HD --> DB
  TI --> DB
  WI --> DB
  PVI --> PF
  PR --> QP

  %% FORECASTS
  subgraph F[2. Forecasts]
    PF[PV forecast\n24h / 15-min]
    CB[Clean base history\nfrom SQLite]
    BF[Base-load forecast v0.2\nquarter × day type × season]
    WWF[WW input / forecast\nflexibility + requirement]
    TIF[Tesla input\nenergy need + deadline]
  end

  DB --> CB --> BF
  WI --> WWF
  TI --> TIF

  %% PLANNER
  subgraph PL[3. Quarter-hour planner]
    QP[Combine PV + base load + WW + Tesla\nApply hard constraints and priorities\nBuild 96-slot shadow plan]
  end

  PF --> QP
  BF --> QP
  WWF --> QP
  TIF --> QP

  %% DECISIONS
  subgraph C[4. Control logic]
    RT[Current state\nHomey measurements + status]
    DEC{Plan still valid\nand safe?}
    WWC[WW control\nmeet comfort/deadline\nprefer PV opportunity]
    TEC[Tesla control\ndeadline charging first\notherwise PV opportunity]
    HOLD[Hold / no action\nrespect hysteresis, leases, limits]
  end

  QP --> DEC
  H --> RT --> DEC
  DEC -->|WW action| WWC
  DEC -->|Tesla action| TEC
  DEC -->|No justified change| HOLD

  %% EXECUTION
  subgraph E[5. Execution via Homey]
    WWA[Boiler / warm-water actuator]
    TEA[Easee / Tesla charging actuator]
  end

  WWC --> WWA
  TEC --> TEA

  %% FEEDBACK
  subgraph M[6. Monitoring & feedback]
    LOG[Logging / SQLite history]
    WEB[Pi Planner website\nforecast + planned windows]
    EVAL[Compare forecast / plan / reality\nbacktest and improve with more history]
  end

  WWA --> LOG
  TEA --> LOG
  RT --> LOG
  QP --> WEB
  LOG --> EVAL
  EVAL --> DB

  %% PRIORITY NOTES
  PRI[Priority principles\n1. Safety / hard device limits\n2. WW comfort and required readiness\n3. Tesla explicit deadline / target\n4. Use PV for flexible load\n5. Minimise avoidable grid import/export\n6. No competing battery optimiser]
  PRI -. governs .-> QP
  PRI -. governs .-> DEC
```

## Operational principles

- **SQLite is the only operational historical database on the Pi.** GitHub/JSON history is bootstrap or publication output, not a live planner database.
- **Planner and control are separated.** The planner proposes quarter-hour intent; Homey/runtime control validates the current situation before actuating devices.
- **WW:** hard comfort/readiness requirements win. Once the daily goal is reached, unnecessary reheating should be avoided; surplus-PV heating is an opportunity, not a comfort violation.
- **Tesla:** an explicit departure deadline/target SoC is a hard planning requirement. Outside deadline charging, PV-opportunity charging is preferred and anti-flapping/hysteresis remains active.
- **Base load:** controllable loads and Quatt are removed before forecasting, preventing double counting when WW or Tesla are added back by the planner.
- **Forecast learning:** base-load forecast v0.2 uses quarter-hour + day type + seasonal analogues with graceful fallback. It remains measurable/backtestable while history accumulates.
- **Execution is fail-safe and idempotent.** A plan does not itself force a device write; current state, safety limits and leases/hysteresis are checked first.
- **Future battery:** Victron DESS remains the primary battery optimiser; the Pi planner should expose future household/flexible-load intent, not compete with DESS in real time.

## Data flow summary

`Homey/history → SQLite → clean base history → base-load + PV + WW + Tesla forecasts → 96-slot planner → runtime validation → Homey actuation → logging/website → feedback`

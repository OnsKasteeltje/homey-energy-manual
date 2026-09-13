---
component: tesla
title: Tesla procesflows
version: 3.0.0
status: active
architecture_status: implemented-production
last_verified: 2026-09-13
source:
  - docs/architecture/CURRENT-EMS-STATE.md
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6
  - Homey Advanced Flow: EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6
  - Homey Advanced Flow: EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION
  - Homey Advanced Flow: EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]
---

# Tesla procesflows

## Productieketen

```process-model
{
  "id": "tesla-flow-production",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Pi dynamic planner v0.3] --> B[Pi /control/current]",
    "    B --> C[PI Bridge v1.2.6]",
    "    C --> D[EM2_POWER_INTENT_V0.2]",
    "    D --> E[EV Power Adapter v0.1.5]",
    "    E --> F[EV Gate v0.2.6]",
    "    F -->|PASS| G[EV Actuator v0.2.7]",
    "    F -->|FAIL| H[Fail closed / no positive write]",
    "    G --> I[Easee session/current]",
    "    I --> J[Tesla]"
  ]
}
```

<!-- GENERATED_MERMAID:tesla-flow-production START -->
```mermaid
flowchart TD
    A[Pi dynamic planner v0.3] --> B[Pi /control/current]
    B --> C[PI Bridge v1.2.6]
    C --> D[EM2_POWER_INTENT_V0.2]
    D --> E[EV Power Adapter v0.1.5]
    E --> F[EV Gate v0.2.6]
    F -->|PASS| G[EV Actuator v0.2.7]
    F -->|FAIL| H[Fail closed / no positive write]
    G --> I[Easee session/current]
    I --> J[Tesla]
```
<!-- GENERATED_MERMAID:tesla-flow-production END -->

## Opportunity policy

```process-model
{
  "id": "tesla-flow-opportunity",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Residual PV after WW reservation] --> B{Positive 15-min slot?}",
    "    B -->|No| C[Target 0 W]",
    "    B -->|Yes| D{Executable at >= 3x6A?}",
    "    D -->|No| C",
    "    D -->|Yes| E[Publish EV target_W]",
    "    E --> F[Following quarter re-evaluated independently]"
  ]
}
```

<!-- GENERATED_MERMAID:tesla-flow-opportunity START -->
```mermaid
flowchart TD
    A[Residual PV after WW reservation] --> B{Positive 15-min slot?}
    B -->|No| C[Target 0 W]
    B -->|Yes| D{Executable at >= 3x6A?}
    D -->|No| C
    D -->|Yes| E[Publish EV target_W]
    E --> F[Following quarter re-evaluated independently]
```
<!-- GENERATED_MERMAID:tesla-flow-opportunity END -->

START6/RUN6 is productiegedrag. Nominaal minimum uitvoerbaar vermogen is 4140 W bij 3×230 V. Goedkope of negatieve dynamische prijs is onder FIXED geen opportunity-trigger.

## Deadline policy

```process-model
{
  "id": "tesla-flow-deadline",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Active deadline + remaining kWh] --> B{Tesla connected?}",
    "    B -->|No| C[Wait / no forced target]",
    "    B -->|Yes| D{Before latest_start_at?}",
    "    D -->|Yes| E[Only normal PV opportunity may charge]",
    "    D -->|No| F[Deadline MUST may use grid]",
    "    F --> G[Homey bridge deadline guard as final safety]",
    "    G --> H[Clamp to configured max A]"
  ]
}
```

<!-- GENERATED_MERMAID:tesla-flow-deadline START -->
```mermaid
flowchart TD
    A[Active deadline + remaining kWh] --> B{Tesla connected?}
    B -->|No| C[Wait / no forced target]
    B -->|Yes| D{Before latest_start_at?}
    D -->|Yes| E[Only normal PV opportunity may charge]
    D -->|No| F[Deadline MUST may use grid]
    F --> G[Homey bridge deadline guard as final safety]
    G --> H[Clamp to configured max A]
```
<!-- GENERATED_MERMAID:tesla-flow-deadline END -->

## Adapter en gate

```process-model
{
  "id": "tesla-flow-adapter-gate",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[EV target_W] --> B[Adapter: floor target / 3x230]",
    "    B --> C{requested_A >= 6?}",
    "    C -->|No| D[0 A]",
    "    C -->|Yes| E[Clamp to safe max]",
    "    D --> F[Gate validation]",
    "    E --> F",
    "    F --> G{schema + revision + freshness + mapping valid?}",
    "    G -->|No| H[FAIL closed]",
    "    G -->|Yes| I[PASS to single actuator]"
  ]
}
```

<!-- GENERATED_MERMAID:tesla-flow-adapter-gate START -->
```mermaid
flowchart TD
    A[EV target_W] --> B[Adapter: floor target / 3x230]
    B --> C{requested_A >= 6?}
    C -->|No| D[0 A]
    C -->|Yes| E[Clamp to safe max]
    D --> F[Gate validation]
    E --> F
    F --> G{schema + revision + freshness + mapping valid?}
    G -->|No| H[FAIL closed]
    G -->|Yes| I[PASS to single actuator]
```
<!-- GENERATED_MERMAID:tesla-flow-adapter-gate END -->

Mappingcontract: `FLOOR_3P230_START6_RUN6_FAIL_CLOSED`.

## Fysieke writer

```process-model
{
  "id": "tesla-flow-writer",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Validated EV gate command] --> B{Target > 0?}",
    "    B -->|No| C[Pause/0A idempotently if needed]",
    "    B -->|Yes| D[Ensure Easee session active/resumed]",
    "    D --> E[Set requested current if changed]",
    "    E --> F[Publish actuator status]"
  ]
}
```

<!-- GENERATED_MERMAID:tesla-flow-writer START -->
```mermaid
flowchart TD
    A[Validated EV gate command] --> B{Target > 0?}
    B -->|No| C[Pause/0A idempotently if needed]
    B -->|Yes| D[Ensure Easee session active/resumed]
    D --> E[Set requested current if changed]
    E --> F[Publish actuator status]
```
<!-- GENERATED_MERMAID:tesla-flow-writer END -->

De EV actuator is de enige automatische physical Easee writer. Het oude `Tesla laden v2.7.15` pad is geen actuele productiearchitectuur meer.
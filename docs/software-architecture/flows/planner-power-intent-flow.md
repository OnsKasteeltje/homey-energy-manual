---
title: Planner and Power Intent Flows
status: implemented-shadow
last_verified: 2026-08-25
---

# Planner and Power Intent Flows

## 1. 24h Planner

```mermaid
flowchart TD
    A[Every 15 min + 45 s delay] --> B[Read EM2_State / WW / Price Context]
    B --> C{Price context usable?}
    C -->|No| D[Planner status DEGRADED_PRICE_CONTEXT]
    C -->|Yes| E[Build 15-min price slots]
    E --> F[Rank Tesla slots before deadline]
    E --> G[Allocate WW slots before 19:00]
    E --> H[Calculate theoretical battery charge/discharge candidates]
    F --> I[Publish EM2_Energy_Plan_24h]
    G --> I
    H --> I
    D --> I
    I --> J[No physical writes]
```

## 2. Power Intent revision guard

```mermaid
flowchart TD
    A[EM2_Public_State changed] --> B[Read Public State, State, Decision, WW Control]
    B --> C{All source revisions aligned?}
    C -->|No| D[valid=false\nREVISION_MISMATCH\nEV target 0 W]
    C -->|Yes| E[Project Core policy]
    E --> F[Calculate EV target_W]
    E --> G[Project WW target_on]
    F --> H[Publish EM2_Power_Intent v0.2]
    G --> H
```

## 3. EV target projection

```mermaid
flowchart TD
    A[Aligned Core Decision] --> B{Intent}
    B -->|TESLA_CHARGE_DEADLINE| C{remaining kWh + deadline valid?}
    C -->|Yes| D[target_W = remaining/time]
    C -->|No| E[target_W = 0]
    B -->|TESLA_CHARGE_OPPORTUNITY| F{flex budget >= 800 W?}
    F -->|Yes| G[target_W = flex export budget]
    F -->|No| H{negative or cheap price?}
    H -->|Yes| I[target_W = discretionary import budget]
    H -->|No| E
    B -->|TESLA_BUFFER_EXPORT| G
    B -->|HOLD / WAIT / blocked| E
```

## 4. EV Power Adapter

```mermaid
flowchart TD
    A[EM2_Power_Intent v0.1/v0.2] --> B{Revision aligned + valid?}
    B -->|No| C[REVISION_MISMATCH]
    B -->|Yes| D{target_W <= 0?}
    D -->|Yes| E[command_A = 0]
    D -->|No| F{Reliable W/A available?}
    F -->|No| G[WAITING_FOR_ELECTRICAL_CONTEXT]
    F -->|Yes| H[deadband = W/A x 6A]
    H --> I{target_W below deadband?}
    I -->|Yes| E
    I -->|No| J[round target_W / W_per_A]
    J --> K[Clamp 6..16 A]
    K --> L[Publish shadow command]
    L --> M[No Easee write]
```

## 5. Generieke adapter schema mismatch

```mermaid
flowchart TD
    A[Power Intent producer] --> B[EM2_POWER_INTENT_V0.2]
    B --> C[Actuator Commands v0.1]
    C --> D{Schema == V0.1?}
    D -->|No| E[INVALID_POWER_INTENT]
    B --> F[EV Power Adapter v0.1]
    F --> G{Schema V0.1 or V0.2?}
    G -->|Yes| H[Continue translation]
```

## 6. Beoogde cut-overgrens

```mermaid
flowchart LR
    A[Core policy] --> B[Power Intent]
    B --> C[Device adapter]
    C --> D[Single physical writer]
    D --> E[Actuator]

    X[Legacy physical writer] -. must be disabled atomically .-> D
```

De fysieke writer blijft buiten deze SHADOW-module totdat een expliciete cut-over is gevalideerd.
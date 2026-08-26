---
title: Planner and Power Intent Flows
status: implemented-shadow
last_verified: 2026-08-26
---

# Planner and Power Intent Flows

## 1. End-to-end Power Intent and adapter architecture

```process-model
{
  "id": "planner-power-intent-flow-0",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[EMS policy / Energy Core] --> B[Power Intent]",
    "    B --> C[EV_target_W]",
    "    B --> D[WW target_on / future WW_target_W]",
    "    C --> E[EV Power Adapter]",
    "    D --> F[WW Power Adapter]",
    "    E --> G[EV writer lifecycle]",
    "    F --> H[WW writer lifecycle]",
    "    G -. SHADOW: no write yet .-> I[Easee]",
    "    H -. SHADOW: no write yet .-> J[Boiler]",
    "    K[Current production writer] --> I",
    "    L[Current boiler writer] --> J"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-0 START -->
```mermaid
flowchart TD
    A[EMS policy / Energy Core] --> B[Power Intent]
    B --> C[EV_target_W]
    B --> D[WW target_on / future WW_target_W]
    C --> E[EV Power Adapter]
    D --> F[WW Power Adapter]
    E --> G[EV writer lifecycle]
    F --> H[WW writer lifecycle]
    G -. SHADOW: no write yet .-> I[Easee]
    H -. SHADOW: no write yet .-> J[Boiler]
    K[Current production writer] --> I
    L[Current boiler writer] --> J
```
<!-- GENERATED_MERMAID:planner-power-intent-flow-0 END -->

De gestippelde adapterroutes zijn SHADOW en mogen niet als actieve fysieke writers worden geïnterpreteerd. De bestaande productie-writers blijven eigenaar totdat een atomic single-writer cut-over is gevalideerd.

## 2. 24h Planner

```process-model
{
  "id": "planner-power-intent-flow-1",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Every 15 min + 45 s delay] --> B[Read EM2_State / WW / Price Context]",
    "    B --> C{Price context usable?}",
    "    C -->|No| D[Planner status DEGRADED_PRICE_CONTEXT]",
    "    C -->|Yes| E[Build 15-min price slots]",
    "    E --> F[Rank Tesla slots before deadline]",
    "    E --> G[Allocate WW slots before 19:00]",
    "    E --> H[Calculate theoretical battery charge/discharge candidates]",
    "    F --> I[Publish EM2_Energy_Plan_24h]",
    "    G --> I",
    "    H --> I",
    "    D --> I",
    "    I --> J[No physical writes]"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-1 START -->
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
<!-- GENERATED_MERMAID:planner-power-intent-flow-1 END -->

## 3. Power Intent revision guard

```process-model
{
  "id": "planner-power-intent-flow-2",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[EM2_Public_State changed] --> B[Read Public State, State, Decision, WW Control]",
    "    B --> C{All source revisions aligned?}",
    "    C -->|No| D[valid=false\\nREVISION_MISMATCH\\nEV target 0 W]",
    "    C -->|Yes| E[Project Core policy]",
    "    E --> F[Calculate EV target_W]",
    "    E --> G[Project WW target_on]",
    "    F --> H[Publish EM2_Power_Intent v0.2]",
    "    G --> H"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-2 START -->
```mermaid
flowchart TD
    A[EM2_Public_State changed] --> B[Read Public State, State, Decision, WW Control]
    B --> C{All source revisions aligned?}
    C -->|No| D[valid=false
REVISION_MISMATCH
EV target 0 W]
    C -->|Yes| E[Project Core policy]
    E --> F[Calculate EV target_W]
    E --> G[Project WW target_on]
    F --> H[Publish EM2_Power_Intent v0.2]
    G --> H
```
<!-- GENERATED_MERMAID:planner-power-intent-flow-2 END -->

## 4. EV target projection

```process-model
{
  "id": "planner-power-intent-flow-3",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Aligned Core Decision] --> B{Intent}",
    "    B -->|TESLA_CHARGE_DEADLINE| C{remaining kWh + deadline valid?}",
    "    C -->|Yes| D[target_W = remaining/time]",
    "    C -->|No| E[target_W = 0]",
    "    B -->|TESLA_CHARGE_OPPORTUNITY| F{flex budget >= 800 W?}",
    "    F -->|Yes| G[target_W = flex export budget]",
    "    F -->|No| H{negative or cheap price?}",
    "    H -->|Yes| I[target_W = discretionary import budget]",
    "    H -->|No| E",
    "    B -->|TESLA_BUFFER_EXPORT| G",
    "    B -->|HOLD / WAIT / blocked| E"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-3 START -->
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
<!-- GENERATED_MERMAID:planner-power-intent-flow-3 END -->

## 5. EV Power Adapter

```process-model
{
  "id": "planner-power-intent-flow-4",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[EV_target_W] --> B{Revision/schema/freshness valid?}",
    "    B -->|No| C[requested_A = 0 / fail closed]",
    "    B -->|Yes| D{target_W <= 0?}",
    "    D -->|Yes| C",
    "    D -->|No| E[theoretical_A = target_W / 3x230]",
    "    E --> F[floor to whole A]",
    "    F --> G{requested_A >= 6 A?}",
    "    G -->|No| C",
    "    G -->|Yes| H[Clamp to safe maximum <=16 A]",
    "    H --> I[Publish requested_A + executable_W]",
    "    I --> J[commanded_A remains null in SHADOW]",
    "    J --> K[No Easee write]"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-4 START -->
```mermaid
flowchart TD
    A[EV_target_W] --> B{Revision/schema/freshness valid?}
    B -->|No| C[requested_A = 0 / fail closed]
    B -->|Yes| D{target_W <= 0?}
    D -->|Yes| C
    D -->|No| E[theoretical_A = target_W / 3x230]
    E --> F[floor to whole A]
    F --> G{requested_A >= 6 A?}
    G -->|No| C
    G -->|Yes| H[Clamp to safe maximum <=16 A]
    H --> I[Publish requested_A + executable_W]
    I --> J[commanded_A remains null in SHADOW]
    J --> K[No Easee write]
```
<!-- GENERATED_MERMAID:planner-power-intent-flow-4 END -->

## 6. WW Power Adapter

```process-model
{
  "id": "planner-power-intent-flow-ww-adapter",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[WW target_on from Power Intent] --> B{Revision/schema/freshness valid?}",
    "    B -->|No| C[Fail closed / no physical write]",
    "    B -->|Yes| D{target_on}",
    "    D -->|true| E[requested = ON]",
    "    D -->|false| F[requested = OFF]",
    "    D -->|null| G[requested = HOLD]",
    "    E --> H[Publish WW shadow command]",
    "    F --> H",
    "    G --> H",
    "    H --> I[deviceWrites=false]",
    "    I --> J[Existing boiler writer remains physical owner]"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-ww-adapter START -->
```mermaid
flowchart TD
    A[WW target_on from Power Intent] --> B{Revision/schema/freshness valid?}
    B -->|No| C[Fail closed / no physical write]
    B -->|Yes| D{target_on}
    D -->|true| E[requested = ON]
    D -->|false| F[requested = OFF]
    D -->|null| G[requested = HOLD]
    E --> H[Publish WW shadow command]
    F --> H
    G --> H
    H --> I[deviceWrites=false]
    I --> J[Existing boiler writer remains physical owner]
```
<!-- GENERATED_MERMAID:planner-power-intent-flow-ww-adapter END -->

`WW_target_W` is het toekomstige numerieke contract. De huidige v0.2 producer levert nog `target_on`; de adapter mag daarom niet zelf een fictief watt-target construeren.

## 7. Generieke Actuator Commands v0.2

```process-model
{
  "id": "planner-power-intent-flow-5",
  "kind": "mermaid-source",
  "declaration": "flowchart TD",
  "lines": [
    "    A[Power Intent producer] --> B[EM2_POWER_INTENT_V0.2]",
    "    B --> C[Actuator Commands v0.2]",
    "    C --> D{Schema V0.1 or V0.2?}",
    "    D -->|No| E[INVALID_POWER_INTENT]",
    "    D -->|Yes| F{intent valid + deviceWrites false + revision present?}",
    "    F -->|No| E",
    "    F -->|Yes| G[Publish EM2_ACTUATOR_COMMANDS_V0.2]",
    "    G --> H[EV translation delegated to EV Power Adapter]",
    "    G --> I[WW translation delegated to WW Power Adapter]",
    "    G --> J[Battery shadow / not integrated]",
    "    H --> K[No physical writes]",
    "    I --> K",
    "    J --> K"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-5 START -->
```mermaid
flowchart TD
    A[Power Intent producer] --> B[EM2_POWER_INTENT_V0.2]
    B --> C[Actuator Commands v0.2]
    C --> D{Schema V0.1 or V0.2?}
    D -->|No| E[INVALID_POWER_INTENT]
    D -->|Yes| F{intent valid + deviceWrites false + revision present?}
    F -->|No| E
    F -->|Yes| G[Publish EM2_ACTUATOR_COMMANDS_V0.2]
    G --> H[EV translation delegated to EV Power Adapter]
    G --> I[WW translation delegated to WW Power Adapter]
    G --> J[Battery shadow / not integrated]
    H --> K[No physical writes]
    I --> K
    J --> K
```
<!-- GENERATED_MERMAID:planner-power-intent-flow-5 END -->

Dedupe gebruikt `sourceRevision + inputSchema`.

## 8. Beoogde cut-overgrens

```process-model
{
  "id": "planner-power-intent-flow-6",
  "kind": "mermaid-source",
  "declaration": "flowchart LR",
  "lines": [
    "    A[EMS policy] --> B[Power Intent]",
    "    B --> C[Device Power Adapter]",
    "    C --> D[Writer lifecycle]",
    "    D --> E[Single physical writer]",
    "    E --> F[Actuator]",
    "    X[Legacy physical writer] -. disabled atomically at cut-over .-> E"
  ]
}
```

<!-- GENERATED_MERMAID:planner-power-intent-flow-6 START -->
```mermaid
flowchart LR
    A[EMS policy] --> B[Power Intent]
    B --> C[Device Power Adapter]
    C --> D[Writer lifecycle]
    D --> E[Single physical writer]
    E --> F[Actuator]
    X[Legacy physical writer] -. disabled atomically at cut-over .-> E
```
<!-- GENERATED_MERMAID:planner-power-intent-flow-6 END -->

De fysieke writer blijft buiten deze SHADOW-module totdat een expliciete cut-over is gevalideerd.

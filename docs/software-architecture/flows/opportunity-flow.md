---
component: opportunity-engine
title: Opportunity Engine Flow
version: 0.1.0
status: shadow
architecture_status: implemented
last_verified: 2026-08-25
---

# Opportunity Engine Flow

## Actuele beslisflow

```mermaid
flowchart TD
  A[Core/Decision revision] --> B{Safety / MUST actief?}
  B -->|ja| C[Voer MUST-pad uit / opportunity ondergeschikt]
  B -->|nee| D{P1 grid measurement valid?}
  D -->|nee| E[flex_export_budget = 0]
  D -->|ja| F[bereken flex_export_budget na reserves]
  F --> G{Tesla connected en flex >= startgrens?}
  G -->|ja| H[TESLA_CHARGE_OPPORTUNITY / export target]
  G -->|nee| I{WW eligible voor opportunity?}
  I -->|ja| J[WW candidate max SHOULD]
  I -->|nee| K{Prijscontext vers en gunstig?}
  K -->|ja| L[Prijs-opportunity binnen importbudget]
  K -->|nee| M[HOLD]
  E --> K
```

## Power Intent-projectie

```mermaid
flowchart LR
  D[EM2_Decision] --> R{Revisions aligned?}
  S[EM2_State] --> R
  W[EM2_Control_WW] --> R
  P[EM2_Public_State] --> R
  R -->|nee| Z[REVISION_MISMATCH\nEV target 0 W]
  R -->|ja| I{Decision intent}
  I -->|TESLA_CHARGE_OPPORTUNITY + export| X[target_W = flex_export_budget]
  I -->|TESLA_CHARGE_OPPORTUNITY + price| Y[target_W = discretionary_import_budget]
  I -->|HOLD / WAIT| H[target_W = 0]
```

## Grenzen

Deze flow beschrijft policy/intents. Alleen expliciet aangewezen productiecontrollers mogen fysieke writes uitvoeren. De generieke Power Intent/adapterketen blijft SHADOW totdat single-writer-cut-over is gevalideerd.

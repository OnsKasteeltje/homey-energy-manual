---
title: Publisher and Public State Flow
status: active
last_verified: 2026-08-25
source:
  - Homey Advanced Flow: EM v2 | 04 Publisher | v1.0.4 (Tesla lifecycle)
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2 SHADOW
---

# Publisher and Public State Flow

## 1. Publisher runtime

```mermaid
flowchart TD
    A[Every 5 min] --> B[Delay 60 s]
    X[Manual start] --> C[Read Homey Logic variables]
    B --> C
    C --> D{EM2_Public_State.meta present?}
    D -->|No| E[Publish_Due=true\nBLOCKED_PUBLIC_STATE_MISSING]
    D -->|Yes| F[Enrich tesla.deadline_status]
    F --> G{state_revision numeric?}
    G -->|No| H[Publish_Due=true\nBLOCKED_REVISION_MISSING]
    G -->|Yes| I{GitHub token present?}
    I -->|No| J[Publish_Due=true\nBLOCKED_TOKEN_MISSING]
    I -->|Yes| K{Revision pending OR heartbeat >=6 min OR forced?}
    K -->|No| L[SKIP_CURRENT]
    K -->|Yes| M[Set generated_at / heartbeat_at / publish_reason]
    M --> N[GET current GitHub file SHA]
    N --> O{GET 200 or 404?}
    O -->|No| P[Publish_Due=true\nGITHUB_GET_ERROR]
    O -->|Yes| Q[PUT energy-state-v2.json]
    Q --> R{PUT success?}
    R -->|No| S[Publish_Due=true\nGITHUB_PUT_ERROR]
    R -->|Yes| T[Rewrite EM2_Public_State with published payload]
    T --> U[Update Last Publish + Revision + Version]
    U --> V[Publish_Due=false\nPUBLISHED]
```

## 2. Downstream revision boundary

```mermaid
flowchart TD
    A[Publisher rewrites EM2_Public_State] --> B[Power Intent variable_changed trigger]
    B --> C[Read Public State + EM2_State + Decision + WW Control]
    C --> D{pubRev == stateRev == decisionRev == wwRev?}
    D -->|No| E[EM2_POWER_INTENT_V0.2\nvalid=false\nREVISION_MISMATCH\nEV target 0 W]
    D -->|Yes| F[Project Core policy to numeric/binary targets]
    F --> G[EM2_POWER_INTENT_V0.2\nvalid=true]
    G --> H[Actuator adapters in SHADOW]
```

## 3. Public website boundary

```mermaid
flowchart LR
    A[Internal EM2_Public_State] --> B[Publisher enrichment]
    B --> C[GitHub docs/data/energy-state-v2.json]
    C --> D[Website / presentation]

    D -. no control feedback .-> A
```

## 4. Recovery behavior

```mermaid
stateDiagram-v2
    [*] --> CURRENT
    CURRENT --> PUBLISH_PENDING: revision changed
    CURRENT --> PUBLISH_PENDING: heartbeat >= 6 min
    CURRENT --> PUBLISH_PENDING: Publish_Due=true
    PUBLISH_PENDING --> PUBLISHED: GitHub PUT succeeds
    PUBLISH_PENDING --> RETRY_DUE: input/token/GitHub error
    RETRY_DUE --> PUBLISH_PENDING: next scheduled/manual run
    PUBLISHED --> CURRENT: revision bookkeeping updated
```

## 5. Gevalideerde bijzonderheid

De live Publisher noemt zichzelf in status en `EM2_Last_Publisher_Version` versie `V1.0.4`, maar vult in de gepubliceerde payload momenteel `meta.publisher_version=EM2_PUBLISHER_V1.0.3`. Het diagram volgt het daadwerkelijke gedrag; de afwijking staat als bekende beperking in de componentdocumentatie.

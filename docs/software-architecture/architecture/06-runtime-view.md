---
title: Runtime View
version: 0.1
status: active
architecture_status: implemented
last_verified: 2026-08-26
source:
  - docs/software-architecture/flows/
  - docs/software-architecture/components/
---

# Runtime View

## Doel

Deze view legt de generieke runtime-keten vast. Gedetailleerde componentflows worden uit de afzonderlijke process models gegenereerd en blijven leidend voor operationele logica.

```mermaid
sequenceDiagram
    participant M as Measurements
    participant C as Energy Core
    participant P as Planner / Policy
    participant I as Power Intent
    participant A as Device Adapter
    participant D as Physical Device
    participant O as Observability

    M->>C: actuele metingen/state
    C->>P: genormaliseerde systeemstate
    P->>I: gekozen target power (W)
    I->>A: typed power-intent contract
    A->>A: validate + clamp + idempotency
    A->>O: calculated output / SHADOW evidence
    alt ACTIVE and write permitted
        A->>D: physical command
        D-->>C: resulting device state
    else SHADOW
        A-->>D: no write
    end
```

## Runtime-regels

- De planner bepaalt intent; adapters herinterpreteren geen opportunity-, prijs-, prioriteits- of deadlinebeleid.
- SHADOW en ACTIVE gebruiken dezelfde berekeningsroute; alleen de fysieke write-gate verschilt.
- Fysieke writes zijn idempotent en single-writer beschermd.
- Runtime-observability publiceert input, intent, berekende adapteroutput, write-status en relevante reject/fail-closed reden.
- Component-specifieke flows zijn detailviews van deze keten en moeten met de actuele implementatie overeenkomen.

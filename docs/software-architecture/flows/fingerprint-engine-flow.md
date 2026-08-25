---
title: Fingerprint Engine procesflows
version: 0.1
status: active
last_verified: 2026-08-25
source:
  - Homey: EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING
  - Homey: EM v2 | 01a Quooker | P1 Event Heartbeat v0.2
  - Homey: Energie | Wasmachine & Droger analyse | v1.4.2
---

# Fingerprint Engine procesflows

## 1. Generieke maturity-flow

```mermaid
flowchart TD
    A[Ground-truth event] --> B[Fingerprint candidate]
    B --> C{Herhaalbaar patroon?}
    C -->|Nee| A
    C -->|Ja| D[Validated fingerprint]
    D --> E{Actieve runtime detector aanwezig?}
    E -->|Nee| F[M2: dataset / SHADOW herkenning]
    E -->|Ja| G[M3: runtime detector]
    G --> H{Safety-validatie voor control?}
    H -->|Nee| I[Observatie-only]
    H -->|Ja| J[M4: control-grade]
```

## 2. Quooker event-assisted detector

```mermaid
flowchart TD
    P1[P1 measure_power changed] --> HB[Set EM_Quooker_P1_Event_Seen = true]
    T[1-min detector tick] --> Q[Targeted Cooker read]
    Q --> S{Cooker switch ON?}
    S -->|Nee| O[Status OFF]
    O --> E{P1 heartbeat gezien?}
    E -->|Ja| R[Targeted P1/L3 read]
    R --> BL[Update baseline indien stabiel]
    E -->|Nee| PUB[Publish detector state]
    BL --> PUB
    S -->|Ja| H{P1 heartbeat gezien?}
    H -->|Nee| IDLE[Status ON_IDLE]
    IDLE --> PUB
    H -->|Ja| P[Targeted P1/L3 read]
    P --> D[delta = L3 - baseline]
    D --> X{1400 W <= delta <= 1750 W?}
    X -->|Ja| HEAT[Status HEATING + power estimate]
    X -->|Nee| IDLE2[Status ON_IDLE]
    HEAT --> PUB
    IDLE2 --> PUB
```

## 3. Laundry event-first analyse

```mermaid
flowchart TD
    A[AEG applianceState/cyclePhase change] --> S[Full event snapshot]
    S --> D[Derive washer/dryer active state]
    D --> C{Geïsoleerde transition?}
    C -->|Nee| P[Publish latest sample only]
    C -->|Ja| K[Compare P1 phase deltas]
    K --> F{Known-load delta <= 450 W?}
    F -->|Nee| P
    F -->|Ja| B[Select dominant phase transition]
    B --> V{40..3500 W and phase distinct?}
    V -->|Nee| P
    V -->|Ja| E[Append evidence max 30]
    E --> M[Median + phase consistency]
    M --> CF[Confidence NONE/LOW/MEDIUM/HIGH]
    CF --> P
```

## 4. Laundry 5-min fallback

```mermaid
flowchart TD
    T[5-min sampler] --> S{EM2_State valid and <=15 min old?}
    S -->|Nee| X[No learning]
    S -->|Ja| P[Read washer/dryer active + P1 phases from EM2_State]
    P --> C{State transition since previous sample?}
    C -->|Nee| Q[Store sample]
    C -->|Ja| I[Apply same isolation filters]
    I --> E[Learn evidence when valid]
    E --> Q
```

## 5. Confidence-gated presentation

```mermaid
flowchart TD
    D[Detector/model output] --> C{Confidence}
    C -->|NONE/LOW| S[Show status only; no live wattage]
    C -->|MEDIUM/HIGH| W[Estimated wattage allowed]
    W --> L[Label source as P1_TRANSITION_MODEL]
    L --> N[Never present as direct device meter]
```

## 6. Control boundary

```mermaid
flowchart LR
    FP[Fingerprint detector] --> ST[Observation state]
    ST --> DEC[Separate decision layer]
    DEC --> ACT[Separate actuator]
    FP -. forbidden .-> ACT
```

Een fingerprint-detector schrijft nooit rechtstreeks naar een fysiek apparaat.

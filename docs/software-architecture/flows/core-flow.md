---
component: core-flow
title: Core procesflow
version: 0.10.13
status: active
architecture_status: implemented
last_verified: 2026-08-25
source:
  - homey:advancedflow:227f8d3b-7551-46dd-837d-1b8c69add824
---

# Core procesflow

Dit diagram is opgesteld op basis van de live Homey Advanced Flow `EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)` en niet op basis van een gewenste doelarchitectuur.

```mermaid
flowchart TD
    A1[Elke 5 minuten] --> C[Core HomeyScript v0.10.13]
    A2[Handmatige start] --> C

    C --> R1[1x Homey.devices.getDevices]
    C --> R2[1x Homey.logic.getVariables]
    R1 --> S[In-memory snapshot]
    R2 --> S

    S --> Q[Quooker freshness + detectorstate]
    S --> L[Wasmachine / droger direct state]
    S --> E[Lees P1, PV, Tesla/Easee, Equalizer, boiler, Quatt]
    S --> X[Lees prijs/PV context]

    E --> T[Source timing + freshness]
    T --> P1{P1 vers <= 60 s?}
    P1 -->|Nee| F0[Flex-exportbudget = 0 W fail-closed]
    P1 -->|Ja| FB[Bereken P1-authoritatief flexbudget]

    T --> SY{PV-bronnen vers en skew <= 180 s?}
    SY -->|Ja| HB[Bereken Huis + Overig]
    SY -->|Nee| HD[Onderdruk afgeleide Huis/Overig]

    FB --> B[Energy budget]
    F0 --> B
    HB --> B
    HD --> B
    Q --> B
    L --> B

    B --> ST[Schrijf EM2_State + revision]
    ST --> TD[Tesla Decision SHADOW]
    TD --> TS[EM2_Shadow vergelijking]

    ST --> WW[Update EM2_WW_State]
    WW --> WWD{Warmwater policy}
    X --> WWD
    B --> WWD
    WWD --> WWC[EM2_Control_WW SHADOW]

    ST --> PUB[Construeer EM2_Public_State schema 2.12]
    TD --> PUB
    TS --> PUB
    WW --> PUB
    WWC --> PUB
    X --> PUB

    PUB --> DUE[Zet EM2_Publish_Due]
    DUE --> READY[Publisher status READY_FOR_PUBLISHER]

    TD -. geen fysieke EV-write .-> N1[Read-only]
    WWC -. geen fysieke boiler-write .-> N1
    E -. Quatt OBSERVE_ONLY .-> N1
```

## Beslisregels uit de implementatie

### Tesla

```mermaid
flowchart TD
    A[Start Tesla Decision] --> B{Deadline actief en resterend kWh > 0?}
    B -->|Ja| C{Latest start bereikt?}
    C -->|Ja| D[MUST: deadline charge of blocked-not-connected]
    C -->|Nee| E{Flex >= 800 W of negatieve prijs of goedkope prijs + importbudget?}
    E -->|Ja| F[SHOULD: opportunity charge / wait-not-connected]
    E -->|Nee| G[HOLD]
    B -->|Nee| H{Aangesloten en flex >= 1500 W?}
    H -->|Ja| I[MAY: TESLA_BUFFER_EXPORT]
    H -->|Nee| G
```

### Warm water

De volledige warmwaterbeslisboom is uitgebreider, maar de actuele implementatie hanteert deze prioriteitsvolgorde:

```mermaid
flowchart TD
    A[Start WW Control] --> B{Boilermodus actief?}
    B -->|Nee| Z1[MUST: boiler uit / hold]
    B -->|Ja| C{Na 19:00?}
    C -->|Ja| Z2[MUST: boiler uit / hold]
    C -->|Nee| D{Dagdoel bereikt?}
    D -->|Ja| E[Alleen gevalideerde post-goal SHOULD; nooit MUST]
    D -->|Nee| F{Catch-up vereist?}
    F -->|Ja| G[MUST: BOILER_ON / HOLD]
    F -->|Nee| H{Voor 09:30?}
    H -->|Ja| I[Wachten / vroege run beëindigen]
    H -->|Nee| J{Sterke flex-export?}
    J -->|Ja| K[SHOULD: EXPORT]
    J -->|Nee| L{Negatieve prijs + horizon OK?}
    L -->|Ja| M[SHOULD: PRICE_NEGATIVE]
    L -->|Nee| N{Goedkope prijs + horizon + importbudget OK?}
    N -->|Ja| O[SHOULD: PRICE_CHEAP]
    N -->|Nee| P{PV top4h + minimaal flexbudget?}
    P -->|Ja| Q[SHOULD: PV_FORECAST]
    P -->|Nee| R{Actieve run-lock?}
    R -->|Ja| S[HOLD]
    R -->|Nee| T[Conservatief HOLD / eventueel BOILER_OFF]
```

## Architectuurgarantie

Dit flowbestand moet opnieuw tegen de live Homey-flow worden gecontroleerd zodra `EM v2 | 00 Core Tick` van versie verandert of wanneer de centrale HomeyScript-code inhoudelijk wordt aangepast.

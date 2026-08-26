---
title: Building Block View
version: 0.1
status: active
architecture_status: implemented
last_verified: 2026-08-26
source:
  - docs/software-architecture/components/
  - docs/software-architecture/architecture/04-data-model.md
---

# Building Block View

## Doel

Deze view beschrijft de statische verantwoordelijkheidsverdeling binnen HEMS. Het model volgt C4-principes pragmatisch: alleen componentgrenzen die relevant zijn voor ownership, contracts en write-routes worden expliciet gemaakt.

## Hoofdstructuur

```mermaid
flowchart LR
    Measurements[Measurements / device state] --> Core[Energy Core]
    Core --> Planner[24h Planner]
    Planner --> Intent[Power Intent Layer]
    Intent --> EV[EV Power Adapter]
    Intent --> WW[WW Power Adapter]
    Intent --> Battery[Victron / Battery Adapter]
    EV --> Easee[Easee Charger]
    WW --> Boiler[Hot-water device]
    Battery --> Victron[Victron system]
    Core --> Publisher[Public State Publisher]
    Price[Price Adapter] --> Planner
    Opportunity[Opportunity Engine] --> Planner
    Fingerprint[Fingerprint Engine] --> Core
```

## Ownership rules

- Energy Core normaliseert actuele meet- en systeemstate.
- Planner en Power Intent bezitten EMS-beslislogica en produceren target-W intenties.
- Device adapters bezitten uitsluitend contractvalidatie, vertaling, veiligheidsgrenzen, idempotency en de fysieke write-route.
- Per fysiek device bestaat maximaal één ACTIVE writer.
- Publisher/website is observability en bevat geen control policy.

## Grenzen

SHADOW componenten mogen berekende output publiceren maar niet fysiek schrijven. Een componentgrens wordt pas als ACTIVE beschouwd nadat de relevante runtime- en RC-validatie is vastgelegd.

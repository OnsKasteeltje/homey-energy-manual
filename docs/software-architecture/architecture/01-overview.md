---
component: architecture
title: Softwarearchitectuur Overzicht
version: 0.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-25
source:
  - docs/architectuur.md
  - docs/software-architecture/components/core.md
  - docs/software-architecture/components/publisher-public-state.md
---

# Softwarearchitectuur Overzicht

## Doel

Het Home Energy Management System (HEMS) scheidt meten, state, beslissen, publiceren en fysiek aansturen. De actuele implementatie is leidend; SHADOW- en planned-functionaliteit wordt expliciet als zodanig gemarkeerd.

## Hoofdketen

```mermaid
flowchart TD
  DEV[Homey devices / P1 / PV / Easee / Boiler / Quatt] --> CORE[Energy Core v2]
  CORE --> STATE[State + Decision + WW Control]
  STATE --> PUB[Publisher / EM2_Public_State]
  PUB --> WEB[Website / frontend]
  PUB --> PI[Power Intent SHADOW]
  PI --> ADP[Actuator adapters SHADOW]
  CORE --> PROD[Tesla production writer / legacy boiler writers]
  PRICE[Contract / price context] --> CORE
  PRICE --> PI
  PLAN[24h Planner SHADOW] --> PI
  VICTRON[Victron future adapter] -. planned .-> CORE
```

## Architectuurlagen

1. **Fysieke veiligheid** — 3×25 A aansluiting, lokale apparaatbeveiligingen en Easee Equalizer staan boven software-optimalisatie.
2. **Meet- en statelaag** — Core gebruikt maximaal één volledige device-snapshot per tick en publiceert canonieke Logic-state.
3. **Contextlaag** — contract, prijs, PV/freshness en configuratie worden als losse context aangeboden.
4. **Decision-laag** — MUST-verplichtingen gaan vóór economische opportunities.
5. **Power Intent / adapters** — numerieke vermogensintenties en elektrische vertaling zijn SHADOW totdat één-writer-cut-over expliciet is gevalideerd.
6. **Publisher / website** — `EM2_Public_State` is het publieke read-model en tegelijk revision-boundary voor downstream logic.

## Belangrijkste operationele grenzen

- P1 is autoritatief voor netimport/export en flex-exportbudget.
- Een ongeldige afgeleide huis/PV-balans blokkeert niet automatisch verse P1-flex.
- Tesla-productie heeft één automatische Easee-writer.
- Slimme WW-control is SHADOW; fysieke boilerwrites lopen nog via gecontroleerde legacy flows.
- Fingerprint-detectie observeert en attribueert; zij stuurt geen actuators rechtstreeks aan.
- Victron/batterij is nog niet runtime-geïntegreerd.

## Documentatieregel

Alle onderliggende component- en flowdocumenten worden pas in dit masterdocument opgenomen nadat ze tegen actuele code/configuratie zijn gecontroleerd. Gegenereerde output is afgeleid en wordt niet handmatig gewijzigd.

---
title: Deployment View
version: 0.1
status: active
architecture_status: implemented
last_verified: 2026-08-26
source:
  - docs/architectuur.md
  - docs/software-architecture/components/
---

## Deployment View

### Doel

Deze view beschrijft waar de belangrijkste softwareverantwoordelijkheden runtime landen en welke externe systemen aan de HEMS-control plane grenzen.

```mermaid
flowchart TB
    subgraph GitHub[GitHub]
      Repo[Architecture + code/config repository]
      Actions[CI / architecture build]
      Pages[MkDocs / GitHub Pages]
      Repo --> Actions
      Actions --> Pages
    end

    subgraph Homey[Homey runtime]
      Core[Energy Core]
      Planner[Planner / Power Intent]
      EV[EV Power Adapter]
      WW[WW Power Adapter]
      Publisher[Public State Publisher]
      Core --> Planner
      Planner --> EV
      Planner --> WW
      Core --> Publisher
    end

    EV --> Easee[Easee Charger]
    WW --> HotWater[Hot-water device]
    Homey --> Victron[Victron / Cerbo GX - integration boundary]
    Publisher --> Cloud[Cloudflare / public status endpoint]
    Cloud --> Pages
```

### Deploymentregels

- Homey is de runtime control plane voor de huidige EMS-logica.
- GitHub is de versioned source-of-truth en CI/publication plane, niet de fysieke device-control plane.
- Cloud/publicatiecomponenten mogen observability/state publiceren maar geen alternatieve device-write route vormen.
- Victron blijft als integratiegrens expliciet gemodelleerd zolang de software-integratie niet ACTIVE is.
- Secrets, credentials en device identifiers horen niet in architectuurpublicaties.

# Flows

De operationele Homey-flows zijn geordend volgens de Energy Core v2-doelarchitectuur:

- **01 · Meten & observeren**
- **02 · Context & forecast**
- **03 · Beslissing**
- **04 · Aansturing**
- **05 · Publicatie & historie**
- **80 · Shadow / validatie**
- **90 · Historisch / uitgeschakeld**
- **99 · Temp / diagnostiek**

## Actuele v2-kern

De oudere v1-keten met zelfstandige State Collector/Allocator/Live-publicatie is niet meer leidend. De centrale v2-Core maakt één revision-consistente State/Decision/Shadow/publicatieketen.

| Laag | Actieve flow / component | Ritme | Rol |
|---|---|---:|---|
| Core | `EM v2 | 00 Core Tick | v0.10.5` | 5 min | centrale snapshot, State, Decision, Shadow, budget en publicatie |
| Quooker observer | `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING` | licht/event-assisted | switchstatus + P1 heatingdetectie, geen fysieke write |
| Context | `EM v2 | 30 Context | Price + PV v0.4` | 15 min | PBTH/PV-context en WW Planner |
| Watchdog | `EM v2 | 05 Watchdog | Core Freshness v0.2.1` | periodiek | freshness safety net, geen zelfstandige devicepolling |
| Publicatie | Core publisher `EM2_CORE_PUBLISH_V0.10.5` | gethrottled | `energy-state-v2.json`, schema 2.11 |

## Centrale dataketen

```text
Homey devices + Logic
        ↓
EM v2 Core Tick
        ├─→ State
        ├─→ Decision
        ├─→ Shadow
        ├─→ WW State / Control intent
        └─→ GitHub energy-state-v2.json
                       ↓
                  Website/app
```

Voor Quooker geldt aanvullend:

```text
Homey Cooker-switch ─► OFF / ON_IDLE
P1/L3 event ─────────► HEATING + power_w
        ↓
loads.quooker
        ↓
Core/GitHub → Live View
```

De Quooker-detector gebruikt geen volledige `getDevices()`-snapshot. De bestaande Quooker-flows blijven de fysieke aan/uit-regeling uitvoeren; de v0.3-detector observeert alleen.

## Live View

De Live View toont momenteel zeven afzonderlijke verbruikers: Tesla, Boiler, Ruimteverwarming, Wasmachine, Droger, Quooker en Overig. Alleen werkelijk actief verbruik boven 20 W krijgt een actieve energiestroom. Quooker `ON_IDLE` blijft daarom visueel inactief; `HEATING` wordt actief weergegeven met het gedetecteerde vermogen.

## Versieregel

Van dezelfde functionele flowfamilie mag maximaal één productieversie actief zijn. Bij een inhoudelijke wijziging wordt een hogere versie gemaakt, gevalideerd en geactiveerd; de voorganger wordt uitgeschakeld/SUPERSEDED gehouden als rollback wanneer dat zinvol is.

> Laatste update: **21 augustus 2026** — v2-Core v0.10.5/schema 2.11, Quooker v0.3 switch-authoritative + P1 heating en actuele Live View verwerkt.

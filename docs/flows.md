# Flows

De operationele Homey-flows zijn geordend volgens de doelarchitectuur:

- **01 · Meten & observeren**
- **02 · Context & forecast**
- **03 · Beslissing**
- **04 · Aansturing**
- **05 · Publicatie & historie**
- **80 · Shadow / validatie**
- **90 · Historisch / uitgeschakeld**
- **99 · Temp / diagnostiek**

## Actuele energie-kern

| Laag | Actieve flow | Ritme | Rol |
|---|---|---:|---|
| Meten & observeren | `Energy Manager State Collector v1.0` | 2 min | centrale runtime-snapshot |
| Context & forecast | `M7 - Prijs en PV forecast context - read only` | 15 min | prijs- en PV-context |
| Shadow / validatie | `Energie Manager PV - Shadow Mode v1.6.7` | 5 min | observeren, boiler-/Equalizeranalyse, shadowhistorie |
| Shadow / beslissing | `Energy Manager Allocator - Shadow v0.2.4` | 5 min | centrale shadowbeslissing en validatie |
| Aansturing | `Tesla laden v2.6` | 2 min | enige automatische Easee-writer |
| Publicatie | `Live energie publicatie v1.2` | 5 min | live website-snapshot uit `EM_Runtime_State` |
| Publicatie | `GitHub status sync - Homey lokaal v1.4` | 30 min | algemene flow-/shadowstatus |

## Centrale dataketen

```text
Homey devices + Logic
        ↓
Energy Manager State Collector v1.0
        ↓
EM_Runtime_State
        ├─→ Energy Manager Allocator - Shadow v0.2.4
        └─→ Live energie publicatie v1.2
```

`Tesla laden v2.6` blijft bewust rechtstreeks actuele Homey/Easee-data lezen omdat de fysieke laadregeling veiligheidskritisch is.

## Versieregel

Van dezelfde functionele flowfamilie mag maximaal één versie actief zijn. Na de load-optimalisatie van 16 augustus 2026 zijn onder andere v1.6.6, allocator v0.2.3, live energie v1.1 en status-sync v1.3 uitgeschakeld ten gunste van de opvolgers hierboven.

Gebruik de bestaande flowpagina’s in de navigatie voor de inhoudelijke details van Warm water, Energie Manager, M7, Quooker en GitHub-sync.

> Laatste update: **16 augustus 2026** — centrale state collector en load-geoptimaliseerde flowketen verwerkt.

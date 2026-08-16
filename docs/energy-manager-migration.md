# Energy Manager — gefaseerde migratie naar centrale allocatie

## Doel

De bestaande Homey-regeling blijft tijdens de migratie operationeel. Nieuwe centrale beslislogica wordt eerst **read-only in shadow mode** toegevoegd en neemt pas na validatie per actuator de besturing over.

De migratie volgt vier principes:

1. **geen big-bang omschakeling**;
2. **één eigenaar per fysieke actuator**;
3. **strategie centraal, lokale veiligheid en uitvoering lokaal**;
4. **eerst meten en vergelijken, daarna pas sturen**.

## Actuele architectuur — 16 augustus 2026

De migratie is inmiddels verder dan de oorspronkelijke baseline. De actuele doel-/implementatieketen is:

```text
Homey devices + Logic + M7 context
              ↓
Energy Manager State Collector v1.0
              ↓
        EM_Runtime_State
              ↓
Energy Manager Allocator - Shadow v0.2.4
              ↓
state / decision / validation / history
```

De centrale allocator blijft **read-only**. De fysieke productie-aansturing blijft vooralsnog bij de bestaande actuatorflows.

Actuele functionele rollen:

| Functie | Rol | Actuele architectuur |
|---|---|---|
| Warm water | productie | `Warm water optimalisatie - PV boiler + CV advies v1.3` |
| Tesla | productie | `Tesla laden v2.6` |
| Centrale runtime-state | meten/context | `Energy Manager State Collector v1.0` |
| Energy Manager shadow | observer/historie | `Energie Manager PV - Shadow Mode v1.6.7` |
| Centrale allocator | shadow/read-only | `Energy Manager Allocator - Shadow v0.2.4` |
| M7 Opportunity | shadow/read-only | `M7 - Opportunity Score - Shadow v1.3` |
| M7 prijs/PV | read-only | `M7 - Prijs en PV forecast context - read only` |
| Live website-energie | publicatie | `Live energie publicatie v1.2` |
| Algemene flowstatus | publicatie | `GitHub status sync - Homey lokaal v1.4` |

> De actuele Homey-status op de website wordt uitsluitend als operationeel actueel beschouwd wanneer `homey-status.json` recent genoeg is. Een oude statuspublicatie mag niet als actuele flownaam/status worden gepresenteerd.

## Control mode

De centrale migratie gebruikt één expliciete control mode:

| Waarde | Betekenis |
|---|---|
| `LEGACY` | alleen bestaande productieflows zijn leidend |
| `SHADOW` | centrale allocator rekent mee maar stuurt niets |
| `HYBRID` | alleen expliciet gemigreerde actuators volgen centrale opdrachten |
| `ACTIVE` | centrale Energy Manager is strategisch leidend voor alle gemigreerde flexloads |

Huidige fase: **`SHADOW`**.

## Stap 1 — centrale Energy State — GEREALISEERD

`Energy Manager State Collector v1.0` bouwt één gedeelde runtime-snapshot in Homey Logic:

```text
EM_Runtime_State
```

De snapshot bevat onder andere:

- netto P1-vermogen en L1/L2/L3;
- PV-productie per omvormer;
- Tesla/Easee laadstatus, gevraagd en werkelijk vermogen;
- Equalizer-fasecontext;
- boilervermogen en warmwaterstatus;
- relevante deadline- en M7-context;
- status van flexibele huishoudelijke belastingen waar beschikbaar.

Ontbrekende data blijft expliciet `null`/`UNKNOWN`; de allocator mag daarvoor geen fictieve waarde aannemen.

Het architectuurdoel is **één keer meten, meerdere keren gebruiken**. Alleen veiligheidskritische regelpaden, zoals de Tesla-aansturing, mogen hiervan afwijken wanneer directe actuele device-data nodig is.

## Stap 2 — centrale allocator in shadow — GEREALISEERD

De actieve centrale allocator is:

```text
Energy Manager Allocator - Shadow v0.2.4
```

Deze draait iedere vijf minuten vanuit `EM_Runtime_State` en schrijft **geen fysieke apparaten** aan.

De allocator publiceert intern onder andere:

- centrale state;
- centrale beslissing;
- laatste beslissing;
- historie;
- validatie-uitkomst;
- cumulatieve validatiestatistiek.

De beslisklassen zijn:

### MUST

Een verplichting die vóór een grens moet worden uitgevoerd, bijvoorbeeld:

- Tesla-deadline bereikt de catch-upgrens;
- boiler moet het dagdoel nog halen en de uiterste verwarmingsgrens nadert.

### SHOULD

Uitvoeren wanneer het energetisch/economisch aantrekkelijk is, bijvoorbeeld:

- boiler vroegtijdig verwarmen met beschikbaar PV-overschot;
- Tesla vóór de deadline opportunistisch laden;
- later: accu laden bij gunstige prijs/PV.

### MAY

Pure flexibiliteit zonder harde verplichting, bijvoorbeeld:

- Tesla als exportbuffer wanneer geen deadline actief is.

Lokale veiligheidslagen kunnen iedere centrale opdracht beperken of blokkeren.

## Stap 3 — shadowvergelijking — ACTIEF

De allocator vergelijkt zijn centrale beslissing met het observeerbare productiegedrag van Tesla en boiler.

Per cyclus wordt geclassificeerd als:

- `AGREE`;
- `DIFFER`;
- `NOT_COMPARABLE`.

De vergelijking gebruikt waar mogelijk werkelijk gedrag in plaats van alleen legacy-statuslabels:

- Tesla werkelijk laden / niet laden;
- Tesla werkelijk vermogen;
- boiler verwarmen / niet verwarmen;
- P1- en fasecontext;
- relevante M7-/deadlinecontext.

Een `DIFFER` is een **analysepunt**, niet automatisch een fout.

### Validatiecriteria boiler vóór HYBRID

De boiler wordt pas kandidaat voor `HYBRID` wanneer minimaal is bereikt:

- **30 bruikbare vergelijkingen**;
- **≥95% agreement**;
- **0 onverklaarde MUST-conflicten**;
- minstens **één volledige echte verwarmingscyclus** correct gevolgd.

Deze criteria worden eerst inhoudelijk beoordeeld; er vindt geen automatische migratie plaats.

## Stap 4 — boiler naar HYBRID — NOG NIET UITGEVOERD

Na succesvolle shadowvalidatie is de boiler de eerste actuator die wordt gemigreerd.

Reden:

- actuator is praktisch binair;
- geen dynamische hardware-load-balancing zoals Easee;
- rollback is eenvoudig te organiseren.

Tijdens `HYBRID` geldt per actuator exact één automatische schrijver:

```text
Energy Manager intent
      ↓
actuator-flow
      ↓
fysiek device
```

De legacy boilerbeslissing wordt pas buiten bedrijf gesteld nadat de nieuwe actuatorroute is getest en rollback is bevestigd.

## Stap 5 — Tesla migratie — LATER

Tesla volgt pas nadat de boiler-HYBRID stabiel is en de Tesla-shadowvalidatie voldoende representatieve situaties bevat:

- opportunistisch laden;
- niet aangesloten;
- deadline actief;
- catch-up;
- Easee Equalizer begrenst;
- Easee Equalizer blokkeert/pauzeert.

De Easee Equalizer blijft altijd de lokale load-balancing- en installatieveiligheidslaag boven de Homey-beslissing.

## Publicatie-architectuur

Websitepublicatie is geen onderdeel van de kritische regelroute.

```text
EM_Runtime_State
   └─→ Live energie publicatie v1.2 → GitHub → website

Shadow v1.6.7
   └─→ shadowhistorie → GitHub

GitHub status sync v1.4
   └─→ flowstatus → GitHub
```

De website mag sneller of langzamer verversen dan de interne regelcyclus. Een publishing- of GitHub-probleem mag de fysieke energieregeling niet blokkeren.

Voor algemene Homey-flowstatus geldt bovendien een freshness-regel: een te oude `homey-status.json` wordt op de homepage expliciet als **verouderd** gepresenteerd in plaats van als actuele operationele waarheid.

## Rollback

Rollback blijft altijd één flowversie terug:

```text
nieuwe actuatorversie UIT
oude productieversie AAN
controlMode terug naar SHADOW of LEGACY
```

Geen migratiestap mag een destructieve wijziging aan de vorige werkende flow vereisen.

## Victron-grens

Victron wordt later de snelle batterij-/netregelaar. Homey geeft alleen strategische intenties en probeert geen snelle vermogensregelkring te implementeren.

```text
Homey Energy Manager
      ↓ strategisch doel
Victron ESS
      ↓ snelle lokale regeling
MultiPlus / batterij / grid
```

Easee Equalizer blijft onafhankelijk de lokale EV-load-balancing en installatiebescherming uitvoeren.

## Status van deze migratie

- [x] productiebaseline vastgelegd
- [x] centrale Energy State gedefinieerd
- [x] `Energy Manager State Collector v1.0` gerealiseerd
- [x] `EM_Runtime_State` gerealiseerd
- [x] allocator-outputcontract gedefinieerd
- [x] control modes `LEGACY/SHADOW/HYBRID/ACTIVE` gedefinieerd
- [x] centrale allocator in Homey gerealiseerd
- [x] allocator naar centrale runtime-state gemigreerd
- [x] shadow state/decision/history gerealiseerd
- [x] `AGREE / DIFFER / NOT_COMPARABLE` validatie gerealiseerd
- [x] cumulatieve validatiestatistiek gerealiseerd
- [x] vergelijking met productiegedrag gestart
- [x] Homey-load verlaagd door centrale state en lichtere publishers
- [ ] voldoende representatieve boiler-shadowvalidatie verzamelen
- [ ] boilercriteria inhoudelijk beoordelen
- [ ] boiler gecontroleerd naar `HYBRID` migreren
- [ ] Tesla-validatie over meerdere laadscenario's afronden
- [ ] Tesla later gecontroleerd migreren
- [ ] Victron read-only integreren
- [ ] Victron-strategie in shadow valideren
- [ ] beperkte strategische ESS-aansturing pas daarna activeren

De fysieke regeling blijft dus bewust grotendeels in de bestaande productieflows terwijl de centrale architectuur meetbaar wordt gevalideerd.

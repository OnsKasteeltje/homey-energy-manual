# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** centrale single-reader Core Tick actief in read-only SHADOW.  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.1`.  
**Doel:** Homey als lichte edge-orchestrator; website en historie los van de fysieke regelroute.  
**Fysieke v2-writes:** geen.

Op 17 augustus 2026 is de v2-keten succesvol geconsolideerd naar één centrale Core Tick. State, Decision, Shadow, warmwater-state, warmwater-Control en publicatie worden nu atomair vanuit dezelfde sample en revision berekend. De bestaande fysieke boilerregeling is niet door v2 overgenomen: v2 berekent uitsluitend wat hij *zou* doen.

## Harde architectuurregels

1. Homey leest fysieke apparaten centraal en maximaal één keer per Energy Core-cyclus.
2. Per Core Tick wordt maximaal één `getDevices()` en één `getVariables()` uitgevoerd.
3. Downstream-berekeningen gebruiken dezelfde in-memory snapshot; geen herhaalde device-scans.
4. Iedere fysieke meetwaarde wordt één keer genormaliseerd in `EM2_State`.
5. Deadbands/hysterese onderdrukken kleine fluctuaties vóór publicatie.
6. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.
7. Websitebezoek veroorzaakt nul Homey-calls: de site leest uitsluitend gepubliceerde snapshots.
8. Historie en publicatie mogen geen extra device-scan veroorzaken.
9. State, Decision, Shadow en Control-intent horen bij dezelfde State-revision.
10. Ontbrekende data blijft `null`/`UNKNOWN`; v2 verzint geen waarden.
11. Een v2-Control-adapter mag pas fysieke writes krijgen nadat de shadowvalidatie voldoende betrouwbaar is.

## Actuele keten

```text
Devices / meters / Easee + Homey Logic
        │
        │ Core Tick iedere 5 min
        │ 1 × getDevices()
        │ 1 × getVariables()
        ▼
EM v2 | 00 Core Tick | v0.9.1
        │
        ├── 10 State
        │     └── EM2_State · revision N
        │
        ├── 20 Decision
        │     └── EM2_Decision · sourceRevision N
        │
        ├── 80 Shadow
        │     └── EM2_Shadow · sourceRevision N
        │
        ├── 15 Warm Water State
        │     └── EM2_WW_State · sourceRevision N
        │
        ├── 60 Warm Water Control
        │     └── EM2_Control_WW · sourceRevision N
        │         GEEN fysieke write
        │
        └── 90 Publish
              └── energy-state-v2.json → website

Parallel, zonder device-read:
EM v2 | 70 History | Day Series → energy-day-v2.json
```

De losse Collector-, Decision/Shadow-, Warm Water Observer-, Warm Water Actuator- en Publisher-paden zijn voor de operationele v2-kern gedeactiveerd. Ook `Core Tick v0.9` is na de succesvolle cut-over gedeactiveerd. De actuele operationele kern is uitsluitend `Core Tick v0.9.1`.

## Actieve v2-kern

| Onderdeel | Uitvoering | Device-read | Device-write | Functie |
|---|---|---:|---:|---|
| Core Tick v0.9.1 | elke 5 min | **1 centrale scan** | **nee** | volledige actuele v2-regelketen |
| State | binnen Core Tick | geen extra | nee | P1, PV, Tesla/Easee, Equalizer, boiler en appliance-status normaliseren |
| Decision | binnen Core Tick | geen extra | nee | energy state, intent en prioriteit |
| Shadow | binnen Core Tick | geen extra | nee | intent vergelijken met geobserveerde toestand |
| Warmwater state | binnen Core Tick | geen extra | nee | dagdoel, looptijd en thermostaatgedrag afleiden |
| Warmwater Control | binnen Core Tick | geen extra | **nee** | `BOILER_ON`, `BOILER_OFF` of `HOLD` als shadow-intent |
| Publish | binnen Core Tick | geen extra | nee | revision-consistente GitHub-snapshot, gethrottled |
| History | parallel vanuit bestaande state | nee | nee | compacte dagreeks zonder extra device-scan |

## Atomische revision-keten

`EM2_State` is de fysieke energie-state voor de regelcyclus. Een relevante verandering verhoogt de revision. Binnen dezelfde Core Tick worden vervolgens Decision, Shadow, Warm Water State en Warm Water Control berekend met dezelfde `sourceRevision`.

De succesvolle cut-overtest op 17 augustus 2026 bevestigde gelijktijdig:

```text
state_revision    = 157
decision_revision = 157
shadow_revision   = 157
WW sourceRevision = 157
WW Control sourceRevision = 157
```

Daarmee is de eerdere race-condition tussen Core Tick, losse WW Actuator en Publisher verwijderd.

## Warmwater Observer — geïntegreerd

Warmwatercontext wordt binnen de Core Tick uit de actuele Energy State afgeleid en opgeslagen in `EM2_WW_State` (`EM2_WW_STATE_V0.5`).

De state houdt bij:

- boiler-aan-tijd van vandaag;
- resterende 240-minuten fallbacktijd;
- of daadwerkelijk opwarmen is bevestigd;
- of `OP_TEMPERATUUR` is bereikt;
- of catch-up vóór 19:00 noodzakelijk wordt;
- kwaliteit van de huidige dagstate.

Voor thermostaatdetectie geldt:

```text
boiler aan + vermogen > 1500 W gedurende 15 min
    → opwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende 10 min
    → OP_TEMPERATUUR bereikt
```

De waargenomen cyclus van 17 augustus heeft deze einddetectie in Shadow correct doorlopen. Omdat de v2-observatie die dag pas later is gestart, blijft de statekwaliteit terecht `PARTIAL_FROM_START_TIME`.

## Warmwater Control — geïntegreerd PURE SHADOW

Warm Water Control wordt nu atomair binnen Core Tick v0.9.1 berekend en opgeslagen als `EM2_Control_WW` (`EM2_CONTROL_WW_V0.7`). Er is geen aparte Logic-read en geen aparte 5-minutentrigger meer nodig.

De veiligheids-guards zijn:

```text
readOnly      = true
deviceWrites  = false
stateFresh    = true
revisionMatch = true
wwStateFresh  = true
```

### Huidig beleid

| Situatie | Shadow-intent | Prioriteit |
|---|---|---|
| elektrische boilermodus niet geselecteerd | `BOILER_OFF` indien nodig | MUST |
| `OP_TEMPERATUUR` bereikt | `BOILER_OFF` indien nodig | MUST |
| na 19:00 | geen nieuwe run / `BOILER_OFF` | MUST |
| catch-up noodzakelijk | `BOILER_ON` indien uit | MUST |
| 09:30–18:30 en ≥ 2100 W export | `BOILER_ON` | SHOULD |
| boiler ≥30 min aan en >500 W import | `BOILER_OFF` | SHOULD |
| anders | `HOLD` | MAY |

De 240 minuten zijn fallback, niet het primaire doel. Het primaire dagdoel blijft `OP_TEMPERATUUR`.

**Belangrijk:** `BOILER_ON` en `BOILER_OFF` zijn op dit moment uitsluitend intenties. Core Tick v0.9.1 bevat geen fysieke boiler-write.

## Publisher — geïntegreerd

Publicatie is onderdeel van dezelfde Core Tick en gebruikt dezelfde atomische snapshot. De actuele websitepayload gebruikt:

```text
schema_version    = 2.3
publisher_version = EM2_CORE_PUBLISH_V0.9.1
control_mode      = SHADOW
```

GitHub-publicatie is bewust begrensd:

```text
relevante revision-wijziging
    → pending
    → minimaal 10 minuten tussen publicaties

geen publicatie nodig
    → geen GitHub-write

geen relevante wijziging
    → heartbeat uiterlijk na 30 minuten
```

De website veroorzaakt zelf geen Homey-calls.

## Website en historie

Homepage, Live energiestroom en Energie Dagoverzicht gebruiken de v2-publicaties.

- Live/Home: `energy-state-v2.json`;
- payloadschema: 2.3;
- Dagoverzicht: `energy-day-v2.json`;
- browserrefresh en health veroorzaken geen Homey-device-scan;
- actuele State, Decision, Shadow en WW Control zijn revision-consistent.

## Control modes

| Mode | Betekenis |
|---|---|
| `SHADOW` | **huidige mode**: v2 observeert en berekent control-intent, geen v2 device-writes |
| `HYBRID` | alleen expliciet gevalideerde actuators mogen door v2 worden gestuurd |
| `ACTIVE` | v2 is leidend voor alle gemigreerde flexloads |

De eerstvolgende promotie is niet automatisch HYBRID. Eerst wordt de centrale Core Tick als stabiele baseline gevalideerd en wordt minimaal één volledige warmwatercyclus vanaf vóór de start gevolgd. Daarna kan een afzonderlijke beslissing worden genomen over fysieke WW-Control.

## Load-budget na cut-over

De operationele v2-kern is nu ontworpen rond het minimale readmodel:

- **1 × `getDevices()` per 5 minuten**;
- **1 × `getVariables()` per 5 minuten**;
- State, Decision, Shadow, WW State en WW Control vervolgens in-memory in dezelfde run;
- geen aparte WW Actuator-poll;
- geen aparte Publisher-poll;
- GitHub-write maximaal iedere 10 minuten bij relevante wijzigingen;
- 30-minuten-heartbeat;
- website: nul Homey-calls.

Dit is de nieuwe baseline voor verdere v2-ontwikkeling. Nieuwe functies horen waar mogelijk aan deze centrale snapshot te consumeren in plaats van nieuwe periodieke device-readers toe te voegen.

## Gedeactiveerde voorgangers

Onder andere de volgende paden zijn niet meer operationeel onderdeel van de kern:

- losse State Collector-versies;
- losse Decision/Shadow-versies;
- losse Warm Water Observer-versies;
- `EM v2 | 60 Control | Warm Water Actuator v0.6`;
- losse State Publisher-versies;
- `EM v2 | 00 Core Tick | v0.9`.

Ze worden voorlopig niet destructief verwijderd zodat rollback mogelijk blijft. Er mag per functie slechts één actuele operationele versie actief zijn.

## Rollback en veiligheid

De migratie blijft niet-destructief. Oude versies zijn gedeactiveerd, niet verwijderd. Core Tick v0.9.1 draait volledig in `SHADOW` en voert geen fysieke Tesla- of boilerwrites uit.

De cut-over is op 17 augustus 2026 gevalideerd met een succesvolle schema-2.3-publicatie waarin State, Decision, Shadow, WW State en WW Control allemaal revision 157 gebruikten en `physicalWritePerformed=false` was.

> Laatste update: **17 augustus 2026 — Core Tick v0.9.1 cut-over.** Single-reader architectuur operationeel; State → Decision → Shadow → WW State → WW Control → Publish atomair; oude parallelle kernpaden gedeactiveerd; fysieke Control blijft uitgeschakeld.

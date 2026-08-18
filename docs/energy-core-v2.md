# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** centrale single-reader Core Tick actief in read-only SHADOW.  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.3`.  
**Contextlaag:** `EM v2 | 30 Context | Price + PV v0.1`.  
**Doel:** Homey als lichte edge-orchestrator; website en historie los van de fysieke regelroute.  
**Fysieke v2-writes:** geen.

Energy Core v2 gebruikt één centrale fysieke snapshot per vijf minuten. State, Decision, Shadow, warmwater-state, warmwater-Control en publicatie worden atomair uit dezelfde sample en revision berekend. Prijs- en PV-forecastcontext worden apart iedere 15 minuten bijgewerkt zonder extra device-scan.

## Harde architectuurregels

1. Homey leest fysieke apparaten centraal en maximaal één keer per Energy Core-cyclus.
2. Per Core Tick wordt maximaal één `getDevices()` en één `getVariables()` uitgevoerd.
3. Downstream-berekeningen gebruiken dezelfde in-memory snapshot; geen herhaalde device-scans.
4. Context die geen device-read nodig heeft mag apart, laagfrequent worden vernieuwd.
5. Iedere fysieke meetwaarde wordt één keer genormaliseerd in `EM2_State`.
6. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.
7. Websitebezoek veroorzaakt nul Homey-calls: de site leest uitsluitend gepubliceerde snapshots.
8. Historie en publicatie mogen geen extra device-scan veroorzaken.
9. State, Decision, Shadow en Control-intent horen bij dezelfde State-revision.
10. Verouderde context wordt niet als actuele waarheid gebruikt.
11. Een v2-Control-adapter mag pas fysieke writes krijgen nadat de shadowvalidatie voldoende betrouwbaar is.

## Actuele keten

```text
Prijs + PV forecast cards
        │ iedere 15 min
        │ geen device-scan
        ▼
EM v2 | 30 Context | Price + PV v0.1
        └── M7_* booleans + EM2_Context_UpdatedAt

Devices / meters / Easee + Homey Logic
        │
        │ Core Tick iedere 5 min
        │ 1 × getDevices()
        │ 1 × getVariables()
        ▼
EM v2 | 00 Core Tick | v0.9.3
        │
        ├── 10 State → EM2_State · revision N
        ├── 20 Decision → EM2_Decision · sourceRevision N
        ├── 80 Shadow → EM2_Shadow · sourceRevision N
        ├── 15 Warm Water State → EM2_WW_State · sourceRevision N
        ├── 60 Warm Water Control → EM2_Control_WW · sourceRevision N
        │                         GEEN fysieke write
        └── 90 Publish → energy-state-v2.json

Parallel, zonder device-read:
EM v2 | 70 History | Day Series v0.1 → energy-day-v2.json
```

## Actieve v2-kern

| Onderdeel | Uitvoering | Device-read | Device-write | Functie |
|---|---|---:|---:|---|
| Core Tick v0.9.3 | elke 5 min | **1 centrale scan** | **nee** | volledige actuele v2-regelketen |
| Price + PV Context v0.1 | elke 15 min | **nee** | nee | relatieve prijs- en PV-forecastsignalen + freshness |
| State | binnen Core Tick | geen extra | nee | P1, PV, Tesla/Easee, Equalizer, boiler en appliance-status normaliseren |
| Decision | binnen Core Tick | geen extra | nee | energy state, intent en prioriteit |
| Shadow | binnen Core Tick | geen extra | nee | intent vergelijken met geobserveerde toestand |
| Warmwater state | binnen Core Tick | geen extra | nee | dagdoel, looptijd en thermostaatgedrag afleiden |
| Warmwater Control | binnen Core Tick | geen extra | **nee** | opportunity-planner voor `BOILER_ON`, `BOILER_OFF` of `HOLD` |
| Publish | binnen Core Tick | geen extra | nee | revision-consistente GitHub-snapshot, gethrottled |
| History | parallel vanuit bestaande state | nee | nee | compacte dagreeks zonder extra device-scan |

## Context: prijs en PV forecast

De contextlaag evalueert iedere 15 minuten vier relatieve signalen:

- `M7_Price_Negative`: huidige stroomprijs is negatief;
- `M7_Price_Cheap_Next4h`: huidige prijs is goedkoper dan de komende vier uur;
- `M7_Price_Expensive_Next4h`: huidige prijs is duurder dan de komende vier uur;
- `M7_PV_Top4h`: huidig uur behoort tot de vier beste PV-forecasturen tussen 09:00 en 18:00.

Na de update wordt `EM2_Context_UpdatedAt` gezet. Core Tick gebruikt deze context alleen wanneer hij maximaal 35 minuten oud is. Bij ontbrekende of verouderde context werkt de warmwaterplanner conservatief: actuele netexport en harde catch-up blijven bruikbaar, maar prijs-/forecastsignalen worden genegeerd.

## Atomische revision-keten

`EM2_State` is de fysieke energie-state voor de regelcyclus. Een relevante verandering verhoogt de revision. Binnen dezelfde Core Tick worden Decision, Shadow, Warm Water State en Warm Water Control berekend met dezelfde `sourceRevision`.

De eerste v0.9.3-validatie op 18 augustus 2026 publiceerde schema 2.3 met gelijke revisions over State, Decision en Shadow en zonder fysieke writes.

## Warmwaterstate

Warmwatercontext wordt binnen de Core Tick opgeslagen in `EM2_WW_State` (`EM2_WW_STATE_V0.6`).

De state houdt onder andere bij:

- dagdoel `OP_TEMPERATUUR`;
- gelatchte `goalReachedToday` tot lokale dagwissel;
- bevestigde verwarmings- en low-power-fasen;
- huidige aaneengesloten relais-run;
- fallback/catch-up richting 19:00;
- kwaliteit van de huidige dagstate.

Voor thermostaatdetectie geldt:

```text
boiler aan + vermogen > 1500 W gedurende 15 min
    → opwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende 10 min
    → OP_TEMPERATUUR bereikt
```

Zodra `OP_TEMPERATUUR` die kalenderdag eenmaal is bereikt, blijft het dagdoel gehaald. Avondelijk warmwatergebruik opent het doel niet opnieuw (`sameDayReheat=false`).

## Warmwater Control — opportunity planner in PURE SHADOW

Warm Water Control wordt atomair binnen Core Tick v0.9.3 berekend en opgeslagen als `EM2_Control_WW` (`EM2_CONTROL_WW_V0.8`).

De veiligheids-guards zijn onder andere:

```text
readOnly      = true
deviceWrites  = false
stateFresh    = true
revisionMatch = true
wwStateFresh  = true
contextFresh  = true/false
```

### Huidig beleid

| Situatie | Shadow-intent | Prioriteit |
|---|---|---|
| elektrische boilermodus niet geselecteerd | `BOILER_OFF` indien nodig | MUST |
| dagdoel vandaag al bereikt | `BOILER_OFF` indien nodig | MUST |
| na 19:00 | geen nieuwe run / `BOILER_OFF` | MUST |
| catch-up noodzakelijk | `BOILER_ON` indien uit | MUST |
| vóór 09:30 en relais staat aan | `BOILER_OFF` | SHOULD |
| ≥2100 W actuele netexport | `BOILER_ON` | SHOULD |
| verse negatieve prijs | `BOILER_ON` | SHOULD |
| verse prijs goedkoper dan komende 4 uur | `BOILER_ON` | SHOULD |
| vers top-4 PV-forecastuur én ≥500 W export | `BOILER_ON` | SHOULD |
| lopende run <30 min | `HOLD` | MAY |
| na min-run, geen opportunity en >500 W import of prijs duidelijk ongunstig | `BOILER_OFF` | SHOULD |
| anders | `HOLD` / wachten | MAY |

De gewenste dagelijkse lijn is daarmee:

```text
ochtend warmwatergebruik
    → niet onmiddellijk herverwarmen
    → wachten op actuele PV-export, gunstige prijs of PV-forecastmoment
    → indien nodig tijdig catch-up richting 19:00
    → OP_TEMPERATUUR eenmaal bereikt
    → dagdoel gelatcht; geen heropwarming dezelfde dag
```

**Belangrijk:** alle `BOILER_ON`- en `BOILER_OFF`-uitkomsten zijn nog uitsluitend Shadow-intenties. Core Tick v0.9.3 bevat geen fysieke boiler-write.

## Ochtendobservatie 18 augustus

De expliciete legacyflows `Boiler aan` en `Boiler opwarmen` bleken uitgeschakeld. De ochtendverwarming werd dus niet door een actieve legacy-startflow veroorzaakt. Het boilerrelais stond fysiek nog aan van de vorige cyclus; na warmwatergebruik sloot de interne thermostaat opnieuw en kon het element vanzelf weer verwarmen.

De eerste v0.9.3 Shadow-run gaf voor die situatie terecht:

```text
action      = BOILER_OFF
priority    = SHOULD
opportunity = WAIT_MORNING
reason      = Ochtendherverwarming uitstellen; wachten op PV/prijs-opportunity
```

Dat gedrag kan pas fysiek worden afgedwongen nadat WW-Control expliciet van Shadow naar een gevalideerde write-route wordt gepromoveerd.

## Bekend aandachtspunt vóór fysieke WW-Control

De huidige fallbackteller gebruikt nog `boilerOnMinToday`: tijd waarin het relais aan staat. De ochtendobservatie liet zien dat dit kan oplopen terwijl de interne thermostaat af staat. Voor het primaire doel `OP_TEMPERATUUR` is dat niet bepalend, maar vóór fysieke Control moet de 240-minuten fallback worden gebaseerd op **werkelijk/bevestigd verwarmen** in plaats van alleen relais-aan-tijd. Dit staat daarom als expliciet validatiepunt vóór promotie naar fysieke Control.

## Publisher

Publicatie is onderdeel van dezelfde Core Tick en gebruikt dezelfde atomische snapshot:

```text
schema_version    = 2.3
publisher_version = EM2_CORE_PUBLISH_V0.9.3
control_mode      = SHADOW
```

GitHub-publicatie blijft begrensd op minimaal tien minuten bij relevante wijzigingen en een heartbeat uiterlijk na dertig minuten. De website veroorzaakt zelf geen Homey-calls.

## Control modes

| Mode | Betekenis |
|---|---|
| `SHADOW` | **huidige mode**: v2 observeert en berekent control-intent, geen v2 device-writes |
| `HYBRID` | alleen expliciet gevalideerde actuators mogen door v2 worden gestuurd |
| `ACTIVE` | v2 is leidend voor alle gemigreerde flexloads |

Voor WW-promotie naar fysieke Control moeten minimaal de opportunity-planner, context-freshness, thermostaatdetectie, fallback-accounting en een volledige dagcyclus betrouwbaar zijn gevalideerd.

## Load-budget

De operationele kern blijft Homey-zuinig:

- **1 × `getDevices()` per 5 minuten** in Core Tick;
- **1 × `getVariables()` per 5 minuten** in Core Tick;
- State, Decision, Shadow, WW State en WW Control vervolgens in-memory;
- context iedere 15 minuten zonder device-scan;
- geen aparte WW Actuator-poll;
- geen aparte Publisher-poll;
- GitHub-write maximaal iedere 10 minuten bij relevante wijzigingen;
- 30-minuten-heartbeat;
- website: nul Homey-calls.

> Laatste update: **18 augustus 2026 — Core Tick v0.9.3 + Price/PV Context v0.1.** Warmwater opportunity-planner actief in PURE SHADOW; ochtendherverwarming wordt uitgesteld ten gunste van PV/prijs wanneer de deadline dit toelaat.

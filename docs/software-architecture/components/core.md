---
component: core
title: Energy Core v2
version: 0.10.13
status: active
architecture_status: implemented
control_mode: SHADOW
last_verified: 2026-08-25
source:
  - homey:advancedflow:227f8d3b-7551-46dd-837d-1b8c69add824
  - docs/energy-core-v2.md
  - docs/data/energy-state-v2.json
---

# Energy Core v2

## 1. Doel

Energy Core v2 is de centrale, read-only orchestratie- en state-laag van het HEMS. De actieve Homey-flow is `EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)` en draait iedere vijf minuten. De Core leest per tick één devicesnapshot en één Logic-variabelensnapshot, construeert daaruit een consistente systeemstate, berekent beslis- en SHADOW-uitkomsten en maakt één publiceerbaar Energy State-contract gereed.

## 2. Scope

De Core omvat momenteel:

- P1/netmeting en fasewaarden;
- PV-productie uit SolarEdge en twee GoodWe-omvormers;
- Tesla/Easee elektrisch contextbeeld inclusief vermogen, requested/offered current, spanning en fasecurrents;
- Easee Equalizer context;
- boiler- en warmwaterstate;
- Quatt als `COMFORT_BASELOAD` en `OBSERVE_ONLY`;
- Quooker-status uit de aparte detectorlaag;
- wasmachine- en drogerstatus;
- contextsignalen voor PV en prijs;
- energie-/flexbudget;
- Tesla Decision en Shadow vergelijking;
- warmwater dagstate en SHADOW-control-intent;
- publicatiecontract `energy-state-v2.json`.

De Core voert zelf geen fysieke Tesla-, boiler- of Quatt-writes uit.

## 3. Trigger en uitvoering

De Advanced Flow heeft twee entry points:

- crontrigger: iedere 5 minuten;
- handmatige startkaart voor gecontroleerde runtime-tests.

Beide paden komen uit op exact dezelfde HomeyScript-actie. Hierdoor is de functionele uitvoerlogica identiek voor periodieke en handmatige runs.

## 4. Single-reader architectuur

Aan het begin van iedere run worden parallel exact deze twee centrale reads uitgevoerd:

```javascript
const [devices, vars] = await Promise.all([
  Homey.devices.getDevices(),
  Homey.logic.getVariables()
]);
```

Daarna worden alle downstream-berekeningen op dezelfde in-memory snapshot uitgevoerd. Dit voorkomt extra devicepolls binnen de Core en verkleint zowel Homey API-load als temporele inconsistentie binnen één Core-run.

## 5. Bronnen

### P1

P1 is autoritatief voor netto import/export en daarmee voor flex-control. De Core gebruikt een maximale P1-leeftijd van 60 seconden. Wanneer P1 niet vers is, gaat het flex-exportbudget fail-closed naar 0 W.

### PV

De Core leest SolarEdge, GoodWe 4200 en GoodWe 2000. Voor een betrouwbare afgeleide huisbalans gelden freshness- en synchronisatieguards:

| Bron | Maximale leeftijd |
|---|---:|
| SolarEdge | 20 min |
| GoodWe 4200 | 10 min |
| GoodWe 2000 | 10 min |
| Maximale onderlinge source-skew | 180 s |

Een source-skew maakt P1-gebaseerde flex-control niet ongeldig zolang P1 zelf vers is, maar onderdrukt wel de afgeleide `houseLoadW` en `otherHouseLoadW`.

### Quatt

Quatt is een bekende comfortlast. De Core leest elektrisch vermogen en diagnostische thermische/COP/statuswaarden, maar zet:

```text
role         = COMFORT_BASELOAD
controlMode  = OBSERVE_ONLY
controllable = false
```

### Tesla / Easee

v0.10.13 publiceert naast laadvermogen en laadstatus ook:

- `requestedA`;
- `offeredA`;
- `voltageV`;
- `l1A`, `l2A`, `l3A`;
- lifetime energy meter.

Deze uitbreiding is bedoeld als elektrische context voor de EV Power Adapter in SHADOW en veroorzaakt geen extra devicecalls.

## 6. Balans- en quality-model

De fysieke kandidaat-huislast wordt berekend als:

```text
physicalHouseCandidateW = PV_total_W + P1_grid_W
```

Daartegen worden bekende gemeten lasten gelegd: Tesla + boiler + Quatt + Quooker. Een betrouwbare afgeleide huisbalans vereist zowel geldige/fresh PV-bronnen, voldoende synchronisatie als een fysiek plausibele balans binnen 75 W tolerantie.

De belangrijkste statussen zijn:

- `P1_STALE_OR_INVALID`;
- `SOURCE_STALE_OR_MISSING`;
- `ASYNC_PV_RECONSTRUCTION_UNCERTAIN`;
- `NEGATIVE_HOUSE_BALANCE`;
- `KNOWN_LOADS_EXCEED_HOUSE`;
- `OK`.

Bij asynchrone PV/P1-bronnen blijft het P1-gebaseerde flexbudget bruikbaar, maar `Huis`/`Overig` wordt niet gereconstrueerd.

## 7. Energie- en flexbudget

De actuele budgetpolicy is:

| Parameter | Waarde |
|---|---:|
| Grid safety reserve | 200 W |
| Quatt idle reserve | 100 W |
| Quatt actief vanaf | 250 W |
| Quatt actieve rampreserve | max(350 W, 25% Quatt), max. 750 W |
| Boiler verwacht vermogen | 1900 W |
| Tesla opportunitydrempel | 800 W |
| PV forecast flexminimum | 500 W |
| Max discretionaire import | 4000 W |
| Batterijsteun | 0 W |

De centrale flexformule is:

```text
flexExportBudgetW = max(
  0,
  P1_export_W - 200 W grid reserve - Quatt ramp reserve
)
```

Alleen bij verse P1-data wordt dit budget vrijgegeven. Anders is het 0 W.

## 8. Tesla Decision in Core

De Core produceert `EM2_Decision` in SHADOW. De volgorde is in hoofdzaak:

1. deadline actief + latest-start bereikt + energie resterend → `MUST`;
2. deadline actief + voldoende flex-export, negatieve prijs of goedkope prijs met importbudget → `SHOULD`;
3. geen deadline + Tesla aangesloten + minimaal 1500 W flex-export → buffer-opportunity (`MAY`);
4. anders `HOLD`.

De Core berekent alleen intent en reden. Fysieke EV-acties vallen buiten deze component.

## 9. Shadow vergelijking

`EM2_Shadow` vergelijkt het berekende Tesla-intent met feitelijk geobserveerd laadgedrag. De vergelijking is `AGREE`, `DIFFER` of `NOT_COMPARABLE`. Ook hier geldt expliciet: read-only en geen actuatorwrite.

## 10. Warmwaterstate

De Core onderhoudt `EM2_WW_State` met onder andere:

- daglatch voor `OP_TEMPERATUUR_ONCE_PER_DAY`;
- confirmed-heating accounting boven 1500 W;
- goal-detectie na confirmed heating gevolgd door laag vermogen;
- maximaal 240 bevestigde verwarmingsminuten fallback;
- catch-up richting 19:00;
- run-startreden en run-lockcontext.

De actuele policy staat `sameDayReheat: true` toe, maar na bereikt dagdoel mag een nieuwe run alleen als gevalideerde post-goal `SHOULD`-opportunity ontstaan; deze mag nooit `MUST` worden en wist de daglatch niet.

## 11. Warmwater Control-intent

`EM2_Control_WW` is `SHADOW` en `readOnly`. De Core bepaalt `BOILER_ON`, `BOILER_OFF` of `HOLD` op basis van onder meer:

- elektrische boilermodus;
- 19:00 deadline;
- dagdoel/post-goal policy;
- catch-up;
- ochtendguard vóór 09:30;
- flex-export na Quatt-reserve;
- negatieve/goedkope prijs met horizon- en importbudgetguard;
- PV forecast;
- actieve run-lock;
- actuele import/context freshness.

De safety-sectie van het resultaat zet `physicalWritePerformed: false` en `quattWritePerformed: false`.

## 12. Publicatie

De Core construeert `EM2_Public_State` volgens publicatieschema `2.12` en zet `EM2_Publish_Due`. Publicatie zelf is gescheiden van Core en wordt door de Publisher-laag uitgevoerd.

Core gebruikt revision/signature-detectie om wijziging te bepalen en houdt een minimale dirty-publicatie-interval en heartbeat van 270 seconden aan. State-, Decision- en Shadow-revision worden aan dezelfde `sourceRevision` gekoppeld.

## 13. Outputs

Belangrijkste Logic-outputs van deze component:

- `EM2_State`;
- `EM2_Decision`;
- `EM2_Shadow`;
- `EM2_WW_State`;
- `EM2_Control_WW`;
- `EM2_Public_State`;
- `EM2_Publish_Due`;
- `EM2_Publisher_Status`.

## 14. Idempotency en write-safety

De Core is architectonisch read-only ten opzichte van fysieke apparaten. Herhaalde runs kunnen Logic-state opnieuw berekenen, maar verrichten geen Tesla-, boiler- of Quatt-actuatorwrites. Publicatie is revision/heartbeat-gebaseerd en de daadwerkelijke GitHub-write is gedelegeerd aan de Publisher.

De Homey-flow heeft één centrale scriptkaart, zodat periodieke en handmatige starts niet via verschillende implementatiepaden lopen.

## 15. Foutafhandeling en fail-safe gedrag

- ontbrekende/stale P1 → flexbudget 0 W;
- stale PV-bron → afgeleide huisbalans ongeldig;
- source-skew → huis/Overig onderdrukt, P1-flex blijft geldig als P1 vers is;
- context ouder dan 35 minuten → prijs/PV-context niet sturend;
- onbekende of onbetrouwbare waarden worden niet gebruikt om fysieke writes vrij te geven;
- Core zelf voert geen fysieke writes uit.

## 16. Status

| Eigenschap | Actuele waarde |
|---|---|
| Homey-flow | `EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)` |
| Enabled | ja |
| Broken | nee |
| Interval | 5 min |
| Control mode | `SHADOW` |
| Publisher schema | `2.12` |
| Device snapshots per run | 1 |
| Logic snapshots per run | 1 |
| Fysieke writes door Core | geen |
| Laatst tegen live Homey gecontroleerd | 2026-08-25 |

## 17. Migratienotitie

`docs/energy-core-v2.md` beschrijft nog Core v0.9.7 en is daarom niet meer normatief voor de actuele implementatie. Dit bestand (`components/core.md`) is vanaf v0.10.13 de architectuurmodule voor Core, gebaseerd op de live Advanced Flow. De legacy-pagina kan voorlopig blijven bestaan voor website/historische context totdat de migratie is afgerond.

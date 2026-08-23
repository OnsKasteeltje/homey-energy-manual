# Architectuuroverzicht

Deze pagina beschrijft de **actuele doelarchitectuur van Energy Core v2**. De oudere v1-opzet met losse State Collector, Allocator Shadow en meerdere zelfstandige publishers is niet meer leidend.

## 1. Hoofdstructuur

```text
FYSIEKE INSTALLATIE / VEILIGHEID
3×25 A · P1 · Easee Equalizer · lokale apparaatbeveiligingen
                    │
                    ▼
               METEN / STATE
P1 · PV · Easee · boiler · Quatt · overige relevante devices
                    │
           centrale Core-snapshot / 5 min
                    ▼
             ENERGY CORE v2
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      State      Decision     Shadow
                    │
             realtime intents
                    │
                    ▼
        afzonderlijk gevalideerde writers

Ondersteunende planningslaag buiten de fysieke control-loop:
Contract-/prijscontext · Tesla/WW-verplichtingen · PV-context
                    │
                    ▼
      24h Energy Planner SHADOW / 15 min
                    │
                    ▼
  kostenvensters + flexplanning + Victron SHADOW-scenario
                    │
                    └──► uitsluitend Logic-state / advies

Overige observability buiten de fysieke control-loop:
lichte event-assisted detectors · GitHub-publicatie · historie · website/app
```

De Energy Manager ligt niet in het fysieke stroompad. Installatieveiligheid en lokale hardwarebeveiliging blijven altijd hoger in de hiërarchie. De 24h-planner is nadrukkelijk geen writer en verandert de bestaande realtime regelketen niet.

## 2. Single-reader meetlaag

De Core draait op vijfminutencadans. Per Core Tick geldt als harde ontwerpgrens maximaal één volledige Homey-device-snapshot en één Logic-snapshot. Downstream-logica pollt dezelfde devices niet opnieuw wanneer de informatie al beschikbaar is.

Voor sneller veranderende signalen mag een **gerichte event-assisted detector** worden gebruikt wanneer de vijfminutencadans onvoldoende is. Zo'n detector mag geen nieuwe korte-interval `getDevices()`-scan introduceren.

De 24h-planner leest uitsluitend bestaande Logic-state/context en introduceert geen aanvullende devicepoller.

## 3. Homey structureel ontlasten

Bindende volgorde voor nieuwe functionaliteit:

```text
1. Signaal al in Core-snapshot? → hergebruik
2. Gerichte event-trigger mogelijk? → event-driven/event-assisted
3. Vijfminuten-Core kan het meenemen? → centrale read uitbreiden
4. Alleen anders → expliciete aanvullende poller
```

Website/app veroorzaakt nul Homey-devicecalls. Publicatie, historie en planning gebruiken reeds beschikbare toestand. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.

### Quooker als gevalideerd voorbeeld

```text
Homey Cooker-switch = autoritatief OFF/ON
              │
              ├── OFF → OFF
              └── ON  → ON_IDLE
                         │
relevant P1/L3-event ────┴──► HEATING + power_w
```

Actieve detector: `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING`.

De detector gebruikt geen volledige `getDevices()`-snapshot. Alleen de Cooker wordt gericht gelezen; na een relevant P1-event kan aanvullend één gerichte P1-read plaatsvinden. Historisering gebruikt dezelfde reeds gedetecteerde toestand.

## 4. Waarheidsbronnen en gescheiden meetvaliditeit

Voor de elektrische woningbalans en realtime flex-control is P1 leidend:

```text
P1 < 0 W → netto export
P1 > 0 W → netto import
```

Apparaatmetingen verklaren de belasting. Een belasting die al in P1 zit wordt niet nogmaals van P1 afgetrokken.

De meetvaliditeit is bewust gesplitst:

- `gridMeasurementValid`: verse/geldige P1-netmeting en **autoritatieve gate voor import, export en flex-exportbudget**;
- `derivedHouseBalanceValid`: gereconstrueerde P1+PV/huisbalans, uitsluitend voor `house_load`, residual/Overig en diagnostiek;
- afgeleide PV-/huisweergave mag degraderen zonder de geldige P1-meting ongeldig te verklaren.

Harde invariant:

```text
P1 geldig + SOURCE_SKEW in PV/huisreconstructie
→ flex-exportbudget blijft bruikbaar
→ afgeleide huis/Overig-diagnostiek degradeert
→ geen blokkade van P1-gebaseerde flexbesluiten

P1 stale/ongeldig
→ flex-exportbudget = 0 W (fail-closed)
```

Deze invariant geldt ook downstream in contract-aware Decision/WW-control. De website blijft observability en mag geen control-gates terugschrijven.

Voor Quooker zijn de waarheidsbronnen bewust gescheiden: Homey switch voor beschikbaar/aan-uit; P1/L3 voor daadwerkelijk verwarmen en vermogen.

## 5. Rollen van energieverbruikers

| Verbruiker | Architectuurrol | Flexibel? | Fysieke v2-Control |
|---|---|---:|---|
| Normaal huishouden | basislast | nee | n.v.t. |
| Quatt | `COMFORT_BASELOAD` | voorlopig nee | `OBSERVE_ONLY` |
| Boiler | flexload met comfortdoel | ja | Shadow/gevalideerde writer |
| Tesla | flexload met optionele deadline | ja | afzonderlijke writer |
| Quooker | comfort/gebruikspatroon + gemeten load | beperkt | bestaande Quooker-flows; detector observe-only |
| Victron-batterij | energie-/netbuffer | ja | later via Victron EMS/ESS; nu uitsluitend SHADOW-simulatie |

## 6. Quatt als comfortlast

De primaire elektrische Quatt-bron is `Quatt CIC.measure_power`. Quatt wordt uit de Core-snapshot gelezen en veroorzaakt geen extra Homey-poll. Thermisch vermogen/COP zijn diagnostiek en tellen niet mee als elektrische last.

```text
role         = COMFORT_BASELOAD
control_mode = OBSERVE_ONLY
controllable = false
```

## 7. Centraal vermogensbudget

State publiceert één gedeeld `energy_budget` zodat Tesla, boiler en toekomstige batterijlogica niet onafhankelijk dezelfde ruimte claimen.

```text
flex_export_budget
 = max(0,
       P1_export
       - grid_safety_reserve
       - quatt_ramp_reserve)
```

De actuele gridreserve is 200 W. Installatieveiligheid en Easee-loadbalancing blijven boven dit softwarebudget staan. Het budget wordt uitsluitend vrijgegeven bij `gridMeasurementValid=true`; een ongeldige afgeleide huisbalans verandert deze P1-gate niet.

## 8. Decision-prioriteit

```text
1. Installatieveiligheid en lokale hardwarebeveiliging
2. Comfort-baseload
3. Harde doelen/MUST
4. Economische flex-opportunities
5. Rest naar net / later Victron-batterijbeleid
```

De 24h-planner mag deze prioriteit niet omkeren. Harde Tesla- en warmwaterverplichtingen worden expliciet vastgelegd voordat economische vensters worden gerangschikt.

## 9. Contract-aware Decision baseline

Prijsoptimalisatie loopt via de geïsoleerde `EM2_ContractPrice_*` interface. De beslislaag ondersteunt `FIXED` en `DYNAMIC`; legacy M7-prijsclassificaties zijn geen prijsinput voor de contract-aware candidate.

```text
EM v2 | 40 Decision | Contract-aware v0.2
controlMode = SHADOW_CANDIDATE
noActuatorWrites = true
```

v0.2 past dezelfde split-validity-invariant toe als Core: `gridMeasurementValid` is de gate voor EXPORT/PV-flexopportunities; `derivedHouseBalanceValid` is diagnostisch.

## 10. Warm water en Tesla

Warm water gebruikt bronkeuze, timing en een afzonderlijk gevalideerde actuatorroute. Comfortdoel/deadline gaan vóór opportunistische optimalisatie. Na `goalReachedToday` vervalt de MUST/fallback-verplichting; een gevalideerde post-goal opportunity kan vóór 19:00 maximaal SHOULD zijn en wist de daglatch niet.

Tesla gebruikt hetzelfde gedeelde flexbudget; deadline/MUST gaat vóór opportunity-control. Easee Equalizer blijft autonoom de feitelijke laadstroom en lokale elektrische veiligheid begrenzen.

De bronkeuze `BOILER ↔ CV` blijft een pure advieslaag totdat parameters en writer veilig zijn vrijgegeven. `WW_Boilermodus` blijft operationeel leidend zolang de bronselector shadow-only is.

## 11. 24h Energy Planner — pre-Victron SHADOW

Actieve flow:

```text
EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW
flow-id = 27617767-0a64-43a3-9bcb-e34b0dd6a5c0
cadans = 15 min + 45 s stagger
controlMode = SHADOW
noActuatorWrites = true
```

Rollback:

```text
EM v2 | 45 Planner | 24h Energy Plan v0.1 [ROLLBACK]
flow-id = dedb7e15-8795-478b-995a-734f85025a74
enabled = false
```

De planner vormt de hogere-horizon planningsspine voor kostenoptimalisatie vóór de Victron-installatie. Hij leest bestaande Logic-state/context en verricht geen aanvullende devicepolls.

### 11.1 SHADOW-hardwaremodel

Het huidige simulatiescenario is expliciet:

```text
MultiPlus-II 48/5000/70-50
Cerbo GX MK2
VM-3P75CT
3 × Pylontech US5000
nominaal                 = 14,4 kWh
SHADOW SOC-band          = 20–90%
SHADOW bruikbaar venster = 10,08 kWh
SHADOW AC charge limit   = 3,3 kW
SHADOW AC discharge      = 3,3 kW
SHADOW η charge          = 95%
SHADOW η discharge       = 95%
SHADOW roundtrip         = 90,25%
```

SOC-band, vermogenslimiet en efficiënties zijn **simulatieaannames en geen commissioninginstellingen**. Definitieve waarden worden pas tijdens Victron/Pylontech commissioning vastgesteld.

### 11.2 Procesflow — actuele gecodeerde v0.2

```text
15-min trigger ──► 45 s stagger ──┐
                                  ▼
manual start ─────────────────► planner
                                  │
                                  ▼
Lees EM2_State + WW-state + uniforme prijscontext
+ PBTH kwartierprijzen + Tesla deadline + PV Top4h
                                  │
                                  ▼
                         Contracttype?
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
               DYNAMIC                           FIXED
      max. 96 geldige 15-min slots          statische context
      P25/P75 classificatie                 geen verzonnen slots
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                     Harde verplichtingen
            Tesla deadline + WW vóór 19:00/catch-up
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
       Tesla prijsvensters   WW kwartierallocatie   Batterij
       rangschikken vóór     op bestaand 1,9 kW     charge/discharge
       deadline; geen        boilermodel             candidates
       kWh/slot verzinnen                            op prijs
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  ▼
                 Bouw kwartier-SHADOW-acties
                 HOLD / kandidaat / preferred
                                  │
                                  ▼
       Theoretische arbitragekansen + upper bound
       geen geclaimde gerealiseerde besparing
                                  │
                                  ▼
Publiceer EM2_Energy_Plan_24h + EM2_Energy_Planner_Status
                                  │
                                  ▼
STOP — geen Victron/Easee/boiler/device writes
```

### 11.3 Datakwaliteit en begrenzing

De planner heeft nog geen actuele batterij-SOC, geen gedetailleerde 15-minuten huishoudlastforecast en geen gedetailleerde 15-minuten PV-forecast. `M7_PV_Top4h` is alleen samenvattende context. Daarom zijn batterijacties `CHARGE_CANDIDATE`/`DISCHARGE_CANDIDATE` en is `theoreticalUpperBoundEuro` uitsluitend een theoretische prijs-arbitrage-indicatie, **geen voorspelde gerealiseerde besparing**.

Tesla gebruikt de bestaande deadline en resterende kWh, maar v0.2 verzint geen laadvermogen of kWh per kwartier. Warm water hergebruikt het reeds gecodeerde boilermodel van circa 1,9 kW, dus 0,475 kWh per kwartier.

Ontbrekende toekomstige prijzen worden nooit aangevuld of geschat. DYNAMIC horizonstatus is `FULL_24H`, `PARTIAL` of `DIAGNOSTIC` afhankelijk van werkelijk beschikbare aaneengesloten kwartierprijzen.

Volledige flowdocumentatie: `energy-planner-24h-v0.2.md`.

## 12. Veiligheidshiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Lokale apparaatbeveiligingen
          ↓
Easee Equalizer
          ↓
Victron EMS / ESS (na installatie)
          ↓
Energy Core v2 + hogere-horizon Homey-orkestratie
          ↓
Gevalideerde huishoudelijke actuator-writers
```

De planner staat niet als veiligheidslaag in deze keten: hij is uitsluitend shadow-planning/advies.

## 13. Victron-doelarchitectuur

De geplande Victron-laag bestaat in het actuele SHADOW-scenario uit MultiPlus-II 48/5000, Cerbo GX MK2, VM-3P75CT en 3 × Pylontech US5000. De bestaande PV-omvormers blijven AC-gekoppeld. Victron/ESS wordt na installatie de primaire batterij-, SOC-, laad/ontlaad- en netveiligheidslaag. Homey blijft huishoudelijke orchestrator voor flexloads zoals Tesla en warm water en mag de Victron-safety/ESS-regels niet dupliceren of omzeilen.

Zolang Victron niet fysiek geïntegreerd is, geldt batterijsteun in realtime Core/control als 0 W. Alleen de 24h-planner simuleert het afgesproken scenario. Fysieke Victron-communicatie en writes worden pas na installatie/commissioning ontworpen en gevalideerd.

## 14. Publicatie, historie en website/app

Actuele runtimebaseline per 23 augustus 2026:

```text
Core              = EM v2 | 00 Core Tick | v0.10.12 (WW post-goal SHOULD)
Core cadence       = 5 min
Contract Context   = EM v2 | 30 Context | Contract Price Adapter v0.7
Contract Decision  = EM v2 | 40 Decision | Contract-aware v0.2
24h Planner        = EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW
Planner cadence    = 15 min + 45 s stagger
Planner outputs    = EM2_Energy_Plan_24h + EM2_Energy_Planner_Status
Planner rollback   = v0.1 [ROLLBACK], disabled
```

State, Decision en Shadow worden revision-consistent gepubliceerd. Website/app leest uitsluitend gepubliceerde toestand en blijft buiten de fysieke control-loop.

Voor de Live View geldt sinds 23 augustus een bewuste scopegrens: deze is observability, geen regelsysteem. Een fysiek incoherente/asynchrone PV/P1-combinatie mag als onbekend/degraded worden weergegeven; frontendlogica mag geen EMS-besluit beïnvloeden. Verdere optimalisatie van inverter-refresh uitsluitend voor het dashboard heeft geen prioriteit boven de EMS/Victron-doelstelling.

### CI/publicatie-invariant

Een schemawijziging moet atomair worden verwerkt in publisher, adapter, tests, fixtures en repositoryvalidator. CI controleert na bundling én na MkDocs-build dat de versiegebonden frontendbundle en het uiteindelijke Pages-artifact de actuele broncode/contractmarkers bevatten.

## 15. Control- en writerdiscipline

```text
State → Decision → Shadow/validatie → Control intent → exact één writer → actuator

Planning loopt parallel:
Context + State → 24h Planner SHADOW → plan/advies
                                      └── geen actuatorwrite
```

Observatie-, historie-, website-, detector- en plannerlagen verrichten geen fysieke writes tenzij een toekomstige component expliciet als gevalideerde writer is ontworpen en via een aparte cut-over is vrijgegeven.

Voor Easee geldt aanvullend: FLASH-belastende configuratieacties worden niet gebruikt voor frequente automatische regeling. Normale dynamische stroomsturing en de autonome Equalizer-functie blijven gescheiden van zulke persistente configuratiewrites.

## 16. Flowversionering en stable baseline

Bij een inhoudelijke wijziging wordt een hogere flowversie gemaakt, gevalideerd en geactiveerd; de voorganger wordt uitgeschakeld/SUPERSEDED of `[ROLLBACK]` gehouden wanneer rollbackwaarde bestaat. Maximaal één productieversie per automatische flowfamilie is actief.

**Documentatie-invariant:** procesflowdiagrammen beschrijven altijd de actuele gecodeerde stand. Bij iedere relevante flowwijziging worden code, tekst en procesdiagram in dezelfde wijzigingscyclus bijgewerkt.

## 17. Architectuur-review / regressiecriteria

Iedere wijziging wordt getoetst op:

- bijdrage aan het hoofddoel: laagste energiekosten en optimaal gebruik van de toekomstige Victron-installatie;
- geen onnodige complexiteit uitsluitend voor frontend/observability;
- extra Homey-load/API-calls;
- dubbele publishers/writers;
- correcte waarheidsbron;
- `gridMeasurementValid` versus `derivedHouseBalanceValid` correct gescheiden;
- P1-authoritatieve flex niet geblokkeerd door `SOURCE_SKEW` in afgeleide PV/huisdata;
- FIXED/DYNAMIC contractabstractie via `EM2_ContractPrice_*`;
- 24h-planner blijft SHADOW;
- simulatieaannames expliciet gescheiden van commissioningwaarden;
- geen gerealiseerde besparing claimen zonder SOC/load/PV-data die dit ondersteunt;
- Tesla/WW MUST-verplichtingen blijven boven economische optimalisatie;
- `WW_Boilermodus` productie-leidend zolang WW Source Advice shadow-only is;
- Victron/ESS eigenaar van batterij/SOC/netveiligheid, Homey eigenaar van huishoudelijke flex-orchestratie;
- Easee FLASH-belastende configuratieacties niet frequent automatisch gebruiken;
- revision- en schema-consistentie;
- fail-safe gedrag bij stale/onbekende data;
- testbaarheid en rollback;
- synchroniteit tussen broncode, procesdiagrammen, gegenereerde bundle en productie-artifact.

> Laatste update: **23 augustus 2026** — Core v0.10.12, Contract Price Adapter v0.7, Contract-aware Decision v0.2, pre-Victron 24h Energy Planner v0.2 SHADOW met 14,4-kWh 3×US5000-simulatiescenario; v0.1 disabled als rollback. Frontend blijft expliciet observability-only en procesdiagrammen zijn gelijkgetrokken met de actuele code.
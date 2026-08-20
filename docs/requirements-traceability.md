# Requirements Traceability — Home Energy Management System

_Status: 20 augustus 2026_  
_Bronbaseline: Integraal energierapport Victron ESS + Home Energy Management System v37_

## Doel

Dit document koppelt de projectrequirements expliciet aan de actuele procesflow, Homey-/software-implementatie en resterende vrijgavecriteria. Het is daarmee de vaste traceability-laag tussen **wat het systeem moet doen** en **wat daadwerkelijk is gebouwd/gevalideerd**.

Statuslabels:

- `VERIFIED` — runtime daadwerkelijk gecontroleerd;
- `IMPLEMENTED` — gebouwd en aanwezig;
- `SHADOW` — read-only/advies; geen fysieke actuatorwrite;
- `DECIDED` — bindend architectuur-/procesbesluit;
- `OPEN` — nog te valideren, kiezen of fysiek vrijgeven;
- `KNOWN / MONITOR` — bekend operationeel punt, geen huidige blocker;
- `SUPERSEDED` — niet langer leidend.

## 1. End-to-end procesflow

```text
Installatieveiligheid / lokale hardware
                ↓
Meten / State
P1 · PV · Easee · boiler · Quatt · appliances
                ↓
1 centrale Core-snapshot / revision
                ↓
Context / normalisatie
prijs · contract · PV forecast · kwaliteit
                ↓
Centraal energie-/flexbudget
                ↓
Decision
comfort → MUST/deadlines → economische opportunities
                ↓
Shadow / validatie
                ↓
Control intent
                ↓
exact één gevalideerde writer per actuator
                ↓
fysieke actuator

Buiten de fysieke control-loop:
GitHub-publicatie · historie · website/app · Contract History
```

Deze volgorde is de norm waaraan nieuwe code en flows worden getoetst.

## 2. Architectuur en meetlaag

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| ARCH-001 | Homey blijft huishoudelijke orkestratielaag; fysieke veiligheid staat erboven. | `docs/architectuur.md`; Core/Control-scheiding. | `DECIDED` | Blijvende invariant. |
| ARCH-002 | Victron wordt na installatie primaire batterij-/netregelaar; Homey blijft flexloads orkestreren. | Budgetmodel bevat batterij-interface; Victron-hardware als doelarchitectuur vastgelegd. | `DECIDED / OPEN` | Fysieke Victron-integratie ontbreekt nog. |
| ARCH-003 | Meten, beslissen en fysiek schrijven blijven gelaagd gescheiden. | State → Decision → Shadow → Control intent → writer. | `IMPLEMENTED` | Iedere nieuwe Control-route hiertegen reviewen. |
| LOAD-001 | Core-cadans is 5 minuten. | `EM v2 | 00 Core Tick | v0.10.4`. | `IMPLEMENTED` | Incidentele schedulerafwijking staat als KNOWN/MONITOR. |
| LOAD-002 | Maximaal 1× `getDevices()` per Core Tick. | Single-reader Core-architectuur. | `VERIFIED` | Geen downstream volledige device-scan toevoegen. |
| LOAD-003 | Maximaal 1× `getVariables()` per Core Tick. | Single-reader Core-architectuur. | `VERIFIED` | Geen downstream logic-scan toevoegen. |
| LOAD-004 | Downstream-verwerking hergebruikt dezelfde snapshot/revision. | State/Decision/Shadow revision-consistent gepubliceerd. | `VERIFIED` | Revision match blijft release-gate. |
| LOAD-005 | Website/app/history veroorzaken 0 Homey-devicepolling. | UI leest uitsluitend gepubliceerde data. | `IMPLEMENTED / VERIFIED` | Bij frontendwijzigingen expliciet bewaken. |
| LOAD-006 | Event-driven of Core-snapshot vóór aanvullende polling. | Architectuurrichtlijn; Quooker-route gebruikt lichte P1-signatuur. | `DECIDED / IMPLEMENTED` | Nieuwe poller alleen expliciet gemotiveerd. |

## 3. Waarheidsbronnen en energiebalans

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| GRID-001 | P1 is autoritatief voor netto import/export. | `grid.power_w`, import/export uit P1. | `VERIFIED` | Geen afgeleide bron mag P1 vervangen zolang P1 vers/geldig is. |
| GRID-002 | Verse P1-data blijft geldig als afgeleide PV/huisbalans stale/skewed is. | `grid_measurement_valid` los van `derived_house_balance_valid`; `SOURCE_SKEW`. | `VERIFIED` | UI moet dit onderscheid behouden. |
| GRID-003 | Apparaatvermogen wordt niet dubbel in P1 verwerkt. | Quatt wordt niet nogmaals van P1-export afgetrokken. | `IMPLEMENTED` | Nieuwe grootverbruikers op dubbel tellen toetsen. |
| GRID-004 | Flexbudget gebruikt netto P1-export minus reserves. | `flex_export_budget = max(0, P1_export - gridreserve - Quatt-rampreserve)`. | `IMPLEMENTED / VERIFIED` | Reservepolicy alleen gecontroleerd wijzigen. |
| GRID-005 | Direct gemeten waarden zijn gemeten; alleen afgeleide waarden zijn indicatief. | Live Stream bron-/kwaliteitslogica. | `IMPLEMENTED` | Doorlopende UI-QA. |
| GRID-006 | Standby/lekstroom <20 W geldt niet als actieve verbruiker. | Live device-state threshold. | `IMPLEMENTED` | Visuele regressietest behouden. |

## 4. Prioriteiten en centraal budget

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| DEC-001 | Prioriteit: veiligheid → comfort → MUST/deadline → economie → rest/net/batterij. | Centrale Decision-policy. | `DECIDED / IMPLEMENTED` | Geen economische rule mag MUST overrulen. |
| DEC-002 | Quatt is comfortlast, niet automatisch flexload. | `COMFORT_BASELOAD`, `OBSERVE_ONLY`, `controllable=false`. | `VERIFIED` | Fysieke Quatt-sturing alleen via aparte toekomstige policy. |
| DEC-003 | Gedeeld budget voorkomt dat Tesla/boiler dezelfde ruimte dubbel claimen. | `energy_budget` centraal in State. | `IMPLEMENTED` | Alle nieuwe flexloads op hetzelfde budget aansluiten. |
| DEC-004 | Grid safety reserve = 200 W. | Actuele budgetpolicy. | `IMPLEMENTED` | Wijziging vereist expliciet besluit. |
| DEC-005 | Quatt-rampreserve: 100 W idle; actief max(350 W, 25%), max 750 W. | Actuele budgetpolicy. | `IMPLEMENTED` | Runtimegedrag blijven valideren bij actief winterbedrijf. |
| DEC-006 | Max discretionaire import = 4.000 W. | `discretionary_import_budget_w`. | `IMPLEMENTED` | Geen installatieveiligheidslimiet; safety blijft hoger. |
| DEC-007 | Batterijsteun = 0 zolang Victron niet geïntegreerd is. | `battery_integrated=false`, support 0. | `VERIFIED` | Na Victron commissioning opnieuw valideren. |

## 5. Contract- en prijslogica

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| PRICE-001 | Alleen contracttypen `FIXED` en `DYNAMIC`. | Uniforme contractadapter. | `IMPLEMENTED / SHADOW` | Rolling validatie nog uitbreiden. |
| PRICE-002 | Beide contracttypen normaliseren naar één prijscontext. | Downstream hoeft contracttype niet zelf te interpreteren. | `IMPLEMENTED / SHADOW` | Agreementanalyse FIXED/DYNAMIC open. |
| PRICE-003 | FIXED gebruikt configureerbare import-/exporttarieven zonder PBTH-afhankelijkheid. | FIXED-adapter. | `IMPLEMENTED / SHADOW` | Tariefconfiguratie inhoudelijk blijven beheren. |
| PRICE-004 | DYNAMIC gebruikt PBTH/DAP15 en geen M7-prijsclassificatie als doelarchitectuur downstream. | DYNAMIC-adapter / Price Context. | `IMPLEMENTED / SHADOW` | Oude M7-afhankelijkheden uitfaseren waar nog aanwezig. |
| PRICE-005 | Ontbrekende prijs is `null`, nooit impliciet €0/kWh. | Null-safe prijscontext. | `IMPLEMENTED` | Harde regressieregel. |
| PRICE-006 | Vaste dagelijkse contractkosten zijn geen marginale optimalisatie-input. | Contractpolicy. | `DECIDED` | Geen downstream opname in start/stopbeslissing. |
| PRICE-007 | Prijshorizon bepaalt FULL / INTRADAY / DIAGNOSTIC. | WW Planner/Price Context gates. | `IMPLEMENTED / SHADOW` | Shadowdata blijven verzamelen. |
| PRICE-008 | Bij onvoldoende/stale prijscontext terugvallen op comfort/PV/catch-up. | Fail-safe plannerpad. | `IMPLEMENTED / SHADOW` | Voor fysieke cut-over aantoonbaar testen. |
| PRICE-009 | Contract History verzamelt rolling kwartierdata zonder devicepolling/writes. | Contract History v0.1. | `IMPLEMENTED / SHADOW` | Voldoende FIXED + DYNAMIC samples vereist. |

## 6. Warm water

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| WW-001 | Procesvolgorde: warmwatervraag → BOILER/CV-bronkeuze → timing → writer. | WW Source Advice vóór WW timing/control. | `IMPLEMENTED / SHADOW` | Fysieke bronwrite nog niet vrijgegeven. |
| WW-002 | Primair dagdoel: `OP_TEMPERATUUR_ONCE_PER_DAY`. | `EM2_WW_STATE_V0.8`. | `VERIFIED` | Dagreset op lokale kalenderdag behouden. |
| WW-003 | Confirmed-heating gebruikt werkelijk boilervermogen, niet alleen relaisduur. | Heating threshold/accounting in WW State. | `IMPLEMENTED / VERIFIED` | Sensor-/thresholdwijzigingen opnieuw valideren. |
| WW-004 | Fallback = 240 minuten confirmed heating. | WW State policy. | `IMPLEMENTED` | Comfortdoel blijft leidend. |
| WW-005 | Deadline = 19:00. | WW Control policy. | `IMPLEMENTED / SHADOW` | Catch-up vóór opportunity. |
| WW-006 | Na `goalReachedToday` geen verplichte heropwarming dezelfde dag. | `sameDayReheat=false`. | `VERIFIED` | Eventuele toekomstige demand-trigger apart ontwerpen. |
| WW-007 | Bronkeuze vergelijkt marginale kosten per bruikbare kWh warmte. | WW Source Advice. | `IMPLEMENTED / SHADOW` | Gaswaarde, CV-/boilerrendement valideren. |
| WW-008 | PV is economisch niet automatisch gratis; gemiste terugleverwaarde telt als opportunity cost. | WW Source Advice. | `IMPLEMENTED / SHADOW` | Parameter-/contractvalidatie vereist. |
| WW-009 | Bronselector gebruikt hysterese en fail-safe `KEEP_CURRENT` bij slechte inputs. | Source Advice guards. | `IMPLEMENTED / SHADOW` | Hystereseparameter nog formeel bevestigen. |
| WW-010 | `WW_Boilermodus` blijft operationeel leidend zolang Source Advice SHADOW is. | Geen fysieke mode-write uit Source Advice. | `VERIFIED` | Pas na expliciete cut-over wijzigen. |

## 7. Tesla / Easee

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| EV-001 | Tesla is flexload; deadline/MUST gaat vóór opportunistische optimalisatie. | Decision-prioriteit. | `DECIDED / IMPLEMENTED` | Deadlineberekening blijvend end-to-end testen. |
| EV-002 | PV-opportunity gebruikt `flex_export_budget`, niet kale export. | Tesla Decision-pad. | `IMPLEMENTED` | Geen parallelle exportberekening introduceren. |
| EV-003 | Goedkoop importladen blijft binnen discretionair importbudget. | Centrale budgetinput. | `IMPLEMENTED / SHADOW/Control-afhankelijk` | Fysieke writerpolicy apart bewaken. |
| EV-004 | Easee Equalizer blijft autonome harde EV-loadbalancing. | Lokale safetylaag. | `VERIFIED` | Homey mag deze grens nooit overrulen. |
| EV-005 | Werkelijk laadvermogen is belangrijker voor classificatie dan alleen requested current. | State/Live classificatie. | `DECIDED / IMPLEMENTED` | Meetbronkwaliteit blijven tonen. |
| EV-006 | Exact één automatische writer naar Easee in eindtoestand. | Writerdiscipline/migratiebeleid. | `DECIDED / OPEN` | Voor volledige fysieke cut-over writerinventaris valideren. |

## 8. Appliances, Quooker en live classificatie

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| APP-001 | Directe device-status heeft voorrang op inference waar betrouwbaar beschikbaar. | AEG washer/dryer direct status. | `IMPLEMENTED / VERIFIED` | Alleen ontbrekend vermogen mag indicatief worden afgeleid. |
| APP-002 | Niet-herleidbare kleine restlast wordt `Overig klein`, niet aan inactief apparaat toegewezen. | Live Stream classificatie. | `DECIDED / IMPLEMENTED` | Balans-QA voortzetten. |
| APP-003 | Quooker-detectie mag Homey niet belasten met snelle volledige device-scans. | P1/L3-signatuur en architectuurrichtlijn. | `IMPLEMENTED` | Geen regressie naar snapshot-polling. |
| APP-004 | Quooker-status mag inferred zijn maar bron/freshness moet expliciet blijven. | `P1_L3_SIGNATURE`, inferred/fresh velden. | `IMPLEMENTED` | End-to-end detectiekwaliteit blijven observeren. |

## 9. Website/app en historie

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| UI-001 | Refresh bij boot/open. | App-refreshlogica. | `IMPLEMENTED` | Regressietest bij PWA updates. |
| UI-002 | Periodieke datarefresh iedere 5 minuten. | Frontend refreshlaag. | `IMPLEMENTED` | Geen Homey-call toevoegen. |
| UI-003 | Refresh bij visibility/pageshow/focus/online. | Frontend lifecycle refresh. | `IMPLEMENTED` | Caching blijft aandachtspunt. |
| UI-004 | Pull-to-refresh forceert datarefresh; reload alleen is onvoldoende. | App-refresh implementatie. | `IMPLEMENTED` | Blijvend testen op iOS/PWA. |
| UI-005 | Freshness onderscheidt actueel/vertraagd/verouderd. | UI freshness-indicatie. | `IMPLEMENTED` | Upstream scheduler kan incidenteel stale zijn; KNOWN/MONITOR. |
| UI-006 | History↔Live navigatie mag geen oude cached status terugbrengen. | Refresh/cache-guards. | `IMPLEMENTED` | Regressiegevoelig; QA behouden. |
| UI-007 | Live Stream moet balans, bronlabels en >20 W-drempel correct tonen. | Live frontend. | `IMPLEMENTED / OPEN QA` | Doorlopende visuele/functionele QA. |

## 10. Victron ESS / hardware

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| VIC-001 | MultiPlus-II 48/5000 als 1-fase ESS op L1. | v37 hardwarebaseline. | `DECIDED` | Installatie/commissioning nog uitvoeren. |
| VIC-002 | Cerbo GX MK2 als GX/EMS-platform. | v37 hardwarebaseline. | `DECIDED` | Netwerkstabiliteit commissioning testen. |
| VIC-003 | VM-3P75CT centrale 3-fasemeting. | v37 hardwarebaseline. | `DECIDED` | CT-fasevolgorde en richting fysiek verifiëren. |
| VIC-004 | GX Touch optioneel. | v37 besluit. | `DECIDED` | Geen blocker. |
| VIC-005 | AC-coupled is werkhypothese; DC-route niet vrijgegeven zonder nieuwe Vmp/Voc/stringvalidatie. | v37 vervangt historische SmartSolar/DC-voorkeur. | `DECIDED / OPEN` | Definitieve topologie vóór bestelling bevestigen. |
| VIC-006 | Definitieve batterijbank blijft open tot capaciteit, continu vermogen en BMS/DVCC zijn bevestigd. | v37 open punt. | `OPEN` | Na topologiekeuze dimensioneren. |
| VIC-007 | Na installatie wordt Victron primaire batterij-/netregelaar en levert batterijbudget aan Homey. | Doelarchitectuur. | `DECIDED / OPEN` | Integratie en commissioning vereist. |

## 11. Safety en fysieke Control

| ID | Requirement | Implementatie / bewijs | Status | Vrijgave / aandachtspunt |
|---|---|---|---|---|
| SAFE-001 | Installatieveiligheid en lokale hardwarebeveiligingen staan altijd boven Homey. | Architectuurhiërarchie. | `DECIDED` | Harde invariant. |
| SAFE-002 | Geen fysieke Quatt-sturing zonder aparte policy + Shadow-validatie. | Quatt `OBSERVE_ONLY`. | `VERIFIED` | Geen bestaande Quatt-action cards gebruiken voor EMS zonder nieuw besluit. |
| SAFE-003 | Contract History, uniforme prijscontext en WW Source Advice schrijven nooit actuators. | Read-only/SHADOW. | `VERIFIED / IMPLEMENTED` | Harde invariant. |
| SAFE-004 | Per fysieke actuator uiteindelijk exact één automatische writer. | Writerdiscipline. | `DECIDED / OPEN` | Voor iedere cut-over writerinventaris + rollbackbewijs. |
| SAFE-005 | Iedere nieuwe fysieke Control-route eerst SHADOW en daarna gecontroleerde cut-over. | Change-control. | `DECIDED` | Release-gate. |
| SAFE-006 | Bij ontbrekende/stale optimalisatie-inputs fail-safe terug naar comfort, deadlines en meetbare werkelijkheid. | Context/WW guards; P1-validiteit losgekoppeld. | `IMPLEMENTED / SHADOW` | Fysieke writerpas na fail-safe test. |

## 12. Bekende operationele punten

| ID | Punt | Status | Beleid |
|---|---|---|---|
| OPS-001 | Incidenteel gemiste 5-min Core/publicatie-trigger waargenomen. Handmatige Core-run werkte direct en publiceerde revision-consistent. | `KNOWN / MONITOR` | Geen extra schedulerarchitectuur bouwen tenzij herhaald in normaal bedrijf. |
| OPS-002 | `docs/energy-core-v2.md` bevat nog historische v0.9.7/schema 2.5 status in delen. | `OPEN DOC` | Actualiseren naar v0.10.4/schema 2.10; inhoudelijke principes blijven bruikbaar. |
| OPS-003 | Live Stream/caching is regressiegevoelig. | `OPEN QA` | Blijvend functioneel + visueel testen zonder extra Homey-load. |

## 13. Open vrijgavepad

De resterende stappen naar volledig gerealiseerd EMS zijn, in deze volgorde:

1. definitieve Victron PV-topologie technisch bevestigen;
2. batterijbank en vermogens-/BMS-limieten vastleggen;
3. Contract History voldoende FIXED/DYNAMIC shadowdata laten verzamelen en agreement beoordelen;
4. WW Source Advice-parameters (gaswaarde, CV-rendement, boilerrendement, hysterese) valideren;
5. per actuator writerinventaris, shadowbewijs en rollbackplan afronden;
6. fysieke cut-overs één voor één uitvoeren;
7. na Victron commissioning batterij-/netregeling koppelen aan het bestaande centrale budget;
8. Live Stream en History als observatielaag regressievrij houden.

## 14. Change-control / Definition of Done

Een relevante wijziging is pas projectmatig afgerond wanneer:

```text
requirement geraakt?
      ↓
traceability-ID bijgewerkt
      ↓
architectuurlaag gecontroleerd
      ↓
Homey-loadimpact gecontroleerd
      ↓
Shadow/test indien fysieke sturing
      ↓
runtimevalidatie
      ↓
documentatie + projectbaseline bijgewerkt
      ↓
oude route SUPERSEDED indien van toepassing
```

Bij iedere nieuwe functionele requirement wordt een nieuwe unieke ID aan deze matrix toegevoegd. Daarmee blijft de procesflow aantoonbaar herleidbaar naar de projectrequirements in plaats van alleen impliciet aanwezig in code of chatbesluiten.

> Canonieke status: **proceslogica en architectuur zijn grotendeels in lijn met v37; resterende oranje punten zijn hoofdzakelijk SHADOW-vrijgave, writer-cut-over en fysieke Victron-integratie — geen fundamentele herbouw van de beslisboom is momenteel vereist.**

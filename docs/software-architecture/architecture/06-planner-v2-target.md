---
component: planner-v2-target
title: Planner V2 Target Architecture
version: 0.6.0
status: draft
architecture_status: planned
last_verified: 2026-09-20
source:
  - src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py
  - src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan_start6.py
  - services/pi/planner/heating/build_heating_preheat_plan.py
  - services/pi/planner/warm-water/build_ww_plan.py
  - services/pi/api/status/server.py
  - deploy/systemd/ems-forecast-chain.service
  - src/pi/ems-runtime/planner/control-authority.json
  - src/pi/ems-runtime/planner/contract-policy.json
---

# Planner V2 Target Architecture

## Status en doel

Dit document legt de overeengekomen **target architecture** voor Planner V2 vast. Het beschrijft nog niet de actuele productie-runtime. De bestaande hardened dynamic planner blijft productie-authority totdat een gecontroleerde V2-cutover is uitgevoerd en gevalideerd.

Planner V2 moet de huidige plannerketen vereenvoudigen zonder de bestaande authority- en safetygrenzen te verzwakken. De kernregel is:

> **Policy -> requirements + PV opportunity -> joint planning -> bounded realtime execution. P1 is de actuele energiewaarheid.**

## Architectuur

```mermaid
flowchart TD
  POLICY[Policy / modes<br/>FIXED ENGIE contract<br/>WW mode CV or BOILER]

  EVREQ[EV requirement<br/>connected / remaining kWh<br/>deadline / max A]
  HONEY[Honeywell baseline<br/>current + future setpoints]
  WWREQ[WW electric requirement<br/>only when mode = BOILER]

  WEATHER[Weather input]
  PVMODEL[PV forecast model]
  PV[PV forecast + confidence]

  EVFLEX[EV planning candidates<br/>PV opportunity + deadline reserve]
  HEATFLEX[Heating flex candidates<br/>bounded advance of Honeywell UP transition]

  JOINT[Joint Planner V2<br/>rolling 24h / 96 x 15 min]
  CONTROL[/control/current<br/>current slot + validUntil<br/>targets / bounded envelopes]
  HOMEY[Homey execution + safety<br/>single physical writers]
  P1[P1 live energy balance<br/>realtime authority]
  DEV[Devices]

  HISTORY[History / observability / replay]

  POLICY --> EVFLEX
  POLICY --> HEATFLEX
  POLICY --> WWREQ

  EVREQ --> EVFLEX
  HONEY --> HEATFLEX

  WEATHER --> PVMODEL
  PVMODEL --> PV
  PV --> EVFLEX
  PV --> HEATFLEX

  EVFLEX --> JOINT
  HEATFLEX --> JOINT
  WWREQ --> JOINT

  JOINT --> CONTROL
  CONTROL --> HOMEY
  P1 --> HOMEY
  HOMEY --> DEV

  PV -.-> HISTORY
  JOINT -.-> HISTORY
  P1 -.-> HISTORY
```

## 1. Policy en modes

Policy is vooraf gegeven context en wordt niet door de planner gekozen.

Voor de huidige productiesituatie:

- contract mode: `FIXED`;
- contract id: `ENGIE_3Y_2026_2029`;
- dynamische prijzen zijn geen productie-optimalisatiebron;
- WW mode is een strategische keuze buiten Planner V2: `CV` of `BOILER`;
- de Seasonal Advisor staat boven de planner en mag adviseren over CV versus BOILER; Planner V2 kiest deze mode niet.

Als WW mode `CV` is, bestaat er geen elektrische WW-flexload voor de joint planner. Als WW mode `BOILER` is, mag een WW-requirement als flex-input worden toegevoegd.

## 2. Requirements zijn harde grenzen

Requirements beschrijven wat uiteindelijk bereikt moet worden. De planner mag ze niet stilzwijgend wijzigen.

### EV

De EV-requirement bevat ten minste:

- connected/available state;
- resterende benodigde energie;
- deadline;
- maximaal toegestaan laadvermogen/stroom.

Dezelfde EV-requirement ondersteunt twee laadwijzen:

1. **Opportunistisch laden** — energie eerder laden wanneer PV beschikbaar is.
2. **Deadline-laden** — de resterende energie tijdig laden zodat de harde deadline gehaald kan worden, ook wanneer daarvoor netenergie nodig is.

Opportunistisch geladen energie verlaagt de resterende deadlinebehoefte. De deadline is de harde constraint; PV is optimalisatie. Een verwachte PV-opbrengst mag daarom nooit de deadlinegarantie vervangen.

### Heating / Honeywell

Honeywell blijft baseline-authority voor comfort:

- huidige setpoint;
- toekomstige setpoint;
- tijdstip van de toekomstige wijziging.

Planner V2 mag een door Honeywell reeds gevraagde toekomstige **UP-transition** binnen begrensde regels eerder uitvoeren om PV te benutten. De planner mag geen hogere comforttemperatuur verzinnen en geen Honeywell-doel vervangen.

Een toekomstige Honeywell-verhoging is daarmee vergelijkbaar met een requirement: het doel en vereiste tijdstip komen van Honeywell; alleen het toegestane moment van energie-inzet kan naar voren worden gehaald.

## 3. PV Forecast is upstream opportunity input

PV Forecast is één samenhangend domein:

```text
weather -> PV model -> PV forecast + confidence
```

De joint planning moet niet zelfstandig verspreide weatherlogica bevatten. Weather is broninput voor het PV-model. De planner ontvangt de resulterende PV-verwachting en confidence.

PV Forecast voedt expliciet zowel:

- de keuze voor opportunistisch EV-laden;
- de beslissing of een toekomstige Honeywell-verhoging zinvol naar voren kan worden gehaald.

Heating Flex staat daarom **niet vóór** PV Forecast. PV Forecast is een noodzakelijke opportunity-input voor het vormen/rangschikken van heating-preheat candidates.

Confidence is advisory. Lage confidence mag optimalisatie conservatiever maken, maar is geen globale stopconditie.

## 3.1 PV Forecast V2 contract

Planner V2 consolideert weather-, PV-model- en confidence-logica tot één read-only forecastcontract. De forecast voorspelt **PV-productie**, niet gegarandeerde huishoudelijke export.

Beoogd schema: `EMS_PI_PV_FORECAST_V2`.

Minimaal documentcontract:

```text
schema
generatedAt
mode = READ_ONLY
slotMinutes = 15
horizonSlots = 96
model
slots[]
```

Minimaal per slot:

```text
start
pvForecastW
confidence
confidenceComponents
modelBasis
```

`confidenceComponents` mag onder meer forecast-consistency, weers-/bewolkingsstabiliteit, horizon en recente lokale forecast-accuracy bevatten. Confidence is uitsluitend advisory en wordt nooit een globale execution gate.

Het V2 PV-model mag bestaande bruikbare onderdelen hergebruiken, waaronder:

- 15-minuten weather/radiation als modelinput;
- array-/oriëntatie-informatie en GTI waar die aantoonbaar modelwaarde heeft;
- de historische lokale PV-envelope/calibratie;
- vergelijking van forecast met lokaal gemeten PV voor modelaccuracy.

Weather blijft daarmee intern bronmateriaal voor PV Forecast. De Joint Planner hoeft geen losse weather-feed te consumeren voor PV-beslissingen. Buitentemperatuur mag afzonderlijk naar een toekomstig Heating Thermal Model gaan; dat maakt weather geen tweede PV-plannerinput.

### Geen forecast van gegarandeerde export

Planner V2 definieert niet langer:

```text
forecastExportW = pvForecastW - baseLoadForecastW - quattForecastW
```

als centrale productie-input.

Historical baseload en standalone Quatt power forecast zijn geen noodzakelijke onderdelen van het PV Forecast V2-contract. Een PV Forecast van 4 kW betekent daarom: ongeveer 4 kW PV-productie wordt verwacht. Het betekent niet dat 4 kW export gegarandeerd beschikbaar zal zijn.

Vooruitkijkend gebruikt de Joint Planner deze productieforecast om opportunity-kandidaten en onderlinge allocatie te organiseren. Tijdens uitvoering autoriseert de actuele P1-balans de werkelijke opportunistische energie-opname.

### Relatie met P1

PV Forecast en P1 hebben verschillende rollen:

- **PV Forecast:** vooruitkijkende opportunity en voorbereiding;
- **P1:** actuele import/export en realtime authority.

Een slechte forecast mag dus niet verhinderen dat werkelijk gemeten P1-export wordt benut. Omgekeerd mag voorspelde PV niet zelfstandig opportunistische netimport rechtvaardigen wanneer P1 op dat moment geen overschot laat zien.

De forecast mag wel gebruikt worden om stateful/traag reagerende flex vooraf voor te bereiden, zoals een geldige Heating Flex-kandidaat. De daadwerkelijke opportunistische uitvoering blijft begrensd door de P1-authorityregels en de specifieke actuator-/comfortconstraints.

### V2 commissioning history

PV Forecast V2 bouwt vanaf commissioning een schone validatieset op. Iedere shadow-run wordt met zijn oorspronkelijke `generatedAt`, slot, forecast en confidence gearchiveerd. Modelaccuracy wordt niet afgeleid uit live inverter-power.

Werkelijke PV voor latere validatie komt uit afgesloten, gevalideerde cumulatieve productie-intervallen. Ontbrekende, gap- of discontinuity-data leveren geen trainingspunt op. De initiële `recentLocalAccuracy` blijft een neutrale prior totdat voldoende gesloten V2-observaties beschikbaar zijn. Deze leerketen is read-only en heeft geen control-authority.

## 3.2 EV Opportunity V2 — eenvoudige realtime regeling

Planner V2 neemt de oude EV-opportunity-score-, window- en bufferlagen niet over. De functionele invariant is:

> **Forecast kiest alleen nu-of-later in de grijze zone; P1 autoriseert de actuele opportunity; een rolling 5-minutenmeting moduleert symmetrisch; de deadline garandeert het einddoel.**

### Twee opportunity-modi

Bij een aangesloten/beschikbare EV gelden twee expliciete opportunity-modi:

1. **GRAY_OPPORTUNITY** — actuele P1-export ligt tussen `2000 W` en het minimale 3-fase laadvermogen van 6 A (`EV_W_PER_A * 6`, nominaal circa `4140 W`). Omdat 6 A dan gedeeltelijke netimport veroorzaakt, mag deze mode alleen starten wanneer de vooruitkijkende PV Forecast binnen de relevante beschikbare/deadlinehorizon geen duidelijk betere normale PV-opportunity laat zien. Forecast heeft hier uitsluitend de rol **nu versus later**.
2. **NORMAL_PV_OPPORTUNITY** — actuele P1-export is ten minste voldoende voor 6 A. Deze mode start direct op basis van P1; forecast-confidence is geen realtime gate.

Onder `2000 W` actuele P1-export start geen opportunistische laadsessie. Harde deadline-lading staat los van deze startregels.

Een actieve `GRAY_OPPORTUNITY` promoveert naar `NORMAL_PV_OPPORTUNITY` zodra de beschikbare PV-capaciteit het 6 A-minimum bereikt. Na promotie gelden de normale regels; de sessie blijft niet kunstmatig grijs.

### Modulatie tijdens laden

De realtime EV-opportunityregeling draait in de bestaande Homey PI Bridge op de reeds aanwezige één-minuuttrigger en introduceert geen extra polling of sub-minute control-loop. De normale Homey→Pi Core-state publicatie blijft 300 seconden; die transportcadans wordt niet versneld voor EV-modulatie.

Pi bepaalt strategisch of EV-opportunity is toegestaan en publiceert daarvoor een begrensde mode/envelope (OFF, GRAY of NORMAL, naast de harde deadline-requirement). Homey wordt daarmee geen tweede planner: Homey bepaalt uitsluitend het actuele numerieke laadvermogen binnen de door Pi toegestane mode.

Iedere minuut leest Homey rechtstreeks de actuele P1 `measure_power` en het werkelijke Easee/EV-vermogen. Daarbij is Homey P1 `measure_power` positief bij netimport en negatief bij netexport. Het beschikbare PV-vermogen tijdens laden wordt daarom executor-side gereconstrueerd als:

    availablePvW = max(0, -p1MeasurePowerW + actualEvPowerW)

Dit is equivalent aan `actualEvPowerW + p1ExportW - p1ImportW` uit het canonical state-model.

    availablePvW = actualEvPowerW + p1ExportW - p1ImportW

Homey bewaart hiervoor uitsluitend lokale executor-state: maximaal de laatste vijf timestamped één-minuutsamples van `availablePvW`. De modulatiewaarde is het rolling gemiddelde van die maximaal vijf samples. Deze samplebuffer is geen planner-state, creëert geen nieuwe authority en mag geen actuator schrijven buiten de bestaande `EM2_Power_Intent -> adapter -> gate -> actuator` keten.

Een opportunity-start hoeft niet eerst vijf minuten te wachten: de actuele P1-meting autoriseert de start volgens de GRAY/NORMAL-startregels. Zodra de opportunity actief is, wordt het rolling gemiddelde gebruikt voor stabilisatie en symmetrische modulatie. Dat gemiddelde wordt iedere regelcyclus rechtstreeks vertaald naar het passende gehele ampèrage. De omzetting is **symmetrisch**: omhoog en omlaag gelden exact dezelfde regels; er is geen verplichte stap van 1 A per cyclus en geen aparte up/down-delay.

Voor PV-opportunity geldt:

- minimum laadstroom: `6 A`;
- maximum opportunity-laadstroom: `11 A`;
- het berekende gehele ampèrage mag in één regelcyclus direct naar een hoger of lager passend niveau binnen `6..11 A` gaan;
- de rolling 5-minutenwaarde is de primaire demping tegen pingelen; extra gestapelde qualification windows, confidence-gates, import-penalty scoring of richtingafhankelijke buffers worden niet toegevoegd.

### Verschillende ondergrens per actieve mode

De stop-/vasthoudgrens hoort bij de mode waarin de opportunity zich bevindt:

- `GRAY_OPPORTUNITY`: 6 A mag bewust worden vastgehouden zolang het rolling 5-minuten beschikbare PV-vermogen ten minste `2000 W` is. Onder die grens eindigt de grijze opportunity, tenzij een harde deadline laden vereist.
- `NORMAL_PV_OPPORTUNITY`: de 2 kW-uitzondering geldt **niet**. De normale opportunity wordt alleen gedragen zolang het rolling 5-minuten beschikbare PV-vermogen ten minste het minimale 6 A-laadvermogen kan dragen. Onder die grens eindigt de normale opportunity, tenzij een harde deadline laden vereist.

Hiermee kan een normale PV-opportunity niet ongemerkt veranderen in structureel gedeeltelijk netladen. Alleen een expliciet door forecast geaccepteerde grijze opportunity mag dat doen.

### Deadline en safety

Opportunistisch geladen energie verlaagt `remainingKWh`. Wanneer de harde deadline dit vereist, neemt deadline-laden over en mag netimport plaatsvinden. De `11 A`-limiet is uitsluitend de bovengrens voor PV-opportunity; deadline-laden blijft begrensd door de geldige deadline-`maxA`.

De rolling 5-minutenregeling is optimalisatie, geen hardware-safety. Een afzonderlijke eenvoudige bescherming tegen **forse actuele onverwachte netimport** mag onmiddellijk terugregelen zonder vijf minuten op het gemiddelde te wachten. De exacte drempel voor deze bescherming wordt pas na shadow-observatie vastgelegd en mag geen tweede opportunity-optimalisatiealgoritme worden.

Realtime P1 blijft canonical authority en Homey/Easee blijft de execution/safety boundary met exact één fysieke writer.

## 4. Heating Flex versus Joint Planner

Heating Flex mag geen zelfstandig concurrerende planner worden.

De Heating Flex-laag vertaalt Honeywell + PV opportunity naar begrensde kandidaten, bijvoorbeeld:

```text
futureTarget:       20.0 C
requiredAt:         17:00
earliestStart:      14:00
estimatedEnergy:    ...
maxTarget:          20.0 C
```

De kandidaat reserveert nog niet zelfstandig PV. De **Joint Planner** bepaalt de uiteindelijke kwartierallocatie samen met EV en later eventueel WW. Zo kunnen twee deelplanners niet onafhankelijk dezelfde PV claimen.

Historische Honeywell-, Quatt- en buitentemperatuurdata mogen later een thermal/heating flex model voeden voor betere schatting van response time, energiebehoefte en thermische retentie. Dit is modelverbetering en geen nieuwe comfort-authority.

## 5. Joint Planner

Planner V2 heeft één gezamenlijke rolling horizon:

- 24 uur;
- 96 kwartieren van 15 minuten;
- één allocatie van beschikbare flex over EV, Heating en later eventueel elektrische WW.

Primaire doelstelling bij het huidige vaste contract is het benutten van beschikbare/verwachte eigen PV binnen harde requirements en safetygrenzen.

De planner moet minimaal rekening houden met:

- EV PV-opportunity;
- EV deadline reserve;
- Heating preheat candidates;
- later WW flex wanneer `wwMode = BOILER`.

Er komt geen afzonderlijke productie-quarter-hour-shadow-planner naast de joint planner.

### Gezamenlijke PV-allocatie: EV, Heating en WW

De **Joint Planner is de enige laag die flex-loads definitief aan kwartieren/PV-opportunity toewijst**. Dit geldt niet alleen voor EV en WW, maar nadrukkelijk ook voor het naar voren halen van kamerverwarming.

Heating Flex mag op basis van Honeywell-requirements en PV Forecast geschikte preheat-kandidaten en toegestane tijdvensters afleiden, maar reserveert zelf geen PV en beslist niet zelfstandig over het uitvoeringskwartier. De Joint Planner weegt die kandidaten af tegen EV-opportunity, de harde EV-deadline en — zodra `wwMode = BOILER` — WW-flex.

Daarmee geldt:

- EV, Heating en WW mogen nooit onafhankelijk dezelfde verwachte PV-export claimen;
- Honeywell blijft bepalen **welke temperatuur wanneer vereist is**;
- Heating Flex bepaalt **welke eerdere opwarmmomenten toegestaan en zinvol zijn**;
- PV Forecast + confidence geven de vooruitkijkende opportunity;
- de Joint Planner bepaalt **of en in welk kwartier** preheating daadwerkelijk wordt gepland, in samenhang met de andere flex-loads;
- realtime P1 blijft de actuele energiewaarheid tijdens uitvoering.

Een verwachte PV-piek kan dus bijvoorbeeld concurreren tussen EV-laden en het eerder opwarmen van een kamer. Alleen de Joint Planner mag die gezamenlijke allocatie beslissen. Wanneer elektrische WW later wordt toegevoegd, wordt WW de derde flex-load binnen exact dezelfde allocatie.

Het WW-schouderprincipe hieronder is een specifieke allocatiestrategie **binnen deze bredere gezamenlijke optimalisatie** en vormt geen afzonderlijke EV/WW-planner.

### WW fase 2: PV-schouders bewaren

Wanneer `wwMode = BOILER` wordt elektrische warmwaterproductie een flex-load binnen dezelfde Joint Planner. Daarbij blijft het eerder geïmplementeerde allocatieprincipe expliciet behouden:

> **De boiler benut bij voorkeur de schouders van de PV-exportcurve, zodat de EV de hogere PV-piek kan benutten.**

Dit betekent dat WW en EV niet onafhankelijk dezelfde hoogste PV-kwartieren mogen claimen. De Joint Planner verdeelt de beschikbare PV gezamenlijk:

- WW wordt waar comfort/deadline en thermische opslag dit toelaten naar geschikte PV-schouders verschoven;
- EV krijgt bij voorkeur ruimte rond de hogere PV-piek, vanwege de fijnere vermogensregeling en directe mogelijkheid om export te absorberen;
- opportunistisch EV-laden verlaagt de resterende EV-deadlinebehoefte;
- de harde EV-deadline blijft altijd boven deze opportunity-optimalisatie staan;
- de WW comfort/deadline-requirement blijft eveneens hard en mag niet door het schouderprincipe worden geschonden.

Het schouderprincipe is dus een **allocatievoorkeur binnen geldige requirements**, geen afzonderlijke WW-planner en geen absolute regel die comfort of EV-deadline mag breken.

## 6. P1 is realtime authority; geen globale inputFreshness-gate

Planner V2 kent **geen globale `inputFreshness.status == PASS` gate**.

Reden: een oude of ontbrekende secundaire/forecastbron mag niet het gehele EMS blokkeren. In het bijzonder mogen stale inverter-, weather-, Quatt- of forecastgegevens geen verse P1-werkelijkheid ongeldig maken.

Architectuurregel:

> **P1 is leidend voor de actuele energiebalans. Forecasts zijn advisory inputs voor vooruitplanning.**

Gevolgen:

- actuele P1-import/export is leidend voor realtime PV-regeling;
- PV Forecast bepaalt vooruitkijkende opportunity, niet de actuele waarheid;
- ontbrekende/minder bruikbare forecast kan optimalisatie verminderen, maar veroorzaakt geen globale planner-fail;
- een geldige EV-deadline mag niet falen uitsluitend omdat PV/weather minder actueel is;
- safety/validity wordt functiegericht toegepast op de gegevens die voor die specifieke actie noodzakelijk zijn.

Dit verbiedt niet dat individuele inputs schema-, presence- of semantische validatie hebben. Het verbiedt één globale freshness-schakelaar die alle plannerfuncties gezamenlijk uitschakelt.

## 7. Fail-safe is functiegericht

`failClosed` blijft een safety-principe, maar niet als synoniem voor globale input freshness.

Een functie wordt alleen geblokkeerd wanneer voor **die functie** noodzakelijke informatie ontbreekt of ongeldig is.

Voorbeelden:

- geen bruikbare PV Forecast -> geen betrouwbare vooruitkijkende PV-optimalisatie, maar een geldige EV-deadline blijft uitvoerbaar;
- ongeldige EV-deadline-state -> deadlinefunctie faalt veilig zonder daarmee automatisch Honeywell-baseline of andere onafhankelijke functies ongeldig te verklaren;
- geen bruikbare actuele P1-balans -> realtime PV-capture mag niet blind op een forecast worden uitgevoerd.

## 8. validUntil blijft

`validUntil` blijft onderdeel van het control contract.

Het betekent uitsluitend: **tot wanneer mag deze concrete planneruitkomst/control command worden uitgevoerd?**

Het is dus niet hetzelfde als input freshness. Een oud plannercommand mag niet onbeperkt geldig blijven. Het actuele command blijft bovendien begrensd door het huidige kwartierslot en de expliciete command/plan-geldigheid.

## 9. Realtime execution boundary

Pi blijft strategy/planning authority; Homey blijft executor en lokale safetylaag.

```text
Planner V2 -> /control/current -> Homey -> adapters/gates -> single physical writer -> device
                                      ^
                                      |
                                     P1
```

Homey mag binnen expliciete Pi-grenzen realtime reageren op werkelijke P1-export. Dit is vooral relevant voor EV PV-capture: een forecastmiss kan realtime worden gecorrigeerd zonder dat Homey een tweede strategische planner wordt.

Lokale hardware-safety, waaronder Easee/Equalizer-beveiliging, blijft boven software-optimalisatie staan.

## 10. History en observability staan buiten de control-loop

History V2 is geen verplichte realtime planner-input. Forecast, planneruitkomst en actual/P1 worden wel opgeslagen voor analyse, replay en modelverbetering.

Doelen zijn onder andere:

- PV forecast versus werkelijkheid;
- confidence versus werkelijke forecastfout;
- geplande versus gerealiseerde EV-energie;
- opportunistische EV-energie versus deadline-energie;
- vermeden export;
- heating-preheat-effect;
- thermische response;
- later WW-resultaten.

Historische data worden dus behouden, ook wanneer historical baseload forecast uit de productieplanner verdwijnt.

## 11. Buiten de V2-kern / beoogde retirement

De volgende bestaande concepten zijn **geen onderdeel van de Planner V2-productiekern**:

- historical baseload forecast als plannerinput;
- standalone Quatt power forecast als plannerinput;
- price forecast als productie-optimalisatie bij het actieve FIXED-contract;
- afzonderlijke quarter-hour shadow planner;
- GitHub planner/publication als control- of plannerpad;
- oude Homey planner als parallelle planner;
- oude battery planner.

Dit is een targetbesluit, **geen toestemming om deze onderdelen direct te verwijderen**. De huidige productieplanner refereert technisch nog aan meerdere van deze inputs. Retirement mag pas na dependency-audit, replacement en gecontroleerde cutover.

## 12. Niet opnieuw uitvinden

Bestaande bewezen grenzen blijven uitgangspunt:

- Pi planner authority;
- Pi-owned EV deadline lifecycle;
- `/control/current` als bounded control contract;
- Homey als executor;
- exact één fysieke writer per actuator;
- realtime P1-correctie binnen Pi-envelope;
- contract policy FIXED/ENGIE;
- Honeywell als heating baseline-authority;
- History als observability/replay, niet als tweede control plane.

## 13. Migratiestrategie

Voor implementatie wordt de huidige forecast/control-chain per component geclassificeerd als:

- **KEEP** — blijft functioneel en architectonisch;
- **REPLACE** — functionaliteit blijft nodig maar verhuist/verandert voor V2;
- **RETIRE** — niet meer nodig nadat alle productieafhankelijkheden aantoonbaar zijn verwijderd.

Minimale volgorde:

1. dependency-map huidige productiechain;
2. V2 input/output-contracten;
3. PV Forecast domain consolideren;
4. EV + Heating Flex contracts;
5. Joint Planner V2;
6. `/control/current` V2 contract en functiegerichte safety;
7. shadow/replay-validatie tegen History;
8. gecontroleerde production cutover;
9. pas daarna legacy retirement en verwijderen van repository-structure exceptions.

De bestaande productieplanner blijft onaangetast totdat deze stappen aantoonbaar zijn doorlopen.

## P1 als realtime energie-autoriteit

**P1 is de canonical realtime energy authority. Forecast PV creates opportunity; measured P1 export authorizes opportunistic consumption. Forecast availability or forecast confidence must never override contradictory realtime P1 measurements.**

Dit is een harde Planner V2-invariant. Forecasts zijn vooruitkijkend en helpen de Joint Planner om kansen, kandidaten en harde requirements over de horizon te organiseren. Voor opportunistisch energiegebruik op het actuele moment is de werkelijk door P1 gemeten energiestroom leidend.

Daaruit volgen de volgende regels:

- gemeten P1-export is de belangrijkste realtime driver voor opportunistische flex;
- een tegenvallende of onzekere PV Forecast mag actuele P1-export niet blokkeren;
- voorspelde PV zonder daadwerkelijk beschikbare export mag niet zelfstandig opportunistische netimport veroorzaken;
- harde requirements, zoals een EV-deadline, mogen wel netimport veroorzaken wanneer dat nodig is om de requirement te halen;
- P1-authority geldt voor de gezamenlijke realtime opportunity van EV, Heating en — bij `wwMode = BOILER` — WW.

Per flex-load:

- **EV:** mag binnen de Pi-envelope snel en numeriek op werkelijk P1-overschot moduleren. De bestaande bounded realtime EV-regeling blijft het uitgangspunt.
- **Heating:** P1-export is de realtime opportunity-driver, maar alleen voor vooraf geldige Heating Flex-kandidaten. Een korte exportpiek mag niet zelfstandig nieuwe warmtevraag creëren of buiten Honeywell-grenzen een setpoint wijzigen. Honeywell blijft comfort- en baseline-authority.
- **WW:** alleen bij `wwMode = BOILER` kan werkelijk P1-overschot opportunistisch boilergebruik activeren, binnen WW comfort/deadline- en technische randvoorwaarden. Bij `wwMode = CV` bestaat geen elektrische WW-flex.

De Joint Planner voorkomt vooruitkijkend dat meerdere flex-loads dezelfde verwachte PV-opportunity claimen. Tijdens uitvoering bepaalt P1 hoeveel opportunistische flexibiliteit werkelijk beschikbaar is. Forecast en confidence sturen dus planning en voorbereiding; P1 autoriseert de actuele opportunistische energie-opname.

## Heating Flex V2 — doellogica

Heating Flex V2 optimaliseert **wanneer** een reeds door Honeywell gevraagde toekomstige temperatuurverhoging wordt gerealiseerd. Honeywell blijft de comfort-authority: Heating Flex mag geen hogere comforttemperatuur verzinnen en mag een Honeywell-doel niet verlagen of vervangen.

### Thermische eenheden

Voor planning en thermische analyse worden de Honeywell-ruimtes als volgt geïnterpreteerd:

- **Leefzone:** woonkamer + eetkamer. Dit zijn afzonderlijke Honeywell-comfortzones, maar worden door Heating Flex als één thermisch gekoppelde eenheid beschouwd.
- **Keuken:** zelfstandige thermische eenheid.
- **Serre:** zelfstandige thermische eenheid.

Het samenvoegen in een thermische eenheid verandert de Honeywell-zonering of regeling niet.

### Beslisprincipe

1. Honeywell levert per ruimte het actuele en toekomstige baseline-setpoint en het tijdstip van een toekomstige UP-transition.
2. Heating Flex bepaalt of zo'n bestaande UP-transition thermisch zinvol eerder kan beginnen. Het toekomstige Honeywell-doel blijft de bovengrens.
3. PV Forecast geeft vooruit aan wanneer een PV-opportunity waarschijnlijk is en ondersteunt de planning; forecast-confidence is adviserend en geen globale gate.
4. De Joint Planner arbitreert Heating Flex samen met andere flexibele verbruikers, in het bijzonder EV, zodat dezelfde verwachte PV niet dubbel wordt geclaimd.
5. P1 blijft de realtime energie-authority. Een vooraf geldige Heating Flex-kandidaat mag opportunistisch worden geactiveerd wanneer werkelijke P1-export de opportunity bevestigt. Een korte P1-piek mag nooit zelfstandig nieuwe warmtevraag of een hoger comfortdoel creëren.
6. Heating Flex is een traag thermisch proces en wordt daarom niet als een minuut-tot-minuut vermogensregelaar behandeld. Na activering wordt een stabiele, vooraf begrensde verwarmingsactie uitgevoerd binnen Honeywell- en safetygrenzen.

De bestaande maximale advance van drie uur en stappen van 0,5 °C zijn commissioning-grenzen uit het huidige shadow-model en worden niet als bewezen thermische eigenschappen beschouwd. V2 moet deze grenzen later onderbouwen met historische Honeywell-, Quatt- en buitentemperatuurdata.

### Thermisch leermodel

Per thermische eenheid moet historische analyse uiteindelijk kunnen schatten:

- opwarmsnelheid bij verschillende buitentemperaturen;
- benodigde elektrische Quatt-energie voor een relevante temperatuurstijging;
- thermische retentie: hoeveel van een vervroegde temperatuurstijging na verloop van tijd behouden blijft;
- zinvolle maximale vervroeging van een Honeywell UP-transition.

Quatt is daarbij een energie-/responsbron voor het thermische model en **geen comfort-authority**. Honeywell blijft leidend voor gewenste ruimtetemperaturen.

### Website-doel

Heating Flex krijgt in Frontend V2 een eigen pagina voor commissioning, validatie en latere optimalisatie. Deze pagina toont minimaal:

- tijdlijnen voor Leefzone, Keuken en Serre;
- Honeywell baseline-schema en werkelijke ruimtetemperatuur;
- zichtbaar onderscheid tussen baseline en een door Heating Flex vervroegd verwarmingsdeel;
- PV Forecast, werkelijke P1 import/export en Quatt elektrisch vermogen in samenhang met de verwarmingsactie;
- per thermische eenheid de geleerde respons, zoals opwarmtijd, gebruikte energie en thermische retentie.

De Heating-pagina is observability/validation en krijgt geen zelfstandige control-authority.


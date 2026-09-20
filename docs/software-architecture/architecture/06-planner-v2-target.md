---
component: planner-v2-target
title: Planner V2 Target Architecture
version: 0.1.0
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

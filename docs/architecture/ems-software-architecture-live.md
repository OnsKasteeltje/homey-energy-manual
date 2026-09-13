# EMS Software Architecture - Live As-Is

**Datum:** 13 september 2026  
**Status:** Live-code synopsis  
**Scope:** Raspberry Pi runtime + actieve Homey flows  
**Doel:** Vastleggen van de actuele softwarearchitectuur na de wijzigingen van de afgelopen dagen.

> Deze beschrijving is gebaseerd op de actuele Pi-broncode en live Homey-flowcode, niet op oudere projectdocumentatie. Waar een component nog rollback- of shadow-functionaliteit bevat, is dat expliciet benoemd.

## 1. Architectuuroverzicht

```text
                     +----------------------+
                     |      HOMEY DEVICES   |
                     | P1 / PV / Easee      |
                     | Boiler / Quatt       |
                     | Washer / Dryer etc.  |
                     +----------+-----------+
                                |
                                v
                 +----------------------------+
                 | HOMEY CORE v0.11n          |
                 |                            |
                 | - leest fysieke devices    |
                 | - normaliseert state       |
                 | - freshness / P1 gates     |
                 | - WW dagstatus             |
                 | - Tesla deadline context   |
                 | - Quatt observe-only       |
                 |                            |
                 | -> EM2_State               |
                 | -> EM2_Public_State        |
                 +-------------+--------------+
                               |
                     direct HTTP POST
                     iedere 5 min + 8 s
                               |
                               v
              +----------------------------------+
              |             PI RUNTIME           |
              |                                  |
              | /data/energy-state-v2.json       |
              |             |                    |
              |             v                    |
              | forecasts + history + WW model   |
              |             |                    |
              |             v                    |
              |      DYNAMIC PLANNER             |
              |      15-min rolling horizon      |
              |             |                    |
              |             v                    |
              | dynamic-shadow-plan.json         |
              |             |                    |
              |             v                    |
              | HARDENED VALIDATOR               |
              | freshness / contract / plan      |
              |             |                    |
              |             v                    |
              | /control/current                 |
              +-------------+--------------------+
                            | LAN
                            v
             +----------------------------------+
             | HOMEY AUTHORITY / BRIDGE         |
             |                                  |
             | EM2_Planner_Authority            |
             |          |                       |
             |      PI or HOMEY                 |
             |          |                       |
             |          v                       |
             | EM2_Power_Intent                 |
             +------------+---------------------+
                          |
             +------------+------------+
             v                         v
       EV Power Adapter           WW control path
       W -> 0/6..16 A
             |
       Validation Gate
             |
       EV Actuator LIVE
             |
             v
           Easee
```

## 2. Homey Core is de realtime sensor- en state-laag

De actieve flow **EM v2 | 00 Core Tick | v0.11n PINNED SOURCE** vormt de realtime edge-laag. Deze flow draait periodiek en kan tevens event-driven reageren op wijzigingen in de EV-deadline-input.

De Core leest rechtstreeks onder andere:

- P1/netmeting;
- Tesla/Easee;
- boiler;
- Quatt;
- SolarEdge;
- GoodWe 4.2 kW en GoodWe 2.0 kW;
- wasmachine en droger;
- relevante Homey Logic contextvariabelen.

De Core publiceert onder meer:

```text
EM2_State
EM2_Public_State
EM2_WW_State
EM2_Control_WW
EM2_Control_EV
EM2_Planner_Input
```

De Core voert daarnaast realtime kwaliteitsbewaking uit voor P1-freshness, PV-source freshness, timing/skew tussen bronnen, balansvalidatie, flexbudgetten, Quatt-rampreserve, Tesla-connectiviteit en warmwaterstatus.

Homey is hierdoor niet alleen een hardwaregateway: het is de realtime observatie-, normalisatie- en safety-contextlaag.

## 3. Runtime data loopt direct Homey -> Pi

De actieve flow **EM v2 | 40 Data | Pi State Push v2.0 DIRECT RUNTIME** verstuurt `EM2_Public_State` rechtstreeks naar:

```text
POST http://192.168.1.42:3100/state
```

De flow controleert onder andere:

- schema-versie 2.12;
- state revision;
- alignment tussen public state en Homey state;
- HTTP-resultaat;
- Pi-ACK `ACCEPTED`;
- revision van de ACK.

Runtime telemetry gaat dus niet langer via GitHub.

```text
CODE      -> GitHub
RUNTIME   -> Pi
CONTROL   -> Pi <-> Homey
UI/DOCS   -> website / GitHub
```

## 4. Raspberry Pi is de rolling-horizon optimization engine

De actuele planner leest rechtstreeks uit Pi-runtimebestanden, waaronder:

```text
/home/jeroen/ems/data/energy-state-v2.json
pv-forecast.json
weather-forecast.json
quatt-forecast.json
base-load-forecast.json
pv-forecast-multiday.json
base-load-forecast-multiday.json
ww-input.json
planner-axis.json
```

De planner werkt in kwartieren van 15 minuten en heeft als hoofdobjectief:

```text
MAXIMIZE EXPECTED PV SELF-CONSUMPTION
```

onder harde randvoorwaarden voor comfort, Tesla-deadlines, apparaatgrenzen en inputkwaliteit.

Belangrijke eigenschappen van de actuele planner:

- WW-comfort is een harde constraint;
- WW kan PV-flanken gebruiken;
- Tesla gebruikt residual PV na WW-reservering;
- EV-opportunity wordt dynamisch per slot en window gekwalificeerd;
- forecast en live P1-context worden gecombineerd;
- de planner verricht geen fysieke device writes.

## 5. WW en Tesla worden gezamenlijk geoptimaliseerd

De planner modelleert eerst de niet-flexibele en comfortlasten en reserveert vervolgens benodigde warmwatercapaciteit. Daarna wordt de overblijvende PV-capaciteit opnieuw berekend voor Tesla.

Conceptueel:

```text
PV forecast
 - base load
 - Quatt / comfort load
 - noodzakelijke WW-reservering
 = residual PV voor EV-flex
```

Tesla-opportunity is daardoor niet meer alleen een simpele exportdrempel. De planner kiest per slot een target van 0 of 6..16 A op basis van marginale PV-capture versus importpenalty. Een opportunity-window moet minimaal twee kwartieren lang zijn.

## 6. Tesla-deadline is canonical in de Pi-planner

De actuele deadlinevolgorde is:

```text
1. plan echte PV-opportunity
2. tel opportunity-kWh voor de deadline
3. trek die energie af van remaining deadline kWh
4. plan alleen het resterende tekort
5. plan dat zo laat mogelijk binnen de haalbare slots
6. respecteer deadline_max_a
```

Bij een actieve deadline zonder geldige `deadline_max_a` van 6..16 A faalt de planner gesloten:

```text
FAIL_CLOSED_INVALID_OR_MISSING_DEADLINE_MAX_A
```

De dynamic planner is daarmee de enige canonical Tesla-deadline allocator.

## 7. Hardened planner is validator en production-readiness guard

De hardened laag controleert voor uitvoering onder andere:

```text
production contract mode = FIXED
supplier                 = ENGIE
contract id              = ENGIE_3Y_2026_2029
dynamic pricing prod     = false
automatic switching      = false
failClosed               = true
```

Ook worden kritieke inputs op freshness gecontroleerd. Verouderde input leidt tot fail-closed gedrag.

De hardened Tesla-deadlinefunctie valideert het canonical plan maar hoort geen tweede deadlineplanning te maken.

### Bekende technische schuld

In `deadline_requirement()` staat nog historische compatibiliteitscode met een lokale `max_a = 16`. De huidige validator gebruikt deze waarde niet meer om de planning te wijzigen, maar dit fragment is achterhaald omdat `deadline_max_a` inmiddels in de runtime-state beschikbaar is. Dit is een opschoonpunt.

## 8. Homey heeft een expliciete planner-authority switch

Twee producers kunnen `EM2_Power_Intent` produceren:

```text
PI Dynamic Planner Bridge
Homey P1 Power Intent
```

Beide zijn beschermd door:

```text
EM2_Planner_Authority
```

De PI-route schrijft alleen bij authority `PI`; de Homey-route alleen bij authority `HOMEY`. Hierdoor bestaat een expliciet rollbackmechanisme zonder twee gelijktijdige schrijvers.

## 9. Pi -> Homey control via /control/current

De actieve **PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD** leest:

```text
http://192.168.1.42:3100/control/current
```

De bridge valideert onder andere:

```text
schema = EMS_PI_CONTROL_COMMAND_V0.1
readyForCutover = true
plannerOwner = PI
executor = HOMEY
contract.mode = FIXED
contract.id = ENGIE_3Y_2026_2029
validUntil > now
```

Bij een fout wordt fail-closed gewerkt en wordt een niet-uitvoerbaar/0-target gepubliceerd.

## 10. Homey blijft exact-minute executor safety owner

Homey bevat bewust nog een executor-side hard deadline guard.

Voor de veilige latest-start blijft het Pi-target leidend. Vanaf de noodzakelijke starttijd mag Homey bij een actieve, verbonden Tesla de laadopdracht op het ingestelde deadline maximum zetten om het gebruikersdoel te beschermen.

Dit is geen tweede optimizer, maar een safety override:

```text
Pi    = planning owner
Homey = exact-minute executor / safety owner
```

## 11. Power Intent is de grens tussen planning en uitvoering

De canonical interface naar uitvoering is:

```text
EM2_POWER_INTENT_V0.2
```

met onder andere:

```text
targets.ev.target_W
targets.ww.target_on
targets.battery.target_W
```

De softwareketen is daardoor:

```text
PLAN
 -> POWER INTENT
 -> DEVICE ADAPTER
 -> VALIDATION GATE
 -> ACTUATOR
 -> PHYSICAL DEVICE
```

Dit is de belangrijkste abstractielaag voor toekomstige uitbreiding.

## 12. EV Power Adapter vertaalt vermogen naar uitvoerbare laadstroom

De actieve EV Power Adapter vertaalt een numerieke EV-target in watt naar een fysiek uitvoerbare 3-fasen laadstroom.

Uitgangspunt:

```text
3 x 230 V = 690 W/A
```

Beleid:

```text
START_MIN_A       = 6
RUN_MIN_A         = 6
OPPORTUNITY_MAX_A = 16
```

Deadline-targets gebruiken daarnaast hun eigen deadline-cap.

De adapter gebruikt `floor()` en verhoogt daardoor nooit zelfstandig het upstream gevraagde vermogen. Onder het minimale uitvoerbare laadvermogen wordt 0 A gevraagd.

De adapter schrijft zelf niet naar het apparaat.

## 13. Validation gate beschermt de fysieke EV-write

Voor een fysieke laadstroomwijziging moeten onder andere kloppen:

- schema;
- revision alignment tussen intent, adapter, state en gate;
- freshness;
- adapter-validity;
- mapping-contract;
- toegestane stroom 0 of 6..16 A;
- final gate status `PASS`.

Bij inconsistentie wordt fail-closed naar 0 A gewerkt.

## 14. EV Actuator is de fysieke writer

De actieve actuator is:

```text
EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION
```

Deze laag kan fysiek:

- een Easee-laadsessie starten;
- een gepauzeerde sessie hervatten;
- `target_charger_current` schrijven;
- bij fouten fail-closed naar 0 A gaan.

De feitelijke ownership-keten is dus:

```text
Dynamic Pi Planner
 -> Power Intent
 -> EV Power Adapter
 -> Validation Gate
 -> EV Actuator
 -> Easee
```

## 15. Quatt is observe-only comfort baseload

De actuele Core markeert Quatt expliciet als:

```text
role         = COMFORT_BASELOAD
controlMode  = OBSERVE_ONLY
controllable = false
```

Quatt wordt gemeten, gemodelleerd en voorzien van ramp-reserve, maar wordt niet door de EMS-planner aangestuurd.

## 16. Warm water heeft nog meer lokale Homey-policy dan Tesla

Voor warm water produceert de Homey Core nog zelfstandig:

```text
EM2_WW_State
EM2_Control_WW
```

met onder andere:

- `goalReachedToday`;
- bevestigde heating-minuten;
- fallback-minuten;
- catch-up;
- 19:00 deadline;
- startvenster;
- run-locks;
- thermostat verification;
- post-goal opportunities.

De Pi levert de strategische/kwartierplanning, terwijl Homey nog veel realtime WW-policy en safety bevat.

De huidige verdeling is daarom:

```text
Pi          = strategische WW-planning
Homey Core  = realtime WW state machine + safety policy
Actuator    = fysieke boiler-write
```

Dit werkt, maar is architectonisch minder strak geconsolideerd dan de Tesla-keten en is een logisch toekomstig vereenvoudigingspunt.

## 17. Canonical softwarearchitectuur in een regel

**Homey is de realtime edge/state/safety/execution controller; de Raspberry Pi is de rolling-horizon optimization engine; een revision-guarded Power Intent contract vormt de grens tussen planning en fysieke uitvoering.**

Volledige gesloten regelkring:

```text
SENSORS
   -> HOMEY CORE STATE
   -> DIRECT PI STATE API
   -> FORECAST + HISTORY
   -> DYNAMIC PI OPTIMIZER
   -> HARDENED VALIDATOR
   -> CONTROL API
   -> HOMEY AUTHORITY GATE
   -> POWER INTENT
   -> DEVICE ADAPTERS
   -> VALIDATION GATES
   -> ACTUATORS
   -> PHYSICAL DEVICES
   -> SENSORS
```

## 18. Architectuurbeoordeling

De belangrijkste structurele verbeteringen van de afgelopen dagen zijn:

1. GitHub is uit de realtime control loop gehaald.
2. Pi en Homey communiceren via expliciete runtime- en control-contracten.
3. Tesla heeft een canonical planner op de Pi en Homey alleen als executor/safety-owner.
4. Revision-, freshness- en fail-closed guards zitten op meerdere controlgrenzen.
5. Power Intent vormt een duidelijke hardware-onafhankelijke interface.
6. GitHub is opnieuw source of truth voor productiesoftware; de Pi-runtime is de deployed copy.

De belangrijkste resterende architectuurpunten zijn:

- verdere consolidatie van WW-policy richting een eenduidiger ownershipmodel;
- verwijderen van historische/stale compatibiliteitscode in de hardened planner;
- blijvend bewaken dat runtimecode en GitHub canonical source synchroon blijven.

## 19. Source-of-truth beleid

De gewenste en huidige richting is:

```text
GitHub = canonical source voor software en documentatie
Pi     = runtime/deployment target
Homey  = live edge, integratie, safety en actuatorlaag
```

Wijzigingen aan productielogica horen daarom eerst of direct daarna gecontroleerd terug te landen in GitHub, zodat live runtime en repository niet opnieuw divergeren.

---

**Documentstatus:** Live As-Is architectuur, 13 september 2026.  
**Validatiebasis:** actuele Homey flows + actuele Pi dynamic planner / hardened planner broncode.

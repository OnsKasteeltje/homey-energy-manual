# EMS Software Architecture - Live As-Is

**Datum:** 13 september 2026  
**Status:** Live-code synopsis  
**Scope:** Raspberry Pi runtime + actieve Homey flows + actuele GitHub-architectuur  
**Doel:** Vastleggen van de actuele softwarearchitectuur na cross-check van live Homey, Pi-controlarchitectuur en GitHub `main`.

> Deze beschrijving is gebaseerd op de actuele implementatie en canonical current-state documentatie. Waar nog technische schuld of rollback-functionaliteit bestaat, is dat expliciet benoemd.

## 1. Architectuuroverzicht

```text
HOMEY DEVICES / P1 / PV / EASEE / BOILER / QUATT
                         ↓
                  HOMEY CORE v0.11n
                         ↓
                canonical Homey state
                         ↓
                 direct state push
                         ↓
                   PI RUNTIME
        forecasts + history + WW model
                         ↓
          DYNAMIC PLANNER v0.3
       rolling horizon / 15-min slots
                         ↓
              HARDENED VALIDATOR
                         ↓
               /control/current
                         ↓ LAN
              HOMEY PI BRIDGE v1.2.6
                         ↓
                 EM2_Power_Intent
                  ↙             ↘
          EV adapter/gate     WW adapter/gate
                  ↓             ↓
          EV actuator LIVE   WW actuator v0.9 LIVE
                  ↓             ↓
                Easee         Boiler
```

Canonical verantwoordelijkheidsverdeling:

```text
Pi     = rolling-horizon planning / optimization
Homey  = realtime state / safety / execution
GitHub = canonical source voor software + architectuurdocumentatie
```

## 2. Homey Core is realtime state- en safety-contextlaag

De actieve flow `EM v2 | 00 Core Tick | v0.11n PINNED SOURCE` leest en normaliseert onder andere:

- P1/netmeting;
- Tesla/Easee;
- boiler;
- Quatt;
- SolarEdge;
- GoodWe 4.2 kW en 2.0 kW;
- relevante Homey Logic context.

De Core publiceert onder meer:

```text
EM2_State
EM2_Public_State
EM2_WW_State
EM2_Control_WW
EM2_Control_EV
EM2_Planner_Input
```

Homey blijft daarmee de realtime observatie-, normalisatie- en lokale safetylaag.

## 3. Runtime data loopt rechtstreeks Homey → Pi

De actieve `Pi State Push v2.0 DIRECT RUNTIME` verstuurt actuele state rechtstreeks naar de Pi-runtime. GitHub zit niet in de realtime control loop.

```text
CODE / DOCS  -> GitHub
RUNTIME      -> Pi
CONTROL      -> Pi <-> Homey
UI/PUBLISH   -> website / GitHub artifacts
```

## 4. Raspberry Pi is de rolling-horizon optimization engine

De Pi combineert runtime-state, forecasts en historie en optimaliseert flexibele verbruikers in kwartieren.

Hoofdobjectief:

```text
MAXIMIZE EXPECTED PV SELF-CONSUMPTION
```

onder harde randvoorwaarden voor:

- warmwatercomfort;
- Tesla-deadlines;
- fysieke apparaatgrenzen;
- freshness en inputkwaliteit;
- fixed-contract governance.

De planner verricht geen fysieke device writes.

## 5. WW en Tesla worden gezamenlijk geoptimaliseerd

Conceptueel:

```text
PV forecast
 - base load
 - Quatt / comfort load
 - noodzakelijke WW-reservering
 = residual PV voor EV-flex
```

WW-comfort wordt eerst veiliggesteld; Tesla gebruikt vervolgens residual PV.

De actuele EV opportunity-policy is **15-minuten-slotgebaseerd**:

- start vereist minimaal **één positief uitvoerbaar 15-minuten-slot**;
- elk volgend kwartier wordt opnieuw onafhankelijk beoordeeld;
- de planner vereist dus niet langer een minimumwindow van twee kwartieren;
- realtime anti-flap/sessionbescherming blijft een executorverantwoordelijkheid en staat los van de plannerwindow.

## 6. Tesla-deadline is canonical in de Pi-planner

De planner:

1. plant echte PV-opportunity;
2. telt opportunity-kWh vóór de deadline;
3. trekt die af van remaining deadline kWh;
4. plant alleen het resterende tekort;
5. houdt rekening met `latest_start_at`;
6. respecteert `deadline_max_a`.

Bij een actieve deadline zonder geldige `deadline_max_a` van 6..16 A hoort de planner fail-closed te werken.

De Pi is de canonical deadline allocator; Homey behoudt uitsluitend een executor-side hard deadline guard als laatste safetylaag.

## 7. Hardened validator en contractgovernance

Voor productie gelden:

```text
production contract mode = FIXED
supplier                 = ENGIE
contract id              = ENGIE_3Y_2026_2029
dynamic pricing prod     = false
automatic switching      = false
failClosed               = true
```

Dynamische prijsdata mag onder deze productieconfiguratie alleen voor shadow, analyse of replay worden gebruikt.

De hardened laag controleert daarnaast freshness, planvaliditeit en current-slot uitvoerbaarheid voordat `/control/current` een READY-command mag leveren.

### Bekende technische schuld

In `deadline_requirement()` staat nog historische compatibiliteitscode met lokale `max_a = 16`. Deze code is niet de huidige canonical deadline allocator; `deadline_max_a` uit runtime-state is leidend. Het fragment blijft een expliciet runtime-cleanupitem.

## 8. Homey heeft één expliciete planner-authority switch

Twee producers kunnen `EM2_Power_Intent` leveren:

```text
PI Dynamic Planner Bridge
Homey P1 Power Intent rollback producer
```

Beide worden exclusief gemaakt door:

```text
EM2_Planner_Authority
```

- `PI` → alleen PI bridge produceert canonical intent.
- `HOMEY` → PI bridge blijft inert en Homey rollbackproducer mag intent leveren.

Er mag nooit gelijktijdig dubbele plannerauthority bestaan.

## 9. Pi → Homey control via /control/current

De actieve bridge `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]` leest:

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

Bij fouten wordt fail-closed gewerkt.

## 10. Homey blijft exact-minute executor / safety owner

Homey bevat bewust een hard deadline guard:

- vóór de earliest safe latest-start blijft het Pi-target leidend;
- vanaf de noodzakelijke starttijd mag Homey voor een actieve, aangesloten Tesla het ingestelde deadline maximum afdwingen.

Dit is een safety override en geen tweede optimizer.

## 11. Power Intent vormt de architectuurgrens

Canonical interface:

```text
EM2_POWER_INTENT_V0.2
```

met onder andere:

```text
targets.ev.target_W
targets.ww.target_on
targets.battery.target_W
```

Algemene keten:

```text
PLAN
 -> POWER INTENT
 -> DEVICE ADAPTER
 -> VALIDATION GATE
 -> ACTUATOR
 -> PHYSICAL DEVICE
```

## 12. Actieve EV execution chain

Actuele Homey-keten:

```text
EV Power Adapter v0.1.5
 -> EV Power Adapter Gate v0.2.6
 -> EV Power Actuator v0.2.7 LIVE
 -> Easee
```

Mapping:

```text
3 x 230 V = 690 W/A
START_MIN_A = 6
RUN_MIN_A   = 6
```

De adapter gebruikt `floor()` en verhoogt het upstream vermogensbudget niet zelfstandig. De gate controleert schema, revisions, freshness en mapping. Alleen de actuator schrijft fysiek naar Easee.

## 13. Actieve WW execution chain

Actuele keten:

```text
Power Intent WW target_on
 -> WW Power Adapter
 -> WW Power Adapter Gate v0.2
 -> Warm Water Actuator v0.9 TARGETED-READ LIVE
 -> Boiler
```

De actuator controleert onder andere:

- source mode;
- kill switch;
- schema/revision alignment;
- gate PASS;
- freshness;
- actuele `onoff` state;
- idempotent NOOP wanneer target al bereikt is.

De WW-keten is hiermee fysiek geïntegreerd, maar Homey bevat nog meer realtime WW state/safety policy dan bij Tesla.

## 14. Quatt is observe-only comfort baseload

Quatt blijft:

```text
role         = COMFORT_BASELOAD
controlMode  = OBSERVE_ONLY
controllable = false
```

Quatt wordt gemeten en gemodelleerd, maar niet door de EMS-planner aangestuurd.

## 15. End-to-end validatie

De gecontroleerde cutover van 2026-09-12 heeft beide primaire flexloads end-to-end gevalideerd.

Tesla:

- Pi → Power Intent → EV gate → actuator → Easee ON/OFF PASS;
- oorspronkelijke cutoverproef op 7 A;
- afzonderlijk START6 vanaf paused bewezen op circa 4.235 kW.

Warm water:

- Pi WW target ON → WW gate → actuator → boiler ON;
- restore target → boiler OFF;
- fysieke keten PASS.

## 16. Source-of-truth beleid

```text
GitHub = canonical software + documentatie
Pi     = runtime/deployment target
Homey  = live edge, integratie, safety en actuatorlaag
```

Runtimecode en GitHub moeten aantoonbaar synchroon blijven. Architectuurgevoelige wijzigingen horen in dezelfde release-range in `CURRENT-EMS-STATE.md` en relevante component-/flowdocumentatie te worden verwerkt.

## 17. Resterende architectuurpunten

- verdere vereenvoudiging van WW ownership;
- verwijderen van historische `deadline_requirement()` compatibiliteitscode;
- blijvend bewaken van GitHub ↔ Pi runtime drift;
- batterij-integratie pas na commissioning, met Victron/DESS als primaire realtime batterijoptimizer.

---

**Documentstatus:** Live As-Is architectuur, opnieuw gecrosscheckt op 13 september 2026.  
**Canonical current-state:** `docs/architecture/CURRENT-EMS-STATE.md`.

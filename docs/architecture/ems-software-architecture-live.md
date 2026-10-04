# EMS Software Architecture - Live As-Is

**Datum:** 4 oktober 2026
**Status:** Live-code synopsis  
**Scope:** Raspberry Pi runtime + actieve Homey flows + actuele GitHub-architectuur  
**Doel:** Vastleggen van de actuele softwarearchitectuur na cross-check van live Homey, Pi-controlarchitectuur en GitHub `main`.

> Deze beschrijving is gebaseerd op de actuele implementatie en canonical current-state documentatie. Waar nog technische schuld of rollback-functionaliteit bestaat, is dat expliciet benoemd.

## 1. Architectuuroverzicht

```text
HOMEY DEVICES / P1 / PV / EASEE / BOILER / QUATT
                         ↓
                  HOMEY CORE v0.11p
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
              HOMEY PI BRIDGE v1.5.3
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

De actieve flow `EM v2 | 00 Core Tick | v0.11p PINNED SOURCE` leest en normaliseert onder andere:

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

De actieve `EM v2 | 05 Transport | Homey→Pi State Push v0.1` verstuurt `EM2_Public_State` rechtstreeks naar de Pi-runtime. De transportlaag vereist een aanwezige schema-identificatie en geldige publisher-family, maar bezit geen exacte schema-versiepolicy. De Pi-ingress is de semantische contractgrens: schema 2.13 is de actuele Homey Core-versie en de expliciet gereviewde compatibele ingest-set is `{2.12, 2.13}`; onbekende schema's worden fail-closed geweigerd. GitHub zit niet in de realtime control loop.

Schema 2.13 voegt cumulatieve energietellers toe voor P1 import/export en SolarEdge/GoodWe-productie. Deze counters worden via dezelfde canonical state push naar de Pi gebracht en vormen de betrouwbare bron voor verdere Energiehistorie V2-opbouw; de transportlaag interpreteert deze velden niet.

```text
CODE / DOCS  -> GitHub
RUNTIME      -> Pi
CONTROL      -> Pi <-> Homey
UI/PUBLISH   -> website / GitHub artifacts
```

## 4. Raspberry Pi is de rolling-horizon optimization engine

De Pi combineert runtime-state, forecasts en historie en optimaliseert flexibele verbruikers in kwartieren.

De canonical operationele historie staat in `/home/jeroen/ems/data/ems-history.sqlite`. Geaccepteerde Homey Core pushes schrijven de raw `measurements`; automatische Homey Insights/day-history polling is geen production transport. Afgeleide historie wordt uitsluitend lokaal op de Pi opgebouwd: `services/pi/history/build_15m_history.py` schrijft `measurements_15m`, `services/pi/history/build_house_energy_history.py` schrijft `house_energy_intervals` uit de vijf cumulatieve P1/PV-counters en `services/pi/history/build_daily_energy_history.py` schrijft `daily_energy_history`. `ems-history-15m.service` voert de 15-minuten- en huishoudhistoriebuilder samen uit op de bestaande kwartiercadans; de daily builder behoudt zijn eigen timer. Deze afgeleide builders zijn failure-isolated van realtime state ingest en control. Frontend V2 leest huishoudhistorie uitsluitend via de read-only Web Data API (`EMS_WEB_HISTORY_V1`), niet rechtstreeks uit SQLite of GitHub.

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

De actieve bridge `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.3 PHASE-AUTHORITY [READY]` leest:

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

### 11.1 Heating control-boundary — V0.5 SHADOW

Heating heeft nog geen LIVE Power Intent target of Honeywell-writer. De eerste
control-boundary is daarom lokaal en shadow-only:

```text
V0.3 safety -> Flex Priority / V0.4 -> V0.5 Control Gate SHADOW
                                      -X-> no Homey / no Honeywell write
```

V0.5 staat onder `services/pi/control/heating/`, is geen tweede planner en
hercontroleert freshness/order, upstream safety, Honeywell-UP, CV safety,
planner grant, target ceiling en <=0.5 C progression. Rollback is alleen
`WOULD_RESET_TO_SCHEDULE` na eigen gesimuleerde shadow ownership.
`controlWrites=false`, `physicalWriteAllowed=false` en per-command
`physicalWrite=false` zijn hard. LIVE vereist later Pi->Homey transport,
Homey adapter/gate, exact één Honeywell writer en acknowledgement/readback.
V0.5 moet bij cutover worden gepromoveerd of retired/archived.

De commissioning-observability is eveneens lokaal: `ems-flex-context-history`
archiveert V0.3, Flex Priority, V0.4 en de V0.5 control-gate semantiek in
`planner-history.sqlite/flex_context_snapshots`. Het bestaande V0.1
flex-context schema blijft behouden; `controlGate` is een additief veld zodat
historische snapshots leesbaar blijven. `ems-health` bewaakt voor dezelfde
Heating-keten zowel artefact-freshness als timer/service-functionaliteit. Deze
evidence-route is read-only en kan nooit upstream planner-, gate- of
actuatorautoriteit krijgen.

## 12. Actieve EV execution chain

Actuele Homey-keten:

```text
EV Power Adapter v0.2.0 PHASE-AWARE
 -> EV Gate v0.3.0 PHASE-AWARE
 -> EV Power writer v0.4.5 AUTH-ALERT LIVE
 -> Easee
```

Mapping:

```text
1P = 230 W/A, 6..16 A
3P = 690 W/A, 6..16 A
OFF→1P = 1500 W residual export
1P stop = 1100 W rolling 2-minute reconstructed signal
OFF/1P→3P = 4400 W
3P leave = 3600 W
minimum phase dwell = 120 s
deadline = forced 3P within Pi request maxA
```

De bridge owns de bounded realtime phase-selector binnen de Pi-envelope. De adapter vertaalt het authoritative phase contract exact; de Gate valideert schema, control revisions, freshness en de 230/690 W/A mapping. Alleen de actuator schrijft fysiek naar Easee. Voor 1P↔3P gebruikt de actuator een bounded pause/phase/deadtime/resume-transactie. De aparte Easee Cloud-authenticatie voor phase control is fail-closed. Writer v0.4.5 onderscheidt refresh-, phase-command- en retry-authfouten en stuurt bij een terminale authfout één gededupliceerde Owner-push, met Timeline fallback; melding heeft geen control impact.

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

## 14. Quooker flex integration — LIVE

Quooker is voorbereid als eenvoudige flexload zonder thermisch model. De Pi bezit uitsluitend het lokale tijdvenster:

- maandag t/m vrijdag: `OPPORTUNITY` vóór 17:00, `FORCED_ON` van 17:00–18:00, daarna `OFF`;
- zaterdag/zondag: `OPPORTUNITY` vóór 13:00, `FORCED_ON` van 13:00–14:00, daarna `OFF`.

Het gemodelleerde Quooker-vermogen is 1580 W. Binnen `OPPORTUNITY` gebruikt Homey de bestaande `EM2_P1_Rolling` 120-secondenmeting als realtime executor-safety: start bij gemiddeld minstens 1250 W export (`avgGridW <= -1250`) en blijf aan totdat gemiddeld minstens 600 W import ontstaat (`avgGridW >= +600`).

De keten is momenteel:

```text
Pi Dynamic Planner
 -> /control/current targets.quooker
 -> Homey PI bridge
 -> EM2_Power_Intent.targets.quooker
 -> EM v2 | 60 Adapter | Quooker Power v0.1 SHADOW
 -> EM2_Control_Quooker
 -> EM v2 | 60 Actuator | Quooker v0.2 LIVE
 -> Cooker physical onoff
```

De adapter blijft translation-only en verricht geen fysieke writes. Sinds 2 oktober 2026 is `EM v2 | 60 Actuator | Quooker v0.2 LIVE` de enige automatische fysieke writer voor `Cooker`. Hij gebruikt het gevalideerde `EM2_Control_Quooker`, schrijft idempotent en failt closed naar OFF bij ongeldig of stale control. De drie legacy Waterkoker-tijdflows zijn in dezelfde cutover disabled en mogen niet gelijktijdig met de LIVE-actuator worden geactiveerd.

De aparte Homey→Pi observability-route blijft control-neutral, maar transporteert sinds 4 oktober 2026 het actuatorcontract versiegetrouw. Voor v0.2 LIVE worden `mode=LIVE`, `actualOnBefore`, `actualOnAfter`, top-level `physicalWritePerformed` en `writeError` als evidence behouden. De AI mag alleen `physicalWritePerformed=true` als direct bewijs van een fysieke actuator-write gebruiken; een idempotente LIVE-run met `false` is geen fout en detector-HEATING is afzonderlijke elektrische observatie.

Canonical Homey actuator-device:

`Cooker` — device ID `42992d14-c4e4-43fc-aaf0-29a73a8e2eb9`, capability `onoff`.

## 15. Quatt is observe-only comfort baseload

Quatt blijft:

```text
role         = COMFORT_BASELOAD
controlMode  = OBSERVE_ONLY
controllable = false
```

Quatt wordt gemeten en gemodelleerd, maar niet door de EMS-planner aangestuurd.

## 16. End-to-end validatie

De gecontroleerde cutover van 2026-09-12 heeft beide primaire flexloads end-to-end gevalideerd.

Tesla:

- Pi → Power Intent → EV gate → actuator → Easee ON/OFF PASS;
- oorspronkelijke cutoverproef op 7 A;
- afzonderlijk START6 vanaf paused bewezen op circa 4.235 kW.

Warm water:

- Pi WW target ON → WW gate → actuator → boiler ON;
- restore target → boiler OFF;
- fysieke keten PASS.

## 17. Source-of-truth beleid

```text
GitHub = canonical software + documentatie
Pi     = runtime/deployment target
Homey  = live edge, integratie, safety en actuatorlaag
```

Runtimecode en GitHub moeten aantoonbaar synchroon blijven. Architectuurgevoelige wijzigingen horen in dezelfde release-range in `CURRENT-EMS-STATE.md` en relevante component-/flowdocumentatie te worden verwerkt.

## 18. Resterende architectuurpunten

- verdere vereenvoudiging van WW ownership;
- verwijderen van historische `deadline_requirement()` compatibiliteitscode;
- blijvend bewaken van GitHub ↔ Pi runtime drift;
- batterij-integratie pas na commissioning, met Victron/DESS als primaire realtime batterijoptimizer.

---

**Documentstatus:** Live As-Is architectuur, opnieuw gecrosscheckt op 19 september 2026.  
**Canonical current-state:** `docs/architecture/CURRENT-EMS-STATE.md`.


## 18. Runtime publication separation target

GitHub `main` remains the canonical source for software, configuration, schemas, tests and architecture/documentation. Automatic publication of operational telemetry, planner snapshots, status or history into `docs/data/*.json` on `main` is transitional technical debt and is not the target architecture.

The target publication boundary is:

```text
Homey -> Pi runtime -> planning/control -> Homey
                  |
                  +-> dedicated read-only web data interface -> website

GitHub main -> software/configuration/schemas/tests/documentation
```

The website remains presentation plus explicit command input only. Current state, planner output and history must ultimately be consumed from the Pi operational-data boundary without a Git commit or Pages rebuild. Historical web queries derive from canonical Pi history rather than Git history.

User commands use a separate authenticated command interface and must not turn GitHub into a command bus.

Migration is artifact-by-artifact and fail-safe: inventory -> equivalent read-only resource -> parallel comparison -> consumer cutover -> validation -> only then stop that artifact's `main` mutation. No runtime publisher may be disabled merely to quiet `main`; all consumers and rollback requirements must first be proven.

Canonical migration decision and publisher/consumer matrix: `docs/architecture/runtime-publication-separation.md`.

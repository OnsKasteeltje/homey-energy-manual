# Energy Core v2 — doelarchitectuur

## Status

**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.7`  
**Contextlaag:** `EM v2 | 30 Context | Price + PV v0.3`  
**Prijsbron:** PBTH/DAP15 `NL_Netherlands` via `EM2_Price_Context`  
**Control mode:** `SHADOW`  
**Fysieke Quatt-writes:** geen (`OBSERVE_ONLY`)  
**Publicatieschema:** `2.5`

Energy Core v2 gebruikt één centrale fysieke snapshot per vijf minuten. State, Decision, Shadow, warmwater-state, warmwater-Control en publicatie worden uit dezelfde sample/revision berekend. Quatt is vanaf v0.9.7 een first-class energieverbruiker én budget-input, zonder een extra periodieke device-read.

## Harde architectuurregels

1. Per Core Tick maximaal één `getDevices()` en één `getVariables()`.
2. Downstream-berekeningen gebruiken dezelfde in-memory snapshot.
3. P1 is leidend voor de netto energiebalans; apparaatmetingen verklaren en classificeren de belasting.
4. Quatt is voorlopig een comfortload en **geen flexload**: meten en budgetteren mag, fysieke aansturing niet.
5. Websitebezoek veroorzaakt nul Homey-calls; de site leest gepubliceerde snapshots.
6. State, Decision, Shadow en Control-intent horen bij dezelfde State-revision.
7. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.
8. Een v2-Control-adapter krijgt pas fysieke writes na expliciete shadowvalidatie.
9. Ontbrekende prijswaarden worden nooit als `0` geïnterpreteerd; onbekend blijft `null` en leidt tot een quality/fallback-pad.

## Actuele keten

```text
PBTH/DAP15 NL_Netherlands
        │ iedere 15 min via bestaande Context-scheduler
        │ null-safe normalisatie, geen tweede scheduler
        ▼
EM v2 | 30 Context | Price + PV v0.3
        └── EM2_Price_Context · schema EM2_PRICE_CONTEXT_V0.3
            PURE SHADOW / context-only / geen actuatorwrites

P1 + PV + Easee + boiler + Quatt + overige devices + Homey Logic
        │ iedere 5 min
        │ 1 × getDevices() + 1 × getVariables()
        ▼
EM v2 | 00 Core Tick | v0.9.7
        ├── State → EM2_State · revision N
        ├── Energy budget → in dezelfde State
        ├── Decision → EM2_Decision · sourceRevision N
        ├── Shadow → EM2_Shadow · sourceRevision N
        ├── Warm Water State → EM2_WW_State · sourceRevision N
        ├── Warm Water Control → EM2_Control_WW · sourceRevision N
        │                         GEEN fysieke v2-write
        └── Publish → energy-state-v2.json · schema 2.5
```

## PBTH PriceContext v0.3

Vanaf 19 augustus 2026 is PBTH/DAP15 `NL_Netherlands` de genormaliseerde prijsbron voor de nieuwe v2-prijscontext. De adapter draait binnen de bestaande 15-minuten Context-flow; er is dus **geen extra scheduler** toegevoegd.

`EM2_Price_Context` bevat onder andere:

- actuele import- en exportprijs;
- kwartierprijzen `m15`, `m30` en `m45`;
- beschikbare intraday/next-day horizonwaarden;
- `quality` en `horizon_status`;
- expliciete guards voor bronbeschikbaarheid, null-safety en write-safety.

De normalisatie is bewust strikt: `null`, `undefined` en lege PBTH-velden blijven `null` en worden nooit numeriek `0`. Velden waarvoor nog geen betrouwbare volledige tijdreeks beschikbaar is — zoals afgeleide nachtminimum- of `best_before_10`-waarden — worden niet verzonnen.

De adapter is momenteel **PURE SHADOW/context-only**:

```text
mode               = PURE_SHADOW
null_safe          = true
no_actuator_writes = true
control_dependency = false
```

Dat betekent dat PBTH v0.3 al als gevalideerde contextbron beschikbaar is, maar op dit documentatiemoment nog **niet** als fysieke stuurafhankelijkheid voor boiler, Tesla of Quatt geldt. De WW Planner mag pas na afzonderlijke shadowkoppeling en validatie van freshness, horizon, fallback en revision-alignment op deze context gaan beslissen. Fysieke actuatorwrites blijven daarbij buiten scope.

## Quatt als first-class energieverbruiker

De primaire live bron is **Quatt CIC `measure_power`**. Die waarde wordt uit dezelfde `getDevices()`-snapshot gelezen die Core Tick toch al gebruikt. Er is dus geen tweede Quatt-poll, geen aparte periodieke observer en geen hogere Homey-load.

Daarnaast worden uit dezelfde snapshot diagnostische verwarmingswaarden gepubliceerd:

- elektrisch Quatt-vermogen;
- thermisch vermogen;
- COP per warmtepomp waar beschikbaar;
- working mode;
- thermostaat heating-status;
- CV-request en, waar betrouwbaar beschikbaar, vlamstatus.

Thermisch vermogen en COP zijn diagnostiek en worden **niet** bij de elektrische energiebalans opgeteld.

Quatt wordt semantisch gepubliceerd als:

```text
role         = COMFORT_BASELOAD
control_mode = OBSERVE_ONLY
controllable = false
```

Fysieke Quatt-acties — bijvoorbeeld prijsbegrenzing, geluidsniveau of andere setpoints — vallen buiten scope totdat daarvoor apart een veilige Control-policy is ontworpen en gevalideerd.

## Waarom Quatt niet dubbel van export wordt afgetrokken

P1 meet de netto woningbalans en bevat het actuele Quatt-verbruik al. Wanneer Quatt bijvoorbeeld 1.500 W trekt, is die 1.500 W dus al verwerkt in de gemeten import/export.

Daarom is dit **fout**:

```text
flex = P1-export - huidig Quatt-vermogen
```

Dat zou Quatt dubbel tellen.

v0.9.7 gebruikt in plaats daarvan een **Quatt-rampreserve**: alleen extra marge voor mogelijke modulatie/ramp-up wordt van de reeds gemeten export afgetrokken.

## Gedeeld vermogensbudget

De centrale State publiceert vanaf schema 2.5 `energy_budget`:

```text
house_load_w
known_flexible_load_w
comfort_load_w
other_house_load_w
grid_safety_reserve_w
quatt_ramp_reserve_w
flex_export_budget_w
discretionary_import_budget_w
battery_support_w
battery_integrated
```

Huidige policy:

| Component | Waarde / regel |
|---|---:|
| Grid safety reserve | 200 W |
| Quatt idle reserve | 100 W |
| Quatt actief vanaf | 250 W |
| Quatt actieve rampreserve | max(350 W, 25% van Quatt), maximaal 750 W |
| Verwacht boilervermogen | 1.900 W |
| Tesla PV-opportunitydrempel | 800 W flex-exportbudget |
| PV-forecast minimum | 500 W flex-exportbudget |
| Max. discretionaire import | 4.000 W |
| Batterijsteun | 0 W zolang Victron niet geïntegreerd is |

De kernformule is:

```text
flex_export_budget
 = max(0,
       P1_export
       - grid_safety_reserve
       - quatt_ramp_reserve)
```

`discretionary_import_budget` is de resterende ruimte tot 4.000 W actuele netimport voor niet-verplichte economische starts.

## Effect op Decision en Tesla

Quatt zelf krijgt geen `ON/OFF`-intent. In plaats daarvan beïnvloedt hij hoeveel flexruimte aan andere loads wordt toegewezen.

Voor Tesla geldt in SHADOW:

- deadline/MUST blijft leidend;
- een PV-opportunity gebruikt `flex_export_budget_w` in plaats van ruwe P1-export;
- goedkope prijs is alleen een discretionaire opportunity als voldoende importbudget resteert;
- negatieve prijs blijft een expliciet economisch signaal;
- Easee Equalizer blijft de lokale veiligheidslaag en kan altijd verder terugregelen.

Hierdoor kan een modulerende Quatt niet ongemerkt dezelfde exportruimte claimen die Homey tegelijk aan Tesla denkt toe te wijzen.

## Effect op Warm Water Control

Warm Water Control is vanaf v0.9.7 `EM2_CONTROL_WW_V0.11` en blijft PURE SHADOW.

Voor PV-start wordt niet meer alleen naar ruwe export gekeken. De boilerstart vereist circa 1.900 W **flex-exportbudget ná grid- en Quatt-reserve**.

Voor prijsstarts geldt daarnaast:

- negatieve prijs + voldoende tariefhorizon: toegestaan als economische opportunity;
- goedkope prijs + voldoende tariefhorizon: alleen als geprojecteerde import inclusief circa 1.900 W boiler binnen het discretionaire importbudget blijft;
- onvoldoende importbudget: `WAIT_IMPORT_BUDGET`.

De bestaande run-locks blijven gelden:

| Startreden | Run-lock |
|---|---:|
| `CATCHUP` | 0 min opportunity-lock |
| `EXPORT` | 15 min |
| `PV_FORECAST` | 15 min |
| `PRICE_NEGATIVE` | 30 min |
| `PRICE_CHEAP` | 30 min |

Het warmwaterdagdoel en de confirmed-heating fallback uit v0.9.5 blijven ongewijzigd.

## Later: Victron / batterij

Het budgetmodel is bewust al batterij-ready. Nu is:

```text
battery_support_w = 0
battery_integrated = false
```

Na Victron-integratie kan de batterijlaag toegestane laad-/ontlaadruimte aan hetzelfde budget toevoegen zonder de betekenis van Quatt te veranderen.

Doelverdeling:

```text
Installatieveiligheid / netlimieten
        ↓
Easee Equalizer (lokale EV-veiligheid)
        ↓
Victron EMS (later: batterij/net)
        ↓
Energy Core v2 gedeeld budget
        ├── Quatt = comfort / observe-only
        ├── boiler = flex, met comfortdeadline
        └── Tesla = flex, met laaddeadline
```

Victron mag later batterijvermogen inzetten om import/export te optimaliseren, maar Homey hoeft daarvoor de Quatt niet fysiek te sturen. Quatt blijft een bekende comfortlast die eerst in het budget wordt gerespecteerd.

## Warmwaterstate

`EM2_WW_STATE_V0.8` houdt het dagdoel `OP_TEMPERATUUR_ONCE_PER_DAY` bij. Confirmed-heating accounting blijft:

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

Na `goalReachedToday=true` wordt dezelfde kalenderdag geen verplichte heropwarming geopend (`sameDayReheat=false`).

## Validatie v0.9.7

De veilige cut-over heeft de actieve v0.9.6 eerst uitgeschakeld en daarna v0.9.7 geactiveerd. De eerste v0.9.7-publicatie valideerde:

- `publisher_version = EM2_CORE_PUBLISH_V0.9.7`;
- `schema_version = 2.5`;
- `state_revision = decision_revision = shadow_revision = 329`;
- Quatt live in de centrale State/publicatie;
- `energy_budget` live gepubliceerd;
- `control_mode = SHADOW`;
- `quatt.control_mode = OBSERVE_ONLY`;
- `deviceWrites = false`;
- `physicalWritePerformed = false`;
- `quattWritePerformed = false`.

Op het validatiemoment stond Quatt vrijwel in standby (10,3 W). De Quatt-reserve was daarom 100 W. Bij 184 W netexport en 200 W gridreserve resteerde terecht 0 W flex-exportbudget.

## Operationeel Homey-loadbudget

- 1 × `getDevices()` per 5 minuten, **inclusief Quatt**;
- 1 × `getVariables()` per 5 minuten;
- alle State/Decision/WW-berekeningen daarna in-memory;
- PBTH prijscontext iedere 15 minuten via de bestaande Context-scheduler;
- geen tweede PBTH-scheduler;
- GitHub-publicatie gethrottled;
- website: nul Homey-calls.

> Laatste update: **19 augustus 2026 — PBTH PriceContext v0.3.** PBTH/DAP15 `NL_Netherlands` is nu de gevalideerde, null-safe prijscontextbron in PURE SHADOW. De adapter gebruikt de bestaande 15-minuten Context-scheduler en heeft geen actuatorwrites. WW Planner/Control-koppeling volgt pas na afzonderlijke shadowvalidatie.
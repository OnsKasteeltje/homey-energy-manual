# Energie Manager PV

## Operationele status

De centrale productiearchitectuur draait op **Energy Core v2**:

```text
EM v2 | 30 Context | Price + PV v0.4
                │
                ▼
EM v2 | 00 Core Tick | v0.9.7
                │
                ├─ State + gedeeld energie-/flexbudget
                ├─ Decision
                ├─ Shadow
                ├─ Warm Water State
                ├─ Warm Water Control (PURE SHADOW)
                └─ Publish · schema 2.5
```

`v0.9.7` is de actuele Core-versie. De vorige `v0.9.6` is uitgeschakeld en blijft als rollbackversie aanwezig. Voor prijscontext blijft **Price + PV v0.4** de actieve productieversie; kandidaat v0.5 is na een mislukte read-only validatie uitgeschakeld.

## Centrale single-reader architectuur

Iedere vijf minuten leest Core Tick maximaal één gezamenlijke Homey-device-snapshot en één Logic-snapshot. P1, PV, Tesla/Easee, boiler, Quatt en overige relevante devices komen dus uit dezelfde cyclus. Alle verdere State-, Decision-, Shadow- en Control-berekeningen gebeuren in-memory.

Quatt veroorzaakt daardoor **geen extra periodieke `getDevices()`-call**.

De website leest alleen de gepubliceerde GitHub-snapshot; websitebezoek veroorzaakt nul Homey-calls.

## Actuele publicatie

De centrale publieke state staat in:

```text
docs/data/energy-state-v2.json
```

Actueel:

```text
schema_version    = 2.5
publisher_version = EM2_CORE_PUBLISH_V0.9.7
control_mode      = SHADOW
```

State, Decision en Shadow worden revision-consistent gepubliceerd.

## Rollen van de grote energieverbruikers

Energy Core maakt expliciet onderscheid tussen comfortlasten en flexlasten:

| Load | Rol | Door Energy Core fysiek gestuurd? |
|---|---|---|
| Quatt | `COMFORT_BASELOAD` | nee, `OBSERVE_ONLY` |
| Boiler | flexload met warmwaterdoel/deadline | nog PURE SHADOW |
| Tesla | flexload met optionele laad-deadline | centrale Decision; fysieke migratie apart |
| Victron/batterij | toekomstige buffer/netlaag | nog niet geïntegreerd |

Quatt wordt dus serieus meegenomen in de energieverdeling zonder dat Homey de warmtepomp op basis van korte prijs- of PV-schommelingen gaat schakelen.

## Quatt in State

De primaire elektrische meetwaarde is `Quatt CIC.measure_power`. Vanuit dezelfde snapshot publiceert Energy Core onder andere:

```text
quatt.power_w
quatt.thermal_power_w
quatt.cop_1 / cop_2
quatt.working_mode_1 / working_mode_2
quatt.thermostat_heating_on
quatt.cv_requested
quatt.cv_flame
```

Elektrisch Quatt-vermogen telt als woningverbruik. Thermisch vermogen en COP zijn diagnostiek en worden niet als elektrische energie opgeteld.

Quatt wordt expliciet gemarkeerd met:

```text
role         = COMFORT_BASELOAD
control_mode = OBSERVE_ONLY
controllable = false
```

## Gedeeld energie-/flexbudget

P1 bevat het actuele Quatt-verbruik al. Het huidige Quatt-vermogen wordt daarom **niet nogmaals van de P1-export afgetrokken**. Dat zou dubbel tellen.

Wel reserveert Core extra ruimte voor mogelijke Quatt-ramp-up:

```text
flex_export_budget
 = max(0,
       P1_export
       - 200 W gridreserve
       - Quatt-rampreserve)
```

De Quatt-rampreserve is momenteel:

- 100 W wanneer Quatt vrijwel idle is;
- zodra Quatt ≥250 W gebruikt: minimaal 350 W;
- vervolgens 25% van actueel Quatt-vermogen;
- maximaal 750 W.

Daarnaast publiceert Core een discretionair importbudget tot 4.000 W actuele netimport voor economische starts van flexloads.

## Effect op Tesla

Tesla-opportunities gebruiken vanaf v0.9.7 het **flex-exportbudget** in plaats van kale P1-export. Daardoor wordt een deel van het overschot niet tegelijk aan Tesla beloofd terwijl de Quatt nog kan moduleren.

De hoofdregels zijn:

- deadline/MUST blijft leidend;
- PV-opportunity: voldoende flex-exportbudget na Quatt- en gridreserve;
- goedkope prijs: alleen wanneer voldoende discretionair importbudget resteert;
- negatieve prijs: expliciete economische opportunity;
- Easee Equalizer blijft altijd de lokale veiligheidslaag en mag verder terugregelen.

## Effect op warm water

Warm Water Control is vanaf v0.9.7 `EM2_CONTROL_WW_V0.11` en blijft **PURE SHADOW**:

```text
readOnly=true
deviceWrites=false
physicalWritePerformed=false
quattWritePerformed=false
```

Voor een PV-gedreven boilerstart moet ongeveer 1.900 W flex-exportbudget beschikbaar zijn **na** Quatt- en gridreserve. Een top-PV-forecastmoment vereist minimaal 500 W flex-exportbudget.

Bij goedkope stroom wordt bovendien gecontroleerd of de geprojecteerde import na een boilerstart binnen 4.000 W blijft. Zo niet, dan volgt `WAIT_IMPORT_BUDGET` in plaats van een nieuwe economische boilerstart.

De bestaande warmwaterregels blijven gelden: één `OP_TEMPERATUUR`-doel per dag, confirmed-heating fallback en opportunity-specifieke run-locks.

### PBTH prijshorizon

De beoogde full-horizon implementatie gebruikt PBTH `prices_json` met periode `next_hours`. Voor DAP15 geldt één numerieke array-entry per 15 minuten. De payload bevat geen timestamps; daarom mogen geen tijdstempels uit de payload worden verondersteld of verzonnen. De resterende horizon moet worden berekend vanaf het begin van het huidige kwartierslot plus het aantal geldige aaneengesloten slots maal 15 minuten, minus de reeds verstreken tijd in het huidige slot.

De policy is:

```text
>= 12 uur          FULL
6 tot 12 uur       INTRADAY
< 6 uur            DIAGNOSTIC
DEGRADED/MISSING   DIAGNOSTIC
```

`coversTomorrow10` moet worden bepaald door het werkelijke berekende horizon-einde te vergelijken met 10:00 de volgende dag in `Europe/Berlin`. Nachtvoorverwarming is alleen horizon-eligible als zowel `FULL` als `coversTomorrow10=true` geldt.

Op **19 augustus 2026** is kandidaat `EM v2 | 30 Context | Price + PV v0.5` read-only naast v0.4 opgebouwd. De Homey Advanced Flow accepteerde de `prices_json(next_hours)`-kaart, maar de `prices`-outputtoken werd in de geteste tokenketen niet als bruikbare JSON aan de vervolgstap doorgegeven. Een aparte buffer-readback resulteerde in diagnosecode **-2** (lege/niet-parseerbare JSON-buffer). Daardoor kon geen betrouwbare exacte horizon worden gemeten.

De cut-over is daarom bewust **niet** uitgevoerd: v0.5 en de tijdelijke PBTH-probes zijn uitgeschakeld en v0.4 blijft actief. Dit is een integratie-/tokentransportblokkade en geen aanwijzing dat de zichtbare PBTH-prijswaarden zelf onjuist zijn. Er zijn tijdens deze test geen fysieke actuatorwrites uitgevoerd; de WW Planner blijft `readOnly=true`, `deviceWrites=false` en PURE SHADOW.

## Toekomstige Victron-integratie

Hetzelfde budgetmodel is voorbereid op batterijsteun. Zolang Victron niet geïntegreerd is:

```text
battery_support_w = 0
battery_integrated = false
```

Later kan Victron toegestane batterij-laad/ontlaadruimte aan het centrale budget toevoegen. De rolverdeling blijft dan:

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer voor lokale EV-veiligheid
          ↓
Victron EMS voor batterij/net (later)
          ↓
Energy Core v2 voor huishoudelijke flexorchestratie
          ├─ Quatt: comfort / observe-only
          ├─ boiler: flex + comfortdeadline
          └─ Tesla: flex + laaddeadline
```

Fysieke Quatt-aansturing blijft buiten scope totdat daarvoor apart een veilige en expliciet gewenste Control-policy bestaat.

## Validatie 18 augustus 2026

De eerste v0.9.7-publicatie liet schema 2.5 en gelijke State/Decision/Shadow-revision 329 zien. Op dat moment gebruikte Quatt 10,3 W en stond hij praktisch idle. De Quatt-rampreserve was daarom 100 W. Bij 184 W netexport en 200 W gridreserve resteerde terecht 0 W flex-exportbudget.

De validatie bevestigde tevens dat Quatt `OBSERVE_ONLY` bleef en dat geen fysieke boiler- of Quatt-write vanuit deze Core plaatsvond.

> Laatste functionele update: **19 augustus 2026 — PBTH v0.5 full-horizon kandidaat veilig teruggerold na tokentransport-validatiefout.** Price + PV v0.4 blijft productie; WW Planner blijft PURE SHADOW en zonder fysieke writes.
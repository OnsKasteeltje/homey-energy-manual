# Energie Manager PV

## Operationele status

De Energie Manager draait sinds 17 augustus 2026 op **Energy Core v2**. De centrale operationele kern is:

```text
EM v2 | 30 Context | Price + PV v0.1
                │
                ▼
EM v2 | 00 Core Tick | v0.9.5
                │
                ├─ State
                ├─ Decision
                ├─ Shadow
                ├─ Warm Water State
                ├─ Warm Water Control (PURE SHADOW)
                └─ Publish
```

De eerdere architectuur met een losse State Collector, Allocator Shadow, aparte Shadow Manager en meerdere zelfstandige publishers is **niet meer de leidende productiearchitectuur**. Die flows kunnen nog als legacy/rollback of diagnose aanwezig zijn, maar mogen niet als actuele kern worden gelezen.

De volledige technische beschrijving staat op [Energy Core v2](energy-core-v2.md).

## Centrale single-reader architectuur

`EM v2 | 00 Core Tick | v0.9.5` vormt de centrale regelcyclus. Iedere vijf minuten wordt maximaal één gezamenlijke device-snapshot en één Logic-snapshot gelezen. Alle downstream-berekeningen gebruiken daarna dezelfde in-memory state en dezelfde revision.

Belangrijkste ontwerpregels:

- maximaal één `getDevices()` per Core Tick;
- maximaal één `getVariables()` per Core Tick;
- State, Decision, Shadow en Control-intent horen bij dezelfde revision;
- websitebezoek veroorzaakt geen Homey-calls;
- publicatie naar GitHub is gethrottled en veroorzaakt geen extra device-scan;
- per fysieke actuator bestaat uiteindelijk precies één automatische writer.

## Actuele publicatie

De website gebruikt als actuele bron onder andere:

```text
docs/data/energy-state-v2.json
```

De actuele publisher identificeert zich als:

```text
schema_version    = 2.3
publisher_version = EM2_CORE_PUBLISH_V0.9.5
control_mode      = SHADOW
```

Live state, Decision en Shadow worden met dezelfde revision gepubliceerd. De daghistorie wordt parallel bijgehouden door `EM v2 | 70 History | Day Series` zonder extra device-read.

## Warm water

Het primaire warmwaterdoel is **OP_TEMPERATUUR eenmaal per lokale kalenderdag**. Zodra het doel betrouwbaar is bereikt, blijft `goalReachedToday=true` tot de dagwissel. Avondelijk warmwatergebruik opent het dagdoel niet opnieuw (`sameDayReheat=false`).

Thermostaatdetectie:

```text
boiler aan + >1500 W gedurende 15 min
    → verwarming bevestigd

daarna boiler nog aan + <100 W gedurende 10 min
    → OP_TEMPERATUUR
```

### Fallback-accounting v0.9.5

De 240-minutenfallback gebruikt vanaf Core Tick v0.9.5 **bevestigde verwarmingsminuten** en niet langer de tijd dat het boilerrelais alleen maar aan stond.

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

`boilerOnMinToday` blijft beschikbaar als diagnostische teller, maar is niet meer de bron voor de fallbackbeslissing. De state publiceert hiervoor `fallbackAccounting = CONFIRMED_HEATING_MINUTES`.

## Warm Water Control

Warm Water Control is momenteel `EM2_CONTROL_WW_V0.10` en draait volledig in **PURE SHADOW**:

- `readOnly=true`;
- `deviceWrites=false`;
- `physicalWritePerformed=false`.

De planner kan onder meer `BOILER_ON`, `BOILER_OFF` of `HOLD` adviseren op basis van deadline, actuele export, prijs en PV-forecast, maar v2 schakelt de boiler nog niet fysiek.

Opportunity-starts gebruiken passende run-locks:

| Startreden | Run-lock |
|---|---:|
| `CATCHUP` | geen opportunity-lock |
| `EXPORT` | 15 min |
| `PV_FORECAST` | 15 min |
| `PRICE_NEGATIVE` | 30 min |
| `PRICE_CHEAP` | 30 min |

## Tesla en Equalizer

De Easee Equalizer blijft de harde lokale veiligheids- en load-balancinglaag. Homey mag deze bescherming nooit overrulen.

Tesla-Control is nog niet volledig naar de fysieke v2-Control-laag gemigreerd. Tot die migratie expliciet is gevalideerd blijft de bestaande fysieke Tesla-writer de productieroute, terwijl Energy Core v2 de centrale state, context en beslisarchitectuur levert.

Een Tesla-deadline kan actief of afwezig zijn. Zonder deadline kan de Tesla als flexibele energie-/exportbuffer worden gebruikt; met deadline krijgt tijdig voldoende laden uiteindelijk prioriteit boven opportunistische optimalisatie.

## Quatt en toekomstige Victron-integratie

Quatt wordt als relevante grootverbruiker in de v2-state/allocatiearchitectuur meegenomen zonder onnodige extra Homey device-reads. Fysieke Quatt-aansturing valt buiten scope zolang die niet apart veilig is ontworpen en gevalideerd.

Victron/batterij-integratie sluit later aan op dezelfde architectuur: centrale state, gedeeld vermogensbudget en expliciete Control-route. Victron zelf blijft de primaire laag voor batterij- en netregeling; Homey orkestreert flexloads daarboven.

## Veiligheids- en regelhiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer load balancing
          ↓
Victron grid/batterijregeling (later)
          ↓
Energy Core v2
          ↓
Flexloads: Tesla / boiler / overige
```

## Legacy-status

Flows uit architectuur v1, zoals de losse State Collector, Allocator Shadow, `Energie Manager PV - Shadow Mode` en afzonderlijke publishers, zijn niet meer de referentie voor de actuele productiearchitectuur. Ze worden alleen behouden zolang ze nog aantoonbaar nodig zijn voor rollback, historie, veiligheid of gecontroleerde migratie.

De gecontroleerde Legacy Cleanup verwijdert of deactiveert alleen onderdelen waarvan veilig vaststaat dat ze volledig door v2 zijn vervangen.

> Laatste functionele update: **18 augustus 2026 — Energy Core v2 / Core Tick v0.9.5 actief.** Confirmed-heating fallback-accounting is operationeel; Warm Water Control blijft PURE SHADOW zonder fysieke writes.
---
component: business-case-engine-v2
title: EMS Business Case Engine v2
status: shadow
architecture_status: implemented-read-only
last_verified: 2026-08-26
sources:
  - docs/javascripts/business-case-engine-v2.js
  - docs/javascripts/business-case-oracle-v0.1.js
  - docs/javascripts/business-case-history-adapter-v0.1.js
  - docs/data/business-case-scenarios-v2.json
  - docs/data/energy-day-v2.json
  - docs/data/energy-day-series-7d.json
---

# EMS Business Case Engine v2

## 1. Doel

De Business Case Engine maakt de economische onderbouwing van batterij/EMS-keuzes reproduceerbaar en evidence-driven. De component simuleert counterfactual scenario's op dezelfde historische woningdata en scheidt fysieke aannames, economische aannames, EMS-strategie en gemeten evidence.

De volledige component is **read-only**: `controlImpact=false`. Er bestaat geen writerroute naar Homey, Easee, boiler, Power Intent of Victron.

## 2. Architectuur

```text
energy-day / day-series history
P1 + PV + EV + WW + validity
             │
             ▼
Business Case History Adapter v0.1
+ expliciete fixed/dynamic tariffs
             │
             ▼
      normalized time steps
             │
      ┌──────┴──────────────────────┐
      ▼                             ▼
Business Case Engine v2     Perfect-information Oracle v0.1
replay kernel               dynamic programming
      │                             │
      ├─ no battery                 └─ Oracle targets
      ├─ self-consumption                    │
      └─ EMS replay                          ▼
      │                              canonical replay kernel
      └──────────────┬───────────────────────┘
                     ▼
        energy/economic decomposition
                     │
                     ├─ avoided import/export delta
                     ├─ conversion + standby losses
                     ├─ throughput/degradation
                     ├─ terminal SOC
                     ├─ evidence quality
                     └─ NPV/payback/capture ratio
                     │
                     ▼
            evidence/calibration loop
```

## 3. Tijdstap en waarheidsbron

De primaire rekeneenheid is een tijdstap, niet een jaartotaal. De bestaande historylaag levert 5-minutenmetingen. `business-case-history-adapter-v0.1.js` vertaalt `p1W`, validity en relevante evidence naar het BC-contract.

Per tijdstap zijn minimaal nodig:

- geldige P1/netmeting (`gridW` / `p1W`);
- importprijs in euro/kWh;
- exportvergoeding in euro/kWh;
- intervalduur;
- optioneel `emsBatteryTargetW` voor EMS replay.

`NULL_IS_UNKNOWN_NEVER_ZERO` is bindend. Ongeldige meet- of tariefdata wordt niet als 0 geïnterpreteerd; replay rapporteert `validSamples`, `invalidSamples`, `coverage` en quality.

## 4. Vier modellagen

De BC houdt vier grenzen expliciet gescheiden:

1. **Physical model** — capaciteit, SOC-band, charge/discharge power, efficiency, standby en degradation;
2. **Economic model** — import/exporttarief, CAPEX, onderhoud, discount rate en residual value;
3. **EMS strategy model** — self-consumption of gereplayde EMS-targets;
4. **Evidence/calibration model** — werkelijk gemeten P1/PV/EV/WW en later Victron battery telemetry.

Een wijziging in één laag mag niet impliciet aannames in een andere laag veranderen.

## 5. Fysiek batterijmodel

Ieder scenario bevat expliciet nominale capaciteit, min/max/initial SOC, maximaal AC laad-/ontlaadvermogen, afzonderlijke charge/discharge efficiency, standbyvermogen en degradation cost per throughput-kWh.

AC-bus tekenconventie:

```text
+W = batterij laden / extra load
 0 = idle
-W = batterij ontladen / supply
```

SOC blijft binnen de ingestelde band. Niet-uitvoerbare energie wordt als `curtailedChargeKWh` / `curtailedDischargeKWh` gepubliceerd.

## 6. Strategieën

### 6.1 BASELINE_NO_BATTERY

De gemeten netimport/export blijft ongewijzigd en vormt de economische nulmeting.

### 6.2 BATTERY_SELF_CONSUMPTION

Export laadt de batterij en import ontlaadt de batterij, begrensd door fysieke constraints. Hiermee wordt de pure fysieke opslagwaarde geïsoleerd van EMS/prijsoptimalisatie.

### 6.3 BATTERY_EMS_REPLAY

`emsBatteryTargetW` wordt per tijdstap gereplayd binnen exact dezelfde fysieke constraints. Hierdoor kan een actuele of SHADOW EMS-strategie tegen dezelfde historische woningdata worden beoordeeld.

### 6.4 Perfect-information Oracle v0.1

`business-case-oracle-v0.1.js` is een afzonderlijke dynamic-programming optimizer met perfecte kennis van de volledige horizon. Hij gebruikt dezelfde SOC-, vermogen-, efficiency-, standby-, tariff- en degradation-semantiek als de replay-engine.

De Oracle discretiseert batterij-energie (`energyStepKWh`, standaard 0,1 kWh) en rekent terminal energy value mee. Het resultaat wordt vervolgens opnieuw door de canonieke `BATTERY_EMS_REPLAY` kernel gevoerd; economische accounting blijft dus op één plek.

De Oracle is een benchmark/bovengrens voor de gekozen discretisatie, geen voorspelling van gerealiseerde EMS-prestatie.

## 7. EMS capture en onzekerheid

Wanneer baseline, EMS replay en Oracle beschikbaar zijn:

```text
EMS capture ratio =
(EMS value - no-battery value) /
(Oracle value - no-battery value)
```

De doelarchitectuur onderscheidt daarnaast:

```text
Oracle / perfect information
Forecast-realistic EMS
Realized EMS
```

Daarmee kunnen later forecast penalty en control/constraint penalty afzonderlijk worden verklaard.

## 8. Economische decompositie

Iedere euro moet herleidbaar zijn:

```text
baseline energy cost
scenario energy cost
--------------------
gross operational saving
- degradation cost
--------------------
net operational saving
```

De energiekant publiceert baseline/scenario import en export, charge/discharge, throughput, equivalent full cycles, conversion loss, standby, curtailed energy, self-consumption delta, avoided import en terminal SOC.

`financialCase()` voegt CAPEX, onderhoud, residual value, discount rate, NPV en simple payback toe. CAPEX wordt niet verzonnen wanneer een gevalideerde actuele prijs ontbreekt.

## 9. Evidence hardening

Generieke aannames worden geleidelijk vervangen door gemeten evidence. Iedere calibratiecandidate houdt bron, periode, sample-count en quality/confidence traceerbaar.

Evidence-prioriteit:

1. werkelijk AC charge/discharge en SOC uit Victron zodra beschikbaar;
2. P1 import/export en PV uit bestaande history;
3. gemeten battery conversion/standby losses;
4. werkelijk throughput/cycling;
5. forecast-versus-realized verschil;
6. EMS requested versus realized battery behavior.

Een enkele gebeurtenis promoveert nooit automatisch een structurele BC-aanname.

## 10. Annualisering en sensitiviteit

`annualizeReplay()` kan korte windows extrapoleren, maar <90 dagen krijgt verplicht `SHORT_EVIDENCE_WINDOW`. Voor investeringsbesluiten is bij voorkeur een volledig representatief jaar of expliciet seizoensgewogen model nodig.

Definitieve BC-publicatie gebruikt downside/base/upside of equivalente sensitiviteitsbanden voor materiële aannames zoals CAPEX, import/exporttarief, efficiency, standby, degradation/lifetime en forecastkwaliteit.

## 11. Scenario baseline

`business-case-scenarios-v2.json` bevat:

- 2 × Pylontech US5000;
- 3 × Pylontech US5000;
- BYD compatible reference.

Technische waarden zijn SHADOW-aannames met quality-label. CAPEX blijft `null` tot een actuele gevalideerde prijs is vastgelegd. De BYD-reference is geen definitieve productkeuze zolang exact model/capaciteit niet is gekozen.

## 12. Safety- en controlboundary

Harde invarianten:

- `readOnly=true`;
- `controlImpact=false`;
- geen Homey/device/network writes;
- geen wijziging van Power Intent;
- BC/Oracle mag realtime safety of control nooit overrulen;
- incomplete evidence degradeert zichtbaar;
- scenariovergelijkingen gebruiken dezelfde inputreeks en rekenregels;
- Oracle, forecast en realized blijven semantisch gescheiden.

Een toekomstige optimizer die runtime batterijpolicy voedt is **niet** deze component en vereist een aparte SHADOW/control release-gate.

## 13. Tests

Automatische tests dekken minimaal baseline-identiteit, self-consumption, SOC-band, power-clamps, evidence quality, degradation, annualisering, discounted NPV/payback, EMS capture, Oracle cheap→expensive shifting, read-only boundary en history-adapter null semantics.

## 14. Huidige status

| Onderdeel | Status |
|---|---|
| Replay kernel | IMPLEMENTED SHADOW/read-only |
| History adapter | IMPLEMENTED v0.1 |
| Perfect-information Oracle | IMPLEMENTED v0.1 |
| Scenario config 2×/3× Pylontech | IMPLEMENTED assumptions |
| BYD exact productmodel/CAPEX | OPEN |
| Fixed-price replay | technisch ondersteund |
| Dynamic tariff resolver | interface ondersteund; data-koppeling nog te voltooien |
| Forecast-realistic EMS replay | OPEN: Planner/Power Intent history koppelen |
| Victron measured calibration | OPEN tot fysieke integratie |
| >90d / jaar-history | OPEN |

## 15. Eerstvolgende hardening

1. actuele contract/tariefreeks direct aan de history adapter koppelen;
2. langere persistent history beschikbaar maken;
3. actuele gevalideerde CAPEX per hardwarevariant vastleggen;
4. forecast/Power Intent history als aparte replaybron opslaan;
5. na Victron-installatie efficiency/standby/throughput automatisch als calibration evidence berekenen;
6. Oracle discretisatie en terminal-value gevoeligheid benchmarken tegen externe optimizerreferenties.

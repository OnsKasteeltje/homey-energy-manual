---
component: business-case-engine-v2
title: EMS Business Case Engine v2
status: shadow
architecture_status: implemented-read-only
last_verified: 2026-08-26
sources:
  - docs/javascripts/business-case-engine-v2.js
  - docs/data/business-case-scenarios-v2.json
  - docs/data/energy-day-v2.json
  - docs/data/energy-day-series-7d.json
---

# EMS Business Case Engine v2

## 1. Doel

De Business Case Engine maakt de economische onderbouwing van batterij/EMS-keuzes reproduceerbaar en evidence-driven. De engine simuleert counterfactual scenario's op dezelfde historische woningdata en scheidt fysieke aannames, economische aannames, EMS-strategie en gemeten evidence.

De component is **read-only** en heeft geen control- of writerroute naar Homey, Easee, boiler of Victron.

## 2. Architectuur

```text
Historical evidence
P1 + PV + EV + WW + prijzen + validity
             │
             ▼
      Normalization / quality gate
             │
             ▼
     Counterfactual replay kernel
      ┌──────────┼───────────┐
      ▼          ▼           ▼
  no battery  self-use    EMS replay
      │          │           │
      └──────────┼───────────┘
                 ▼
   energy/economic decomposition
                 │
                 ├── avoided import
                 ├── lost/avoided export
                 ├── conversion losses
                 ├── standby losses
                 ├── throughput/degradation
                 └── terminal SOC
                 │
                 ▼
     annualization + NPV/payback
                 │
                 ▼
       evidence/calibration loop
```

Een aparte perfect-information optimizer mag later een Oracle-resultaat leveren. De replay-engine noemt een eigen heuristic **nooit** Oracle. `compareBusinessCases()` accepteert alleen een onafhankelijk aangeleverd Oracle-resultaat voor de EMS capture ratio.

## 3. Tijdstap en waarheidsbron

De primaire replay-eenheid is een tijdstap. De actuele historylaag levert 5-minutenmetingen in `energy-day-v2.json` en 7-daagse historie in `energy-day-series-7d.json`.

Per tijdstap zijn minimaal nodig:

- geldige P1/netmeting (`gridW` / `p1W`);
- importprijs in euro/kWh;
- exportvergoeding in euro/kWh;
- intervalduur;
- optioneel `emsBatteryTargetW` voor replay van feitelijke/SHADOW EMS-beslissingen.

`NULL_IS_UNKNOWN_NEVER_ZERO` blijft bindend: ontbrekende data wordt uitgesloten en nooit naar 0 geïnterpreteerd. Evidence coverage en quality worden in ieder resultaat gepubliceerd.

## 4. Fysiek batterijmodel

Iedere scenario-config bevat expliciet:

- nominale capaciteit;
- min/max SOC;
- initial SOC;
- max AC charge/discharge power;
- afzonderlijke charge/discharge efficiency;
- standbyvermogen;
- degradation cost per throughput-kWh.

Sign-conventie voor de batterij aan de AC-bus:

```text
+W = batterij laden / extra net- of PV-load
 0 = idle
-W = batterij ontladen / supply naar woning/net
```

De engine houdt SOC binnen de ingestelde band en publiceert curtailed charge/discharge wanneer een gewenste actie fysiek niet uitvoerbaar is.

## 5. Strategieën

### 5.1 BASELINE_NO_BATTERY

Historische netimport/export blijft ongewijzigd. Dit is de economische nulmeting.

### 5.2 BATTERY_SELF_CONSUMPTION

Bij export wordt de batterij geladen; bij import wordt ontladen, begrensd door SOC, vermogen en efficiency. Deze strategie meet de pure fysieke waarde van opslag zonder prijs-/EMS-arbitrage.

### 5.3 BATTERY_EMS_REPLAY

De engine consumeert `emsBatteryTargetW` per tijdstap en voert de gewenste actie counterfactual uit binnen dezelfde fysieke constraints. Hiermee kan de echte EMS-strategie tegen dezelfde historie worden vergeleken.

### 5.4 Oracle / perfect information

Een Oracle is een **separate component/solver** met perfecte kennis van de volledige horizon en dezelfde fysieke/economische constraints. Een greedy heuristic mag niet als Oracle worden gepresenteerd. De BC Engine ondersteunt wel vergelijking van een aangeleverd Oracle-resultaat met EMS via:

```text
EMS capture ratio =
(EMS value - no-battery value) /
(Oracle value - no-battery value)
```

## 6. Economische decompositie

Iedere euro moet herleidbaar zijn. De kernoutput onderscheidt minimaal:

```text
baseline energy cost
scenario energy cost
--------------------
gross operational saving
- degradation cost
--------------------
net operational saving
```

De energiekant publiceert daarnaast:

- baseline/scenario import kWh;
- baseline/scenario export kWh;
- AC charge/discharge kWh;
- batterijthroughput;
- equivalent full cycles;
- conversion losses;
- standby losses;
- curtailed energy;
- self-consumption delta;
- avoided import;
- terminal SOC.

Financiële evaluatie voegt CAPEX, onderhoud, residual value, discount rate, NPV en simple payback toe. Financial metrics worden niet berekend met verzonnen CAPEX.

## 7. Evidence hardening

Generieke aannames worden geleidelijk vervangen door gemeten waarden. Iedere kalibratie houdt bron, periode, sample-count en confidence/quality bij.

Prioriteit voor evidence:

1. werkelijk AC charge/discharge en SOC uit Victron zodra beschikbaar;
2. P1 import/export en PV uit bestaande history;
3. werkelijk batterijverlies/standby uit gemeten energy balance;
4. werkelijk throughput/cycling/degradation-proxy;
5. forecast-versus-realized verschil;
6. EMS requested versus realized gedrag.

Een nieuwe gemeten waarde overschrijft een generieke aanname alleen wanneer meetkwaliteit en representativiteit expliciet voldoende zijn.

## 8. Forecast uncertainty

De BC rapporteert uiteindelijk drie economische niveaus:

```text
Oracle / perfect information
Forecast-realistic EMS
Realized EMS
```

Daaruit worden afzonderlijk forecast penalty en control/constraint penalty afgeleid. Een Oracle-resultaat mag nooit rechtstreeks als haalbare jaarlijkse besparing worden gepresenteerd.

## 9. Annualisering

Korte meetvensters mogen technisch worden geannualiseerd, maar krijgen `SHORT_EVIDENCE_WINDOW`. Tot minimaal 90 dagen representatieve historie wordt annualisering als voorlopig beschouwd. Seizoenseffecten worden niet weggepoetst door een simpele vermenigvuldigingsfactor.

Voor een investeringsbesluit is bij voorkeur een volledig jaar historische replay beschikbaar, of een expliciet seizoensgewogen model.

## 10. Scenario baseline

`business-case-scenarios-v2.json` bevat momenteel:

- 2 × Pylontech US5000;
- 3 × Pylontech US5000;
- BYD compatible reference.

Technische waarden zijn expliciete SHADOW-aannames. CAPEX blijft `null` tot actuele gevalideerde prijzen zijn vastgelegd. De BYD-reference is geen definitieve productkeuze zolang het exacte model niet is geselecteerd.

## 11. Safety en control boundary

Harde invarianten:

- `readOnly=true`;
- `controlImpact=false`;
- geen Homey/device writes;
- geen aanpassing van Power Intent;
- geen economische uitkomst mag realtime safety/control overrulen;
- incomplete evidence wordt zichtbaar gedegradeerd, niet geïmputeerd als waarheid;
- scenario's gebruiken dezelfde constraints om eerlijke vergelijking te garanderen;
- Oracle en realized/forecast resultaten worden nooit semantisch vermengd.

## 12. Tests

`tests/business-case-engine-v2.test.mjs` valideert minimaal:

- baseline-identiteit;
- self-consumption charge/discharge;
- SOC-band;
- EMS-target power clamp;
- evidence-quality bij invalid samples;
- degradation accounting;
- korte-window annualization warning;
- discounted NPV/payback;
- EMS capture ratio tegen onafhankelijk Oracle-resultaat.

## 13. Vervolgstappen

1. history normalizer bouwen die `energy-day-series-7d.json` direct naar BC samples omzet inclusief prijscontext;
2. meerdere weken/maanden persistent history beschikbaar maken;
3. gevalideerde CAPEX-componenten vastleggen per hardwarevariant;
4. onafhankelijke perfect-information optimizer toevoegen;
5. forecast-realistic replay koppelen aan Planner/Power Intent history;
6. na Victron-installatie measured efficiency/standby/throughput automatisch als calibration evidence opnemen.

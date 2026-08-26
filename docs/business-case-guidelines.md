# Business Case Engineering Guidelines

Deze guidelines zijn bindend voor iedere economische doorrekening van batterij-, EMS-, EV-, warmwater- en toekomstige flex-investeringen binnen het Home Energy Management System.

## B1 — Tijdreeks vóór jaartotaal

Een business case wordt primair berekend als counterfactual replay op historische tijdstappen. Jaarverbruik, jaar-PV en jaar-export zijn alleen sanity checks en nooit voldoende om batterijwaarde te bepalen.

Voorkeursbron is de meetonafhankelijke 5-/15-minuten history met P1 als elektrische waarheidsbron. `NULL_IS_UNKNOWN_NEVER_ZERO` blijft bindend.

## B2 — Vier strikt gescheiden modellagen

Iedere BC onderscheidt expliciet:

1. **Physical model** — capaciteit, SOC-band, vermogen, efficiency, standby, degradation;
2. **Economic model** — import/exporttarief, belastingen, contracttype, CAPEX, onderhoud, discount rate, residual value;
3. **EMS strategy model** — self-consumption, arbitrage, deadlines, opportunity, batterijprioriteit en power constraints;
4. **Evidence/calibration model** — werkelijke P1/PV/EV/WW/batterijtelemetrie en realized prices.

Een wijziging in één laag mag niet stilzwijgend aannames in een andere laag wijzigen.

## B3 — Geen verzonnen input

Ontbrekende CAPEX, efficiency, levensduur, degradatie of tariefcomponent wordt `null`/unknown of expliciet `PROVISIONAL` gemarkeerd. Een onbekende waarde wordt niet ingevuld met een schijnnauwkeurig getal om een volledige uitkomst te forceren.

Iedere aanname bevat waar relevant bron, datum, scenario en quality/confidence.

## B4 — Dezelfde constraints voor alle scenario's

Scenariovergelijkingen gebruiken dezelfde woninghistorie, prijsreeks, netconstraints en economische rekenregels. Alleen expliciet benoemde scenario-eigenschappen mogen verschillen.

Hiermee worden 2× Pylontech, 3× Pylontech, BYD en toekomstige varianten appels-met-appels vergeleken.

## B5 — Iedere euro is verklaarbaar

Netto operationele waarde wordt minimaal gereconcilieerd als:

```text
+ vermeden netinkoop
+ eventuele prijsarbitrage
+ overige expliciet gevalideerde baten
- gemiste terugleververgoeding
- conversieverliezen
- standby-/vermogenselektronicaverlies
- degradatiekosten
- overige expliciete variabele kosten
----------------------------------------
= netto operationele waarde
```

CAPEX/onderhoud/residual value worden daarna pas in NPV/payback verwerkt.

## B6 — Throughput en degradatie zijn first-class

De BC publiceert batterijthroughput, equivalent full cycles en degradation cost. Degradatie mag niet alleen als een verborgen levensduurcorrectie achteraf worden verwerkt.

Na Victron-integratie vervangen gemeten throughput en efficiency generieke aannames zodra de evidencekwaliteit voldoende is.

## B7 — Terminal SOC is onderdeel van de economie

Een simulatie mag geen fictieve winst boeken door de batterij aan het einde van de horizon kosteloos leeg te trekken of ongewaardeerde energie achter te laten. Terminal SOC wordt altijd gepubliceerd.

Voor optimalisatie over eindige horizons wordt terminal energy value of een expliciete terminal-SOC constraint toegepast.

## B8 — Oracle, forecast en realized zijn verschillende begrippen

De BC onderscheidt minimaal:

- **Oracle/perfect information** — theoretische bovengrens met volledige kennis van de horizon;
- **Forecast-realistic EMS** — wat met vooraf beschikbare informatie haalbaar was;
- **Realized EMS** — werkelijk gemeten gedrag/resultaat.

Een heuristic wordt nooit `Oracle` genoemd. Een Oracle moet uit een afzonderlijk gevalideerde optimizer komen die dezelfde fysieke/economische constraints gebruikt.

## B9 — EMS capture ratio

Waar een gevalideerd Oracle-resultaat bestaat, wordt de effectiviteit van ons EMS uitgedrukt als:

```text
EMS capture ratio =
(EMS value - no-battery value) /
(Oracle value - no-battery value)
```

Daarnaast worden forecast penalty en control/constraint penalty afzonderlijk gerapporteerd wanneer de benodigde datasets beschikbaar zijn.

## B10 — Evidence coverage is onderdeel van het resultaat

Iedere replay publiceert total/valid/invalid samples en coverage. Indicatieve kwaliteit:

- `HIGH`: ≥98% geldige relevante tijdstappen;
- `MEDIUM`: ≥90%;
- `LOW`: <90%.

Een economisch getal zonder evidencekwaliteit is onvolledig.

## B11 — Annualisering is geen bewijs

Korte meetvensters mogen technisch worden geannualiseerd voor exploratie, maar:

- <90 dagen krijgt verplicht `SHORT_EVIDENCE_WINDOW`;
- seizoenseffecten moeten zichtbaar blijven;
- voor een investeringsbesluit is bij voorkeur minimaal één volledig representatief jaar beschikbaar, of een aantoonbaar seizoensgewogen model.

## B12 — Sensitiviteit en onzekerheid

Definitieve BC's tonen geen enkelvoudige terugverdientijd als zekerheid. Minimaal worden base/downside/upside of equivalente sensitiviteitsbanden gebruikt voor materiële aannames zoals:

- import/exportprijs;
- batterij-CAPEX;
- usable capacity;
- efficiency/standby;
- degradation/lifetime;
- forecastkwaliteit;
- toekomstige contract-/salderingsregels.

## B13 — EMS runtime hardent de BC

Runtime-data vormt een terugkoppellus:

```text
BC assumption
     ↓
predicted operation
     ↓
EMS / battery runtime evidence
     ↓
predicted-versus-realized delta
     ↓
calibration candidate
     ↓
quality gate
     ↓
versioned BC assumption update
```

Een kalibratie wordt niet automatisch promoted op basis van één gebeurtenis. Bronperiode, sample-count en confidence blijven traceerbaar.

## B14 — BC beïnvloedt nooit realtime control

De Business Case Engine is read-only. Economische analyses mogen policyontwikkeling informeren, maar nooit rechtstreeks Power Intent, actuator-writers of safety-limits overschrijven.

Een toekomstige optimizer die wél runtime policy voedt is een andere component en doorloopt afzonderlijk SHADOW-, safety- en release-gates.

## B15 — Reproduceerbaarheid

Een gepubliceerd BC-resultaat is alleen geldig wanneer minimaal traceerbaar zijn:

- engine/schema revision;
- history/evidence window;
- scenario/config revision;
- tariff source/revision;
- strategy;
- input quality;
- financiële aannames;
- gegenereerde kern-KPI's.

Met dezelfde inputs moet de deterministische replay dezelfde uitkomst geven.

## B16 — Minimale KPI-set

Iedere volwaardige batterij-BC rapporteert minimaal:

- annual/net operational saving;
- NPV;
- simple en waar relevant discounted payback;
- import/export delta;
- self-consumption delta;
- avoided import;
- charge/discharge throughput;
- equivalent full cycles/year;
- losses en standby;
- degradation cost;
- terminal SOC;
- evidence coverage/quality;
- EMS capture ratio wanneer een gevalideerd Oracle beschikbaar is.

## B17 — Testregels

Nieuwe BC-logica bevat automatische regressietests voor minimaal:

- no-battery identiteit;
- energiebalans en tekenconventie;
- SOC-min/max;
- charge/discharge power-clamps;
- efficiencyverlies;
- degradation accounting;
- invalid/null data;
- tariff accounting;
- terminal SOC;
- annualization warnings;
- financial discounting;
- scenario isolation;
- Oracle/EMS semantische scheiding.

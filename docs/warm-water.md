# Warm water optimalisatie — Energy Core v2

**Status:** 🟢 actief in **PURE SHADOW**  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.4`  
**Context:** `EM v2 | 30 Context | Price + PV v0.1`  
**Fysieke v2-boilerwrites:** **uitgeschakeld**

De warmwaterregeling is onderdeel van Energy Core v2. De eerdere v1-productieflows zijn niet meer de operationele beslislaag. Core v2 observeert de elektrische boiler, leidt de dagstatus af en berekent iedere vijf minuten wat de gewenste aansturing zou zijn. Fysieke aan/uit-acties worden pas toegevoegd nadat de Shadow-logica volledig is gevalideerd.

## 1. Dagdoel

Het primaire dagelijkse comfortdoel is:

> **De elektrische boiler moet eenmaal per lokale kalenderdag aantoonbaar `OP_TEMPERATUUR` bereiken.**

De 240-minutenregel is alleen een fallback wanneer `OP_TEMPERATUUR` niet betrouwbaar kan worden vastgesteld.

Zodra het dagdoel is bereikt:

- `goalReachedToday=true` blijft gelatcht tot de lokale dagwissel;
- later warmwatergebruik opent het dagdoel niet opnieuw;
- `sameDayReheat=false`;
- WW Control adviseert het relais uit te zetten indien het nog aan staat;
- er volgt die dag geen nieuwe verplichte catch-up.

Daarmee is onderscheid gemaakt tussen **“de boiler is op dit moment volledig warm”** en **“het dagelijkse warmwaterdoel is vandaag al gehaald”**.

## 2. Detectie van OP_TEMPERATUUR

De gevalideerde detectie gebruikt het boilervermogen en de relaisstatus:

```text
boiler aan + vermogen > 1500 W gedurende minimaal 15 min
    → verwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende minimaal 10 min
    → interne thermostaat is afgeslagen
    → OP_TEMPERATUUR bereikt
```

Een terugkeer boven 100 W tijdens de low-power bevestiging onderbreekt die bevestiging.

De actuele state staat in `EM2_WW_State` en gebruikt schema `EM2_WW_STATE_V0.7`.

## 3. Niet automatisch direct na ochtendgebruik herverwarmen

Een belangrijk v2-principe is dat warmwatergebruik in de ochtend niet automatisch betekent dat de boiler direct op netstroom moet herverwarmen. Zolang comfort/deadline dit toelaten, wacht de planner op een gunstiger energiemoment.

Vóór **09:30** geldt daarom normaal:

- boiler uit → `HOLD`, wachten;
- boilerrelais nog aan terwijl het dagdoel open staat → Shadow kan `BOILER_OFF / SHOULD` adviseren om spontane thermostaat-herverwarming te voorkomen.

Dit laatste is relevant omdat een relais dat fysiek aan blijft staan later vanzelf opnieuw vermogen kan gaan trekken zodra de interne boilerthermostaat na warmwatergebruik weer sluit.

## 4. Opportunity planner

Vanaf 09:30 combineert v0.9.4 actuele netexport met verse prijs- en PV-forecastcontext.

### Startvoorwaarden en run-lock

| Opportunity | Startvoorwaarde | Minimum run-lock |
|---|---|---:|
| `EXPORT` | ≥ **2100 W** actuele netexport | **15 min** |
| `PV_FORECAST` | huidig uur top-4 PV-forecast én ≥ **500 W** actuele export | **15 min** |
| `PRICE_NEGATIVE` | negatieve stroomprijs én ≥ **30 min** tot volgend tariefuur | **30 min** |
| `PRICE_CHEAP` | huidige prijs goedkoper dan komende 4 uur én ≥ **30 min** tot volgend tariefuur | **30 min** |
| `CATCHUP` | verder wachten bedreigt het dagdoel/deadline | opportunity-lock **0 min**; deadline is leidend |

### Waarom prijs een tariefhorizon heeft

Een relatief goedkoop uur is niet voldoende reden om bijvoorbeeld om 10:45 te starten wanneer om 11:00 een nieuw, mogelijk duurder tarief begint. Daarom geldt:

```text
prijs gunstig
+ minimaal 30 minuten resterend in huidig tariefuur
    → prijsstart toegestaan

prijs gunstig
+ minder dan 30 minuten resterend
    → HOLD / WAIT_PRICE_HORIZON
```

Hierdoor past de startbeslissing bij de 30-minuten prijs-run-lock.

### Waarom PV een kortere lock heeft

Actuele PV/export kan sneller veranderen dan een uurtarief. Een PV- of exportstart krijgt daarom slechts **15 minuten** anti-flap/run-lock. Daarna mag de planner opnieuw optimaliseren. Als de opportunity verdwenen is en structureel ongunstige import ontstaat, kan `BOILER_OFF / SHOULD` volgen.

## 5. Context en freshness

`EM v2 | 30 Context | Price + PV v0.1` vernieuwt iedere 15 minuten:

- `M7_Price_Negative`;
- `M7_Price_Cheap_Next4h`;
- `M7_Price_Expensive_Next4h`;
- `M7_PV_Top4h`;
- `EM2_Context_UpdatedAt`.

Deze contextflow leest geen fysieke apparaten. Core v2 accepteert de context alleen wanneer deze maximaal **35 minuten** oud is. Bij stale context worden prijs en PV-forecast niet gebruikt; actuele netexport en harde catch-up blijven wel beschikbaar.

## 6. Deadline en fallback

De dagelijkse regelperiode eindigt om **19:00**. Als `OP_TEMPERATUUR` nog niet is bevestigd en verder uitstellen de fallback/deadline in gevaar brengt, krijgt `CATCHUP` prioriteit `MUST`.

Conceptueel:

```text
dagdoel nog open
    │
    ├─ vóór 09:30 → wachten
    │
    ├─ opportunity beschikbaar → starten met passende run-lock
    │
    ├─ geen opportunity → blijven wachten zolang dit veilig kan
    │
    └─ deadline in gevaar → CATCHUP / MUST

OP_TEMPERATUUR bereikt
    → dagdoel gelatcht
    → geen same-day reheat
```

## 7. Bekend aandachtspunt vóór fysieke Control

De huidige 240-minuten fallback gebruikt nog `boilerOnMinToday`, dus **relais-aan-tijd**. De ochtendobservatie van 18 augustus liet zien waarom dit niet nauwkeurig genoeg is: het relais kan uren aan staan terwijl de interne thermostaat open is en het element 0 W trekt.

Daarom moet vóór fysieke WW-Control de fallback worden omgezet naar **werkelijke/bevestigde verwarmingsminuten**. Het primaire `OP_TEMPERATUUR`-doel en de thermostaatdetectie worden hierdoor niet aangetast, maar de fallback/catch-up mag vóór fysieke aansturing niet op een opgeblazen relaisteller vertrouwen.

## 8. Samenwerking met andere energieverbruikers

WW is één flexibele belasting binnen Energy Core v2. De centrale architectuur moet uiteindelijk gezamenlijk budgetteren tussen onder andere:

- huishoudelijk basisverbruik;
- Tesla/Easee;
- elektrische boiler;
- Quatt als serieuze energieverbruiker;
- later Victron/batterij.

Daarom wordt de warmwaterplanner niet als zelfstandige losse productieflow verder uitgebouwd; hij consumeert dezelfde centrale state/context als de rest van de Energy Core.

## 9. Veiligheid en huidige Control-status

De actuele WW Control staat in `EM2_Control_WW` (`EM2_CONTROL_WW_V0.9`). De belangrijkste guards zijn:

```text
controlMode   = SHADOW
readOnly      = true
deviceWrites  = false
stateFresh    = true
revisionMatch = true
wwStateFresh  = true
```

De publicatie bevat daarnaast expliciet:

```text
physicalWritePerformed = false
```

`BOILER_ON`, `BOILER_OFF` en `HOLD` zijn dus **beslissingen/adviezen**, nog geen fysieke acties.

## 10. Actuele validatiestand

Op 18 augustus 2026 is Core Tick v0.9.4 succesvol gepubliceerd als `EM2_CORE_PUBLISH_V0.9.4`. De context was vers en State, Decision en Shadow stonden op dezelfde revision. De WW-policy bevatte aantoonbaar:

- `priceStartHorizonMin = 30`;
- `priceRunLockMin = 30`;
- `pvRunLockMin = 15`;
- `catchupRunLockMin = 0`;
- `contextFreshMinutes = 35`.

Op dat validatiemoment was `goalReachedToday=true`; daarom was de correcte Shadow-uitkomst `BOILER_OFF / MUST / GOAL_REACHED`.

> **Volgende WW-blocker vóór fysieke Control:** fallback-accounting van relais-aan-tijd naar werkelijk/bevestigd verwarmen corrigeren en daarna een volledige dagcyclus met de opportunity-planner observeren.

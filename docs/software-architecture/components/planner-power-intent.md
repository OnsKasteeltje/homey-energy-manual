---
component: planner-power-intent
title: 24h Energy Planner and Power Intent
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-26
sources:
  - Homey Advanced Flow: EM v2 | 45 Planner | 24h Energy Plan v0.3.1 SHADOW
  - Homey Advanced Flow: EM v2 | 46 Publish | Planner Shadow v0.1
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | WW Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | Actuator Commands v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 70 History | Day Series v0.5.4
  - Homey Advanced Flow: EM v2 | 76 Evidence | BC Planner Intent Recorder v0.3
---

# 24h Energy Planner and Power Intent

## Doel

Deze laag vertaalt de beschikbare energiecontext naar een 24-uurs SHADOW-plan en projecteert de actuele EMS-policy via Power Intent naar actuator-neutrale doelen. De kernarchitectuur is:

`Measurements + contract context -> 24h Planner SHADOW -> advisory plan`

`EMS policy -> Power Intent -> EV_target_W / WW target -> EV/WW Power Adapter -> writer lifecycle -> Easee/Boiler`

Planner, Power Intent en adapters zijn gescheiden verantwoordelijkheden. De Planner adviseert over toekomstige slots; Energy Core blijft runtime-policy-owner; Power Intent projecteert actuele policy; adapters vertalen alleen naar fysiek uitvoerbare apparaatopdrachten.

## Architectuurgrens

- **Energy Core / EMS policy** bezit MUST/opportunity-arbitrage, hysterese en runtimebeslissing.
- **24h Planner** maakt een read-only toekomstplan en mag runtimepolicy niet overrulen.
- **Power Intent** projecteert actuele Core-policy naar actuator-neutrale doelen.
- **EV/WW Power Adapters** bezitten apparaatvertaling, feasibility, quantization/clamping en fail-closed guards.
- **Writer lifecycle** bezit commanded/confirmed tracking, idempotency, dedupe, run-lease, retries en throttling.
- **Easee en Boiler** mogen elk slechts één actieve fysieke writer hebben.

Geen SHADOW-component voert fysieke device-writes uit.

## Tesla-policy-invariant

Voor Tesla gelden vanaf Planner v0.3.1 en Power Intent v0.2.1 twee strikt gescheiden laadredenen:

1. **PV opportunity** — laden mag alleen worden voorgesteld wanneer er minimaal 800 W verwacht of actueel P1/PV-flexoverschot beschikbaar is. Een goedkope of negatieve netprijs mag op zichzelf nooit een Tesla-opportunity creëren.
2. **Deadline / MUST** — wanneer een expliciete laadverplichting bestaat, heeft verwacht PV-overschot voorrang. Alleen de resterende noodzakelijke netenergie mag met de dynamische prijsforecast over de goedkoopste bruikbare slots vóór de deadline worden verdeeld.

Daarmee geldt expliciet:

`cheap price != Tesla opportunity trigger`

en:

`deadline required energy = PV first -> cheapest required grid slots`

Als later bewust prijsarbitrage zonder deadline gewenst zou zijn, moet dat een afzonderlijke policy/intent worden en mag dit niet onder `TESLA_CHARGE_OPPORTUNITY` worden verborgen.

## 24h Energy Planner v0.3.1 SHADOW

Planner v0.3.1 draait iedere 15 minuten met 45 seconden vertraging en kan handmatig worden gestart. De bestaande flow is in-place opgehoogd; flow-ID en Homey-folder-ID zijn behouden.

De Planner maakt een **96 × 15-minuten energy-balance forecast** en houdt de tijdas onafhankelijk van de prijsbron. Er zijn dus altijd 96 kwartier-slots, ook onder een FIXED-contract.

### Canonieke meetbron

Planner v0.3.1 leest `EM2_Day_History`, geproduceerd door `EM v2 | 70 History | Day Series v0.5.4`. Deze historie is measurement-control-independent en bevat iedere circa vijf minuten onder meer directe P1, de drie PV-bronnen, Tesla-vermogen en boilervermogen.

De Planner pollt hiervoor geen apparaten opnieuw en introduceert geen extra fysieke of netwerkafhankelijkheid in de control-laag.

### Base-loadmodel

Voor iedere bruikbare historische sample geldt:

`PV_W = SolarEdge_W + GoodWe4200_W + GoodWe2000_W`

Met P1 positief = import en negatief = export:

`house_W = P1_W + PV_W`

De eerste benadering van niet-flexibele/base-load is:

`base_W = max(0, house_W - Tesla_W - Boiler_W)`

Per lokale kwartierindex wordt een mediaanprofiel opgebouwd. Bij onvoldoende kwartiersamples wordt de globale mediaan gebruikt. Kwaliteit wordt expliciet gepubliceerd als `CURRENT_DAY_QUARTER_PROFILE`, `GLOBAL_MEDIAN_FALLBACK` of `MISSING`.

### PV-slotforecast

V0.3.1 fabriceert bewust geen weerscurve. Alleen kwartieren met voldoende gemeten same-day PV-samples krijgen een `pvForecastW` op basis van de mediaan van dat lokale kwartier. Onbekende toekomstige kwartieren blijven `null`.

De kwaliteit wordt gemarkeerd als `MEASURED_DAY_PERSISTENCE_LOW_CONFIDENCE` of `SUMMARY_ONLY`. Deze persistence-benadering is een tussenstap naar een echte weather-aware 15-minuten PV-forecast.

### Energy-balancevelden per slot

Elk slot bevat waar mogelijk `baseLoadForecastW`, `pvForecastW`, `netBeforeFlexW`, `importBeforeFlexW`, `pvSurplusBeforeFlexW`, prijs/contextclassificatie, forecastkwaliteit en SHADOW-acties voor Tesla, warm water en batterij.

Waar base-load en PV beide bekend zijn:

`netBeforeFlexW = baseLoadForecastW - pvForecastW`

Positief betekent verwachte import vóór flex-loads; negatief betekent verwacht PV-overschot vóór flex-loads. `gridHeadroomW` blijft expliciet `null` totdat fasebewuste 3×25 A headroom werkelijk is gemodelleerd.

### Tesla zonder deadline: PV-only opportunity

Als geen deadline/MUST actief is, worden Tesla-opportunity-slots uitsluitend geselecteerd uit slots met:

`pvSurplusBeforeFlexW >= 800 W`

Deze slots krijgen `OPPORTUNITY_PV_ONLY` en worden op verwacht PV-overschot gerangschikt. De prijs van het slot beïnvloedt deze opportunityselectie niet.

Als geen slot ten minste 800 W verwacht PV-overschot heeft, plant de Tesla-opportunitylaag geen laadslot — ook niet wanneer de dynamische prijs goedkoop of negatief is.

### Tesla met deadline: PV eerst, prijs voor noodzakelijke netenergie

Bij een actieve Tesla-deadline met resterende kWh worden eerst alle slots vóór de deadline bekeken. Slots met minimaal 800 W verwacht PV-overschot krijgen voorrang. Daarna worden de overige noodzakelijke slots bij een DYNAMIC-contract op prijs gerangschikt; bij FIXED geldt tijd als resterende differentiator.

De gepubliceerde policy is:

`PV_SURPLUS_THEN_CHEAPEST_REQUIRED_GRID_SLOTS`

De Planner verzint nog steeds geen Tesla-throughput per kwartier. `preferredSlots` zijn dus adviserende voorkeursvensters; de echte vermogensopdracht blijft verantwoordelijkheid van runtime EMS -> Power Intent -> EV Adapter.

### Warm water

Voor warm water blijft de bestaande circa 1.9 kW boilerrepresentatie gebruikt om resterende fallbackminuten naar energie om te rekenen en vóór 19:00 te alloceren. Warmwaterpolicy staat los van de hierboven aangescherpte Tesla-opportunity-invariant.

### Batterij

De batterij blijft `THEORETICAL_ONLY_NO_SOC`. V0.3.1 heeft een betere energiebalansbasis, maar beschikt nog niet over werkelijk Victron/Pylontech SOC of commissioningconstraints. Er wordt geen fysieke batterijdispatch gegenereerd.

### Plannerstatus

V0.3.1 publiceert onder meer `BLOCKED_STATE_MISSING`, `DEGRADED_BASE_LOAD_HISTORY`, `DEGRADED_PRICE_CONTEXT`, `DEGRADED_PV_SLOT_FORECAST` en `READY_SHADOW_V0.3.1`.

## Planner publication en BC evidence

`EM v2 | 46 Publish | Planner Shadow v0.1` publiceert het volledige SHADOW-plan als observability-only envelope naar `docs/data/energy-planner-shadow.json`. De publisher hardcodeert de Planner-versie niet zolang het safetycontract geldig blijft: `controlMode=SHADOW`, `readOnly=true`, `physicalWritePerformed=false`.

`EM v2 | 76 Evidence | BC Planner Intent Recorder v0.3` legt per kwartier onder meer base-loadforecast, PV-forecast, `netBeforeFlexW`, verwacht PV-overschot, prijs, gekozen Tesla/WW/batterij SHADOW-actie en actuele Power Intent targets vast. Hiermee ontstaat de basis voor `planned -> intent -> commanded -> actual -> financial result`.

De Evidence-flow had eerder `folder=null`; folderlocatie blijft een expliciete Homey-governancegate totdat aantoonbaar conform.

## Power Intent v0.2.1 SHADOW

Power Intent wordt getriggerd door wijziging van `EM2_Public_State` en is idempotent per source revision. Voor geldige output moeten Public State revision, Core State revision, Decision sourceRevision en WW Control sourceRevision gelijk zijn.

Bij mismatch is `valid=false`, `status=REVISION_MISMATCH` en het EV-doel fail-closed 0 W.

### EV-target contract

Bij `TESLA_CHARGE_DEADLINE`, indien resterende energie en toekomstige deadline geldig zijn:

`target_W = remaining_kWh / hours_to_deadline * 1000`

Bij `TESLA_CHARGE_OPPORTUNITY` geldt vanaf v0.2.1 uitsluitend:

- `flexExportBudgetW >= 800 W` -> `target_W = flexExportBudgetW`;
- anders -> `target_W = 0`.

Negatieve of goedkope prijs kan **geen** discretionary importtarget meer creëren voor `TESLA_CHARGE_OPPORTUNITY`. De output publiceert daarom `teslaOpportunityPolicy=PV_SURPLUS_ONLY` en `pricePolicy=DEADLINE_OPTIMIZATION_ONLY`.

Power Intent converteert niet naar ampère; elektrische feasibility hoort bij de EV Power Adapter.

## WW-target contract

De huidige Power Intent produceert WW nog binair:

- `BOILER_ON -> target_on=true`
- `BOILER_OFF -> target_on=false`
- `HOLD -> target_on=null`

`WW_target_W` blijft het toekomstige numerieke architectuurcontract. De adapter mag dit niet zelf uit policy verzinnen.

## EV Power Adapter v0.1 SHADOW

De EV-adapter vertaalt uitsluitend `EV_target_W` naar een theoretisch uitvoerbare Easee-opdracht. De topologie is 3 fasen × 230 V, minimaal 6 A, maximaal de geconfigureerde veilige stroom met harde bovengrens 16 A, zonder automatische 1↔3-faseschakeling.

`theoretical_A = EV_target_W / (3 × 230)`

`requested_A = floor(theoretical_A)`

Onder 6 A wordt 0 A gevraagd. De adapter verhoogt nooit het upstream vermogensbudget, valideert revision/schema/freshness en blijft fail-closed. In SHADOW blijft `commanded_A=null` en worden geen Easee-writes uitgevoerd.

## WW Power Adapter v0.1 SHADOW

De WW Power Adapter accepteert uitsluitend upstream WW-intent en introduceert geen prijs-, opportunity- of deadlinepolicy. `target_on=true/false/null` wordt deterministisch vertaald naar ON/OFF/HOLD shadow command. HOLD blijft semantisch verschillend van OFF.

De bestaande boilerwriter blijft fysieke eigenaar totdat validation en atomic cut-over zijn geslaagd.

## Generieke Actuator Commands v0.2 SHADOW

Actuator Commands accepteert de overgangsschema's van Power Intent, publiceert `EM2_ACTUATOR_COMMANDS_V0.2` en dedupliceert op source revision én input schema. EV- en WW-apparaatvertaling worden aan hun eigen Power Adapters gedelegeerd.

## Single-writer boundary en cut-over

Een fysieke writer mag pas worden geactiveerd via gecontroleerde atomic cut-over waarbij de bestaande productiewriter wordt uitgefaseerd. Vereisten zijn bewezen revision/schema alignment, freshness/fail-closed, mapping/feasibility, dedupe/idempotency, geen dubbele writes/history/notificaties en een bewezen rollbackpad.

Nooit mogen twee fysieke writers gelijktijdig dezelfde actuator sturen.

## Safety invariants

- geen device writes in Planner/Power Intent/Adapters zolang SHADOW actief is;
- Tesla opportunity is uitsluitend PV/exportbudgetgedreven;
- goedkope of negatieve prijs mag nooit zelfstandig Tesla opportunity charging starten;
- prijsoptimalisatie voor Tesla hoort alleen binnen deadline/MUST-planning;
- onbekende forecastdata blijft onbekend/null en wordt niet gefabriceerd;
- prijs is context, niet de eigenaar van de 24h tijdas;
- fasebewuste grid-headroom wordt pas gebruikt wanneer die werkelijk gemodelleerd is;
- adapters verhogen nooit upstream vermogensbudget;
- requested, commanded en confirmed blijven gescheiden;
- één fysieke writer per actuator na cut-over.

## Huidige status

| Onderdeel | Status |
|---|---|
| 24h Planner v0.3.1 | ACTIVE SHADOW; 96×15-min energy axis; Tesla PV-only opportunity |
| Base-load forecast | ACTIVE SHADOW; current-day quarter profile/global median fallback |
| PV slot forecast | ACTIVE SHADOW; measured-day persistence, low confidence; unknown = null |
| Tesla opportunity policy | PV_SURPLUS_ONLY; minimum 800 W |
| Tesla deadline price policy | PV first; cheapest required grid slots second |
| Phase-aware grid headroom | NOT MODELED |
| Planner Publisher v0.1 | ACTIVE OBSERVABILITY ONLY |
| BC Planner Intent Recorder v0.3 | ACTIVE READ-ONLY |
| Power Intent v0.2.1 | ACTIVE SHADOW; price cannot create Tesla opportunity |
| EV_target_W | ACTIVE SHADOW, numeriek |
| WW target_on | ACTIVE SHADOW, binair |
| WW_target_W | ARCHITECTUURCONTRACT / nog niet numeriek geproduceerd |
| EV Power Adapter v0.1 | ACTIVE SHADOW |
| WW Power Adapter v0.1 | ACTIVE SHADOW |
| EV fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| WW fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| Victron fysieke writer | NIET ACTIEF |

---
component: planner-power-intent
title: 24h Energy Planner and Power Intent
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-26
sources:
  - Homey Advanced Flow: EM v2 | 45 Planner | 24h Energy Plan v0.3 SHADOW
  - Homey Advanced Flow: EM v2 | 46 Publish | Planner Shadow v0.1
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | WW Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | Actuator Commands v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 70 History | Day Series v0.5.4
  - Homey Advanced Flow: EM v2 | 76 Evidence | BC Planner Intent Recorder v0.2
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

## 24h Energy Planner v0.3 SHADOW

Planner v0.3 draait iedere 15 minuten met 45 seconden vertraging en kan handmatig worden gestart. De bestaande flow is in-place opgehoogd van v0.2 naar v0.3; flow-ID en Homey-folder-ID zijn daardoor behouden.

De hoofdwijziging is dat de Planner niet langer primair een prijs-slotcalculator is, maar een eerste **96 × 15-minuten energy-balance forecast** maakt.

### Vaste 24-uurs tijdas

De tijdas is vanaf v0.3 onafhankelijk van de prijsbron. De Planner genereert altijd 96 kwartier-slots, ook onder een FIXED-contract.

Dit corrigeert een structurele beperking van v0.2: daar werd de slotlijst uit dynamische prijzen opgebouwd, waardoor een FIXED-contract geen volwaardige 96-slot planning opleverde.

Prijs is vanaf v0.3 context, niet de eigenaar van de planningstijdas.

### Canonieke meetbron

Planner v0.3 leest `EM2_Day_History`, geproduceerd door `EM v2 | 70 History | Day Series v0.5.4`. Deze historie is measurement-control-independent en bevat iedere circa vijf minuten onder meer:

- directe P1 `p1W` met validity;
- SolarEdge-, GoodWe 4.2 kW- en GoodWe 2.0 kW-vermogen;
- Tesla-vermogen;
- boilervermogen.

De Planner pollt hiervoor geen apparaten opnieuw en introduceert geen extra fysieke of netwerkafhankelijkheid in de control-laag.

### Base-loadmodel

Voor iedere bruikbare historische sample wordt eerst totale PV bepaald:

`PV_W = SolarEdge_W + GoodWe4200_W + GoodWe2000_W`

Met de P1-signconventie positief = import en negatief = export geldt vervolgens:

`house_W = P1_W + PV_W`

De eerste benadering van niet-flexibele/base-load is:

`base_W = max(0, house_W - Tesla_W - Boiler_W)`

Tesla en boiler worden dus uit de gemeten huishoudlast gehaald omdat zij expliciet door het EMS planbare flex-loads zijn. Andere nog niet direct in watt gemeten apparaten blijven in deze eerste base-loadschatting zitten.

Per lokale kwartierindex wordt een mediaanprofiel opgebouwd. Als een kwartier onvoldoende samples heeft, gebruikt v0.3 de globale mediaan als fallback. De kwaliteit wordt expliciet gepubliceerd als `CURRENT_DAY_QUARTER_PROFILE`, `GLOBAL_MEDIAN_FALLBACK` of `MISSING`.

### PV-slotforecast

V0.3 fabriceert bewust geen weerscurve. Alleen kwartieren waarvoor voldoende gemeten same-day PV-samples bestaan krijgen een `pvForecastW` op basis van de mediaan van dat lokale kwartier.

Onbekende toekomstige PV-kwartieren blijven `null`.

De kwaliteit wordt gemarkeerd als `MEASURED_DAY_PERSISTENCE_LOW_CONFIDENCE` of `SUMMARY_ONLY`. Deze persistence-benadering is een tussenstap naar een echte weather-aware 15-minuten PV-forecast en mag niet als volwaardige meteorologische voorspelling worden geïnterpreteerd.

### Energy-balancevelden per slot

Elk van de 96 slots bevat waar mogelijk:

- `baseLoadForecastW`;
- `pvForecastW`;
- `netBeforeFlexW`;
- `importBeforeFlexW`;
- `pvSurplusBeforeFlexW`;
- prijs/contextclassificatie;
- kwaliteit per forecastcomponent;
- Tesla-, warmwater- en batterijactie in SHADOW.

Waar base-load en PV beide bekend zijn:

`netBeforeFlexW = baseLoadForecastW - pvForecastW`

Positief betekent verwachte import vóór flex-loads; negatief betekent verwacht PV-overschot vóór flex-loads.

`gridHeadroomW` is in v0.3 expliciet `null`: fasebewuste 3×25 A headroom is nog niet gemodelleerd en wordt niet verzonnen.

### Hard obligations vóór opportunities

De Planner rangschikt eerst harde verplichtingen.

Voor Tesla gebruikt hij een actieve deadline, resterende kWh en het bestaande latest-start/deadlinevenster. Hij verzint nog steeds geen Tesla-throughput per slot; slots worden gerangschikt maar geen fictieve kWh toegekend.

Voor warm water wordt de bestaande circa 1.9 kW boilerrepresentatie gebruikt om resterende fallbackminuten naar energie om te rekenen en vóór 19:00 te alloceren.

Pas daarna worden opportunities en theoretische batterijmogelijkheden beoordeeld.

### Contract-aware ranking

Bij DYNAMIC worden kandidaten primair op prijs en daarna op verwacht PV-overschot gerangschikt.

Bij FIXED is prijs geen differentiator en wordt eerst op verwacht PV-overschot en daarna op tijd gerangschikt.

Hierdoor heeft de Planner ook onder het gekozen vaste-contractscenario inhoudelijke waarde.

### Batterij

De batterij blijft `THEORETICAL_ONLY_NO_SOC`. V0.3 heeft een betere energiebalansbasis, maar beschikt nog niet over een werkelijk Victron/Pylontech SOC-signaal of commissioningconstraints. Er wordt daarom geen fysieke batterijdispatch gegenereerd.

### Plannerstatus

V0.3 publiceert onder meer:

- `BLOCKED_STATE_MISSING`;
- `DEGRADED_BASE_LOAD_HISTORY`;
- `DEGRADED_PRICE_CONTEXT`;
- `DEGRADED_PV_SLOT_FORECAST`;
- `READY_SHADOW_V0.3`.

Degradatie is expliciet zichtbaar in plaats van ontbrekende data door verzonnen waarden te vervangen.

## Planner publication en BC evidence

`EM v2 | 46 Publish | Planner Shadow v0.1` publiceert het volledige SHADOW-plan als observability-only envelope naar `docs/data/energy-planner-shadow.json`. De publisher hardcodeert de Planner-versie niet en accepteert v0.3 zolang het safetycontract geldig blijft: `controlMode=SHADOW`, `readOnly=true`, `physicalWritePerformed=false`.

`EM v2 | 76 Evidence | BC Planner Intent Recorder v0.2` is aangepast aan de publisher-envelope en de v0.3-structuur `plan.plan.actions`. De recorder legt per kwartier onder meer vast:

- base-loadforecast;
- PV-forecast;
- `netBeforeFlexW` en verwacht PV-overschot;
- prijs;
- gekozen Tesla/WW/batterij SHADOW-actie;
- actuele Power Intent targets.

Hiermee ontstaat de basis voor de volgende closed-loop stap: `planned -> intent -> commanded -> actual -> financial result`.

De Evidence-flow heeft momenteel `folder=null`. Dit is een expliciete governance-afwijking en blijft open totdat hij aantoonbaar in de afgesproken `76 Evidence` Homey-folder is geplaatst. De functionele naamgeving alleen is niet voldoende voor RC-conformiteit.

## Power Intent v0.2 SHADOW

Power Intent wordt getriggerd door wijziging van `EM2_Public_State` en is idempotent per source revision. Voor geldige output moeten Public State revision, Core State revision, Decision sourceRevision en WW Control sourceRevision gelijk zijn.

Bij mismatch is `valid=false`, `status=REVISION_MISMATCH` en het EV-doel fail-closed 0 W.

## EV-target contract

Bij `TESLA_CHARGE_DEADLINE`, indien resterende energie en toekomstige deadline geldig zijn:

`target_W = remaining_kWh / hours_to_deadline * 1000`

Bij `TESLA_CHARGE_OPPORTUNITY` met voldoende flexbudget wordt het beschikbare flex/exportbudget gebruikt. Als geen exportbudget beschikbaar is maar prijs negatief/goedkoop is, kan het discretionary importbudget worden gebruikt. Zonder geldige opportunity is `target_W=0`.

Power Intent converteert niet naar ampère; elektrische feasibility hoort bij de EV Power Adapter.

## WW-target contract

De huidige Power Intent v0.2 produceert WW nog binair:

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

Actuator Commands accepteert de overgangsschema's `EM2_POWER_INTENT_V0.1` en `EM2_POWER_INTENT_V0.2`, publiceert `EM2_ACTUATOR_COMMANDS_V0.2` en dedupliceert op source revision én input schema. EV- en WW-apparaatvertaling worden aan hun eigen Power Adapters gedelegeerd.

## Single-writer boundary en cut-over

Een fysieke writer mag pas worden geactiveerd via gecontroleerde atomic cut-over waarbij de bestaande productiewriter wordt uitgefaseerd. Vereisten zijn bewezen revision/schema alignment, freshness/fail-closed, mapping/feasibility, dedupe/idempotency, geen dubbele writes/history/notificaties en een bewezen rollbackpad.

Nooit mogen twee fysieke writers gelijktijdig dezelfde actuator sturen.

## Safety invariants

- geen device writes in Planner/Power Intent/Adapters zolang SHADOW actief is;
- geen policy-arbitrage in adapters;
- onbekende forecastdata blijft onbekend/null en wordt niet gefabriceerd;
- prijs is context, niet de eigenaar van de 24h tijdas;
- fasebewuste grid-headroom wordt pas gebruikt wanneer die werkelijk gemodelleerd is;
- adapter verhoogt nooit upstream vermogensbudget;
- requested, commanded en confirmed blijven gescheiden;
- één fysieke writer per actuator na cut-over.

## Huidige status

| Onderdeel | Status |
|---|---|
| 24h Planner v0.3 | ACTIVE SHADOW; 96×15-min energy axis |
| Base-load forecast | ACTIVE SHADOW; current-day quarter profile/global median fallback |
| PV slot forecast | ACTIVE SHADOW; measured-day persistence, low confidence; unknown = null |
| Phase-aware grid headroom | NOT MODELED |
| Planner Publisher v0.1 | ACTIVE OBSERVABILITY ONLY |
| BC Planner Intent Recorder v0.2 | ACTIVE READ-ONLY; folder governance OPEN |
| Power Intent v0.2 | ACTIVE SHADOW |
| EV_target_W | ACTIVE SHADOW, numeriek |
| WW target_on | ACTIVE SHADOW, binair |
| WW_target_W | ARCHITECTUURCONTRACT / nog niet numeriek geproduceerd |
| EV Power Adapter v0.1 | ACTIVE SHADOW |
| WW Power Adapter v0.1 | ACTIVE SHADOW |
| EV fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| WW fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| Victron fysieke writer | NIET ACTIEF |

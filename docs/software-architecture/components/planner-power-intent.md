---
component: planner-power-intent
title: 24h Energy Planner and Power Intent
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-27
sources:
  - Homey Advanced Flow: EM v2 | 45 Planner | 24h Energy Plan v0.4.3 SHADOW
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

Deze laag vertaalt meetdata, contractcontext en forecastdata naar een 24-uurs SHADOW-plan en projecteert de actuele EMS-policy via Power Intent naar actuator-neutrale doelen.

`Measurements + forecasts + contract context -> 24h Planner SHADOW -> advisory plan`

`EMS policy -> Power Intent -> EV_target_W / WW target -> EV/WW Power Adapter -> writer lifecycle -> Easee/Boiler`

Planner, Power Intent en adapters zijn gescheiden verantwoordelijkheden. De Planner adviseert over toekomstige slots; Energy Core blijft runtime-policy-owner; Power Intent projecteert actuele policy; adapters vertalen alleen naar fysiek uitvoerbare apparaatopdrachten.

## Tesla-policy-invariant

Voor Tesla zijn twee laadredenen strikt gescheiden:

1. **PV opportunity** — zonder deadline mag laden alleen worden voorgesteld wanneer minimaal 800 W verwacht of actueel PV/exportoverschot beschikbaar is. Een goedkope of negatieve netprijs mag op zichzelf nooit een Tesla-opportunity creëren.
2. **Deadline / MUST** — bij een expliciete laadverplichting krijgt verwacht PV-overschot voorrang. Alleen de resterende noodzakelijke netenergie mag bij een DYNAMIC-contract naar de goedkoopste bruikbare slots vóór de deadline worden verschoven.

Daarmee geldt:

`cheap price != Tesla opportunity trigger`

`deadline required energy = PV first -> cheapest required grid slots`

Een eventuele toekomstige prijsarbitrage zonder deadline moet een afzonderlijke expliciete policy/intent krijgen en mag niet onder `TESLA_CHARGE_OPPORTUNITY` worden verborgen.

## 24h Energy Planner v0.4.3 SHADOW

Planner v0.4.3 draait iedere 15 minuten met 45 seconden vertraging en kan handmatig worden gestart. De bestaande flow-ID en Homey-folder zijn behouden.

De Planner genereert altijd **96 × 15-minuten-slots**, ook onder FIXED. Prijs is context, niet de eigenaar van de tijdas.

### Base-loadmodel

Planner leest `EM2_Day_History` uit de canonieke History-flow. Voor bruikbare samples geldt:

`PV_W = SolarEdge_W + GoodWe4200_W + GoodWe2000_W`

`house_W = P1_W + PV_W`

`base_W = max(0, house_W - Tesla_W - Boiler_W)`

Per lokale kwartierindex wordt een mediaanprofiel opgebouwd met globale mediaan als fallback. De Planner pollt geen apparaten opnieuw.

### Weather-aware PV forecast

De Planner gebruikt Open-Meteo `shortwave_radiation` voor locatie Hauwert en zet irradiance om naar verwacht aggregaat PV-vermogen. De schaalfactor wordt waar mogelijk gekalibreerd tegen gemeten totale PV uit `EM2_Day_History`. Bij voldoende bruikbare calibratiepunten geldt `WEATHER_HAUWERT_CALIBRATED`; anders wordt een theoretische fallback-schaal gebruikt en gemarkeerd als `WEATHER_HAUWERT_THEORETICAL_SCALE`.

De forecastmetadata bevat provider, locatie, coördinaten, variabele, 15-minutenresolutie, retrievaltijd en calibratiepunten. Er wordt geen day-persistence PV-forecast gebruikt.

### Energy-balancevelden

Per slot worden waar mogelijk gepubliceerd:

- `baseLoadForecastW`;
- `pvForecastW`;
- `netBeforeFlexW`;
- `importBeforeFlexW`;
- `pvSurplusBeforeFlexW`;
- prijs/contextclassificatie;
- forecastkwaliteit;
- Tesla-, WW- en batterijactie in SHADOW.

`netBeforeFlexW = baseLoadForecastW - pvForecastW`

Positief betekent verwachte import vóór flex-loads; negatief betekent verwacht PV-overschot. `gridHeadroomW` blijft `null` totdat fasebewuste 3×25 A headroom werkelijk is gemodelleerd.

### Tesla zonder deadline: PV-only opportunity

Als geen deadline/MUST actief is, worden alleen slots geselecteerd waarvoor:

`pvSurplusBeforeFlexW >= 800 W`

Deze krijgen `OPPORTUNITY_PV_ONLY` en worden op verwacht PV-overschot gerangschikt. Prijs beïnvloedt deze opportunityselectie niet. Geen PV-overschot >= 800 W betekent geen Tesla opportunity-slot, ook niet bij goedkope of negatieve prijzen.

### Tesla met deadline: PV eerst, daarna prijs

Bij actieve deadline met resterende kWh worden eerst slots vóór de deadline met voldoende verwacht PV-overschot gerangschikt. Daarna worden resterende noodzakelijke slots bij DYNAMIC op laagste prijs gerangschikt; bij FIXED op tijd.

De Planner publiceert hiervoor `PV_SURPLUS_THEN_CHEAPEST_REQUIRED_GRID_SLOTS`. Het echte vermogen blijft runtime EMS -> Power Intent -> EV Adapter.

### Warm water v0.4.3: elke watt PV telt

WW heeft een harde dagelijkse energiebehoefte vóór 19:00. Planner v0.4.3 corrigeert de eerdere v0.4.2-ranking waarbij alleen een slot met **volledige** 1,9 kW PV-dekking als PV-first gold. Daardoor kon bijvoorbeeld 1,8 kW verwacht PV-overschot ten onrechte in dezelfde restgroep vallen als 0 W PV en vervolgens door een goedkope netprijs worden verdrongen.

De v0.4.3-invariant is:

`PV coverage first -> remaining deadline energy second -> price only after PV preference`

Voor ieder kandidaatkwartier wordt berekend:

`pvCoverageW = min(1900 W, pvSurplusBeforeFlexW)`

`gridRequiredW = max(0, 1900 W - pvCoverageW)`

De Planner maximaliseert eerst `pvCoverageW`, dus **ook gedeeltelijke PV-dekking heeft prioriteit boven goedkope netenergie**. Alleen wanneer de PV-dekking gelijk is, mag bij DYNAMIC prijs als tie-breaker worden gebruikt. Bij FIXED bepaalt daarna tijd de volgorde.

Geselecteerde WW-slots krijgen expliciete semantiek:

- `PV_PREFERRED` — het slot bevat gehele of gedeeltelijke voorspelde PV-dekking;
- `DEADLINE_REQUIRED` — het slot is zonder PV nodig om het resterende dagdoel vóór 19:00 te halen;
- `MUST_CATCHUP` — runtime catch-up is vereist.

Daarnaast publiceert elk geselecteerd WW-slot `warmWaterReason`, `warmWaterPvCoverageW` en `warmWaterGridRequiredW`. De allocation policy is bij DYNAMIC `MAXIMIZE_PV_COVERAGE_THEN_PRICE_TIEBREAK_FOR_DEADLINE` en bij FIXED `MAXIMIZE_PV_COVERAGE_THEN_TIME_BEFORE_DEADLINE`.

Deze labels zijn planning/evidence. Ze veroorzaken geen fysieke boilerwrite; de bestaande WW-productiewriter blijft eigenaar.

### Batterij

De batterij blijft `THEORETICAL_ONLY_NO_SOC` totdat werkelijk Victron/Pylontech SOC en commissioningconstraints beschikbaar zijn.

### Plannerstatus

V0.4.3 publiceert onder meer `BLOCKED_STATE_MISSING`, `DEGRADED_BASE_LOAD_HISTORY`, `DEGRADED_PRICE_CONTEXT`, `DEGRADED_PV_WEATHER_FORECAST` en `READY_SHADOW_V0.4.3`.

## Planner publication en BC evidence

`EM v2 | 46 Publish | Planner Shadow v0.1` publiceert het volledige SHADOW-plan als observability-only envelope naar `docs/data/energy-planner-shadow.json`. De publisher accepteert v0.4.x zolang `controlMode=SHADOW`, `readOnly=true` en `physicalWritePerformed=false` blijven gelden.

De Planner Shadow UI onderscheidt vanaf frontend v109 WW-slots met `PV_PREFERRED` van `DEADLINE_REQUIRED`. Hoverdetails tonen de reden en de voorspelde PV-dekking versus benodigde netstroom, zodat een verplicht deadlineslot niet langer visueel als een PV-voorkeur wordt gepresenteerd.

`EM v2 | 76 Evidence | BC Planner Intent Recorder v0.3` legt planner- en Power-Intent-evidence vast voor de closed-loop keten:

`planned -> intent -> commanded -> actual -> financial result`

## Power Intent v0.2.1 SHADOW

Power Intent is idempotent per source revision en valideert revision alignment tussen Public State, State, Decision en WW Control. Bij mismatch is het EV-doel fail-closed 0 W.

### EV-target contract

Bij `TESLA_CHARGE_DEADLINE`, indien resterende energie en toekomstige deadline geldig zijn:

`target_W = remaining_kWh / hours_to_deadline * 1000`

Bij `TESLA_CHARGE_OPPORTUNITY` geldt uitsluitend:

- `flexExportBudgetW >= 800 W` -> `target_W = flexExportBudgetW`;
- anders -> `target_W = 0`.

Negatieve of goedkope prijs kan geen discretionary importtarget creëren voor `TESLA_CHARGE_OPPORTUNITY`. De output publiceert `teslaOpportunityPolicy=PV_SURPLUS_ONLY` en `pricePolicy=DEADLINE_OPTIMIZATION_ONLY`.

Power Intent converteert niet naar ampère; elektrische feasibility hoort bij de EV Power Adapter.

## WW-target contract

WW is nog binair: `BOILER_ON -> true`, `BOILER_OFF -> false`, `HOLD -> null`. `WW_target_W` blijft het toekomstige numerieke architectuurcontract. De nieuwe `PV_PREFERRED`/`DEADLINE_REQUIRED` Plannerlabels veranderen dit runtimecontract niet.

## EV Power Adapter v0.1 SHADOW

De EV-adapter vertaalt uitsluitend `EV_target_W` naar een theoretisch uitvoerbare Easee-opdracht. De topologie is 3 fasen × 230 V, minimaal 6 A en maximaal de geconfigureerde veilige stroom met harde bovengrens 16 A.

`theoretical_A = EV_target_W / (3 × 230)`

`requested_A = floor(theoretical_A)`

Onder 6 A wordt 0 A gevraagd. De adapter verhoogt nooit het upstream vermogensbudget en blijft fail-closed. In SHADOW blijft `commanded_A=null` en worden geen Easee-writes uitgevoerd.

## WW Power Adapter v0.1 SHADOW

De WW Power Adapter accepteert uitsluitend upstream WW-intent en introduceert geen eigen prijs-, opportunity- of deadlinepolicy. `target_on=true/false/null` wordt deterministisch vertaald naar ON/OFF/HOLD shadow command.

## Single-writer boundary

Een fysieke writer mag pas via gecontroleerde atomic cut-over worden geactiveerd nadat revision/schema alignment, freshness/fail-closed, mapping/feasibility, dedupe/idempotency en rollback zijn bewezen. Nooit mogen twee fysieke writers dezelfde actuator tegelijk sturen.

## Safety invariants

- geen device writes in Planner/Power Intent/Adapters zolang SHADOW actief is;
- Tesla opportunity is uitsluitend PV/exportbudgetgedreven;
- goedkope of negatieve prijs mag nooit zelfstandig Tesla opportunity charging starten;
- prijsoptimalisatie voor Tesla hoort alleen binnen deadline/MUST-planning;
- WW ranking maximaliseert alle voorspelde PV-dekking, inclusief gedeeltelijke dekking, vóór prijsoptimalisatie;
- WW `PV_PREFERRED`, `DEADLINE_REQUIRED` en `MUST_CATCHUP` zijn expliciet verschillende plannersemantiek;
- forecastbron en kwaliteit worden expliciet gepubliceerd;
- fasebewuste grid-headroom wordt pas gebruikt wanneer werkelijk gemodelleerd;
- adapters verhogen nooit upstream vermogensbudget;
- requested, commanded en confirmed blijven gescheiden;
- één fysieke writer per actuator na cut-over.

## Huidige status

| Onderdeel | Status |
|---|---|
| 24h Planner v0.4.3 | ACTIVE SHADOW; weather-aware Hauwert PV forecast |
| WW allocation | ACTIVE SHADOW; maximize partial/full PV coverage first |
| WW planner semantics | `PV_PREFERRED` / `DEADLINE_REQUIRED` / `MUST_CATCHUP` |
| Planner Shadow UI | v109; WW PV/deadline visually separated |
| Base-load forecast | ACTIVE SHADOW; quarter profile/global median fallback |
| PV forecast | ACTIVE SHADOW; Open-Meteo shortwave radiation + measured PV calibration |
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
| EV/WW fysieke writers via nieuwe adapterketen | NIET ACTIEF |
| Victron fysieke writer | NIET ACTIEF |

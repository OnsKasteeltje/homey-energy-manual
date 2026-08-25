---
component: price-adapter
title: Contract Price Adapter
status: implemented-shadow
last_verified: 2026-08-25
source:
  - Homey: EM v2 | 30 Context | Contract Price Adapter v0.8
  - Homey: EM v2 | 40 Decision | Contract-aware v0.2
owner: EMS
---

# Contract Price Adapter

## Doel

De Contract Price Adapter levert één uniforme prijscontext voor FIXED en DYNAMIC contracten zonder dat downstream beslislogica kennis hoeft te hebben van de ruwe bron.

## Bronwaarheid

`EMS_ContractType` is de enige autoritatieve contractinstelling en accepteert `FIXED` of `DYNAMIC`. Een ongeldige waarde valt fail-safe terug naar `FIXED`. `EM2_Contract_Type` is uitsluitend een compatibility mirror en mag niet als bronwaarheid worden gebruikt.

## FIXED

FIXED gebruikt uitsluitend de lokaal geconfigureerde waarden:
- `EM2_Fixed_Import_Normal`
- `EM2_Fixed_Import_Offpeak`
- `EM2_Fixed_Export`
- `EM2_Fixed_Offpeak_Active`

De FIXED-route doet geen PBTH-read. De contextbron is `FIXED_CONFIG`, de horizon is `STATIC` en de kwaliteit is `GOOD` zolang alle vaste tarieven geldig zijn.

## DYNAMIC

DYNAMIC haalt `prices_json(next_hours)` op via PBTH en leest daarnaast de actuele import/exportprijs. De adapter valideert de beschikbare horizon en classificeert deze als `FULL`, `INTRADAY` of `DIAGNOSTIC`.

De dynamische route berekent onder meer:
- current import/export price;
- negative-now;
- cheap/expensive-now;
- cheap/expensive-next-4h;
- min/max/avg next 4h;
- p25/p75 van de beschikbare horizon.

Legacy `M7_Price_*` signalen worden niet gebruikt.

## Uniform contract

De output is `EM2_ContractPrice_Context` met schema `EM2_UNIFORM_PRICE_CONTEXT_V0.3`. Kernvelden zijn `contractType`, `source`, `quality`, `updatedAt`, `importPriceNow`, `exportPriceNow`, `selfUseGainNow`, prijsflags en horizonstatistiek.

## Freshness

De contract-aware beslislaag accepteert prijscontext alleen wanneer:
- `updatedAt` geldig is;
- leeftijd maximaal 35 minuten is;
- `quality == GOOD`;
- horizon voor DYNAMIC bruikbaar is (`FULL` of `INTRADAY`), of `STATIC` voor FIXED.

Bij stale/degraded prijscontext blijft P1-gebaseerde opportunity-logica bruikbaar; prijsarbitrage valt fail-closed weg.

## Contract-aware Decision

`EM v2 | 40 Decision | Contract-aware v0.2` is `SHADOW_CANDIDATE` en schrijft geen actuators. De beslislaag maakt twee candidates:
- `EM2_Decision_ContractCandidate` voor Tesla;
- `EM2_Control_WW_ContractCandidate` voor warm water.

Tesla deadline/MUST blijft contractonafhankelijk. P1/flex-export opportunities blijven eveneens contractonafhankelijk. Prijscontext voegt uitsluitend opportunistische SHOULD/MAY-beslissingen toe.

Voor warm water blijven mode, dagdoel, 19:00 deadline en catch-up leidend. Prijscontext kan alleen een opportunity toevoegen wanneer importbudget en guards dat toelaten.

## Validiteitsmodel

P1/netmeting is autoritatief voor flex/export opportunities. Afgeleide PV/huisbalans is diagnostisch en mag door source-skew degraderen zonder verse P1-flex te blokkeren.

## Safety

- geen actuator-writes;
- geen legacy M7-prijsinput;
- FIXED is onafhankelijk van PBTH;
- stale prijscontext veroorzaakt geen fysieke actie;
- candidate namespace blijft geïsoleerd van productiecontrollers.

---
component: price-adapter
title: Contract Price Context
status: active
architecture_status: implemented-production
last_verified: 2026-09-13
source:
  - docs/architecture/CURRENT-EMS-STATE.md
  - Homey: EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD
  - Homey: EM v2 | 40 Decision | Contract-aware v0.2
owner: EMS
---

# Contract Price Context

## Doel

De prijscontext ondersteunt zowel vaste als dynamische prijsdata, maar de **productiepolicy is momenteel uitsluitend FIXED**. De productie-EMS is gekoppeld aan het driejarige ENGIE-contract. DYNAMIC blijft beschikbaar voor shadow, analyse en replay, niet als productie-authority.

## Productiebronwaarheid

De huidige productie-invarianten zijn:

- `productionContractMode = FIXED`;
- `productionContractId = ENGIE_3Y_2026_2029`;
- `productionSupplier = ENGIE`;
- dynamische prijssturing is uitgeschakeld voor productie;
- automatische fallback naar DYNAMIC is verboden;
- automatische contract-mode switching is verboden;
- inconsistente of ontbrekende contractconfiguratie faalt gesloten.

Daarmee is de operationele volgorde:

`contract mode -> toegestane economic model -> toegestane price source -> planner decision`

## FIXED productiepad

Onder FIXED gebruikt de EMS uitsluitend de vaste contractcontext die voor het ENGIE-contract is geconfigureerd. PBTH/dynamische marktprijzen mogen geen productieactie creëren.

Vaste prijscontext kan nog relevant zijn voor:

- financiële observability;
- rapportage;
- replay/business-case analyse;
- toekomstige policy-evaluatie buiten de actieve productiecontrol.

De productieplanner optimaliseert primair op eigen PV-gebruik, comfort/deadlineconstraints en flex-load feasibility; niet op dynamische uur- of kwartierarbitrage.

## DYNAMIC context

Dynamische prijsdata mag nog worden opgehaald en verwerkt voor:

- shadow planning;
- A/B analyse;
- replay;
- contract/business-case vergelijking.

Zolang FIXED actief is, mag DYNAMIC data niet:

- Tesla opportunity starten;
- WW productieactie veroorzaken;
- planner authority wijzigen;
- automatisch de contractmodus omschakelen;
- als fallback productieprijsbron optreden.

## Homey Contract Price Adapter

De actuele Homey adapterfamilie bevat `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`.

Het bestaan van FIXED+DYNAMIC ondersteuning in de adapter betekent **niet** dat beide modi gelijktijdig of automatisch voor productie zijn toegestaan. De bovenliggende contractpolicy bepaalt welke route bruikbaar is.

## Contract-aware Decision

`EM v2 | 40 Decision | Contract-aware v0.2` blijft een context/candidate-laag. Onder de huidige productiepolicy mag dynamische prijscontext alleen adviserend/shadow zijn.

Tesla deadline/MUST blijft contractonafhankelijk. Directe PV/opportunity-logica blijft eveneens contractonafhankelijk.

## Pi planner contractguard

De Pi `/control/current` route accepteert voor productie uitsluitend commands die voldoen aan:

- contract mode `FIXED`;
- contract id `ENGIE_3Y_2026_2029`;
- owner `PI`;
- executor `HOMEY`;
- geldige/fresh plannerstate.

Een contract mismatch faalt gesloten.

De Homey PI Bridge v1.2.6 valideert dezelfde FIXED/ENGIE metadata voordat het command naar `EM2_POWER_INTENT_V0.2` wordt geprojecteerd.

## Safety

- geen automatische FIXED→DYNAMIC fallback;
- geen automatische contract-mode switching;
- DYNAMIC prijsdata is geen productie-trigger onder FIXED;
- contract mismatch faalt gesloten;
- planner en prijsadapter schrijven geen fysieke actuators;
- P1/live netmeting blijft de relevante fysieke netwaarheid voor flex/exportgedrag.

## Documentatiedrift die hiermee is opgeheven

Het eerdere document suggereerde dat `EMS_ContractType` vrij tussen FIXED en DYNAMIC kon wisselen en dat beide routes gelijkwaardig voor downstream productie waren. Dat is niet meer de actuele production governance. Het driejarige ENGIE FIXED-contract is nu een harde productie-invariant; DYNAMIC is uitsluitend shadow/analyse/replay zolang deze contractpolicy actief is.

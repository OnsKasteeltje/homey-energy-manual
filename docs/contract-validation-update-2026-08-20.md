# Contractvalidatie en warmwaterbronkeuze — 20 augustus 2026

## Status

De twee op 20 augustus geplande, maar in de nacht niet gerealiseerde bouwstappen zijn alsnog gecontroleerd uitgevoerd.

### Contract History v0.1

Homey-flow: `EM v2 | 80 Validation | Contract History v0.1`

- draait iedere 15 minuten;
- gebruikt uitsluitend Homey Logic-variabelen;
- gebruikt geen Homey Insights;
- doet geen device-reads en geen actuatorwrites;
- publiceert rolling validatie naar `docs/data/contract-history-v01.json`;
- bewaart maximaal 672 kwartiersamples (7 dagen);
- legt contracttype, uniforme prijscontext, kandidaatbesluit, productie-uitkomst, revision-alignment en agreement vast;
- bevat ook de actuele `EM2_WW_Source_Advice` voor gezamenlijke validatie.

Runtimevalidatie: **PASS**. De eerste publicatie is succesvol aangemaakt en revision-consistent.

### WW Source Advice v0.1 SHADOW

Homey-flow: `EM v2 | 50 Decision | WW Source Advice v0.1 SHADOW`

Output: `EM2_WW_Source_Advice` (`EM2_WW_SOURCE_ADVICE_V0.1`).

De flow vergelijkt BOILER en CV in EUR per bruikbare kWh warmte:

- elektrische boiler: actuele marginale elektriciteitswaarde gedeeld door boilerrendement;
- CV: gasprijs gedeeld door bruikbare gasenergie × CV-rendement;
- bij netto export wordt voor elektriciteit de gemiste terugleverwaarde als opportunity cost gebruikt;
- bij netto import wordt de actuele importprijs gebruikt.

De bronkeuze is uitsluitend **PURE_SHADOW**. `WW_Boilermodus` blijft operationeel leidend; de flow schrijft niet naar boiler, CV, Quatt of andere apparaten.

Hysterese voorkomt omschakeladvies bij kleine kostenverschillen. Bij ontbrekende/stale prijscontext of ongeldige kosteninputs geldt fail-safe `KEEP_CURRENT`.

Configureerbare SHADOW-inputs:

- `EM2_Gas_Price_EurM3` — initieel 1.19265 EUR/m³;
- `EM2_Gas_UsableKWhPerM3` — initieel 9.77 kWh/m³;
- `EM2_CV_DHW_Efficiency` — initieel 0.90;
- `EM2_Boiler_Efficiency` — initieel 0.98;
- `EM2_WW_Source_Hysteresis_EurKWh` — initieel 0.015 EUR/kWh warmte.

Deze waarden zijn expliciete configuratieparameters en geen verborgen constanten. Rendementen en calorische waarde moeten vóór een eventuele operationele cut-over nog tegen de werkelijke installatie/gekozen rekenbasis worden bevestigd.

Runtimevalidatie: **PASS**. Bij de eerste gecontroleerde run was de uniforme prijscontext `FIXED`, kwaliteit `GOOD`. De bronselector adviseerde `CV`, terwijl de operationele productiebron `BOILER` bleef. Daarmee is bevestigd dat de selector alleen adviseert en de productie niet wijzigt.

## Veiligheidsinvarianten

1. Geen fysieke actuatorwrites vanuit beide nieuwe flows.
2. Geen extra device polling voor Contract History of WW Source Advice.
3. Contract History is onafhankelijk van Homey Insights.
4. `WW_Boilermodus` blijft leidend gedurende SHADOW-validatie.
5. Prijscontext moet vers en `GOOD` zijn; anders blijft de huidige bron gehandhaafd.
6. Een toekomstige operationele bronwissel vereist eerst voldoende rolling shadowdata en bevestiging van de kostenparameters.

## Vervolg

Laat de rolling historie voldoende FIXED- en DYNAMIC-situaties verzamelen. Beoordeel daarna agreement, economische bronkeuze, flapping/hysterese en verschillen met productie voordat `EM2_WW_Source_Advice` ooit aan een actuator- of moduswrite wordt gekoppeld.

# Warmwaterbronkeuze — Stap 2b

_Status: implementatie voorbereid, Homey-write nog geblokkeerd door rate limiting op 20 augustus 2026._

## Doel

Stap 2b voegt een geïsoleerde SHADOW-laag toe die adviseert of warm water economisch beter via de elektrische boiler of via de CV wordt gemaakt. Tijdens SHADOW blijft `WW_Boilermodus` operationeel leidend en worden geen fysieke boiler- of CV-writes uitgevoerd.

## Beslisketen

`warmwatervraag → bronkeuze BOILER/CV → indien BOILER: timing via prijs/PV/deadline → actuator`

## Kostenvergelijking

Beide bronnen worden vergeleken in EUR per bruikbare kWh warmte:

- `costBoiler = electricityMarginalEURkWh / boilerEfficiency`
- `costCV = gasEURm3 / (gasKWhPerM3 * cvEfficiency)`
- `delta = costCV - costBoiler`

Elektriciteitsmarge komt uit de uniforme `EM2_ContractPrice_*`-context. Bij directe PV-zelfconsumptie geldt de gemiste terugleverwaarde als opportunity cost; PV wordt dus niet automatisch als gratis behandeld.

## Configuratie

De selector gebruikt expliciete configuratie-inputs:

- `EM2_WW_Gas_EUR_m3`
- `EM2_WW_Gas_kWh_m3`
- `EM2_WW_CV_Efficiency`
- `EM2_WW_Boiler_Efficiency`
- `EM2_WW_Source_Hysteresis_EUR_kWh`

Ontbrekende, niet-numerieke of fysiek ongeldige waarden leiden tot `UNKNOWN` en nooit tot een bronwisseladvies.

## SHADOW-outputs

- `EM2_WW_Source_Advice`: `BOILER`, `CV`, `HOLD` of `UNKNOWN`
- `EM2_WW_Source_CostBoiler_EUR_kWh`
- `EM2_WW_Source_CostCV_EUR_kWh`
- `EM2_WW_Source_Delta_EUR_kWh`
- `EM2_WW_Source_Reason`
- `EM2_WW_Source_Status`

`EM2_WW_Source_Status` moet minimaal timestamp, contracttype, prijsbron/kwaliteit, geldigheid van de kosteninput, hysterese en `readOnly:true` bevatten.

## Hysterese / anti-flapping

- `delta > hysteresis` → `BOILER`
- `delta < -hysteresis` → `CV`
- `abs(delta) <= hysteresis` → `HOLD`
- onbruikbare brondata → `UNKNOWN`

Voor een latere operationele cut-over kan aanvullend een minimale geldigheidsduur of meerdere opeenvolgende bevestigingen worden geëist. Dat wordt in SHADOW nog niet gebruikt om `WW_Boilermodus` te wijzigen.

## Veiligheidsinvarianten

1. `WW_Boilermodus` wordt niet overschreven.
2. Geen fysieke boiler-, CV- of Quatt-write.
3. De bestaande warmwatertiming en comfort/deadline-logica blijven onaangetast.
4. Prijsdata wordt alleen uit de uniforme contractinterface gelezen.
5. Bij ontbrekende of stale prijscontext wordt geen economisch bronwisseladvies gegeven.
6. Alle outputs zijn observatie-/validatiedata.

## Uitvoeringsstatus 20 augustus 2026

Twee gecontroleerde reads van `EM v2 | 40 Decision | Contract-aware v0.1` (flow-id `56b87a5c-645c-4a95-9744-880c4d0353bd`) zijn door Homey afgewezen met `Too many requests`. Conform de veiligheidsafspraak is daarna geen update- of start-call geforceerd.

Daarom zijn in deze run **geen Homey-writes uitgevoerd** en konden `enabled`/`broken` en de nieuwe outputwaarden niet opnieuw worden gevalideerd. De bestaande flow/configuratie is ongemoeid gelaten. Zodra Homey weer reads/writes accepteert, kan deze specificatie rechtstreeks als SHADOW-uitbreiding worden geïmplementeerd zonder ontwerpbeslissing opnieuw te openen.

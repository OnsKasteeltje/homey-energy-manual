# Wasmachine & droger — automatisch P1-model

## Doel

De wasmachine en droger leveren in Homey wel programma-/apparaatstatus, maar geen afzonderlijk actueel vermogen. Daarom wordt hun elektrische bijdrage niet als echte apparaatmeting gepresenteerd. In plaats daarvan leert een apart P1-model het typische overgangsvermogen van beide apparaten uit geïsoleerde start/stop-overgangen.

## Architectuur

- `Energie | Wasmachine & Droger analyse | v1.3.0` is de leerlaag.
- Het model wordt gedeeld opgeslagen in Homey Logic als `LAUNDRY_ENERGY_MODEL_JSON`; de laatste analyse-sample staat in `LAUNDRY_ENERGY_LAST_SAMPLE_JSON`.
- Statuswissels van wasmachine/droger worden event-first bemonsterd. De periodieke 5-minutenroute gebruikt `EM2_State` en doet geen extra `getDevices()`.
- Alleen geïsoleerde overgangen worden als bewijs gebruikt. Grote gelijktijdige veranderingen in PV, Tesla, boiler of Quatt worden gefilterd.
- Het model bepaalt per apparaat dominante fase, typisch overgangsvermogen, aantal bewijsmetingen, faseconsistentie en confidence.
- Voor de wasmachine bestaat daarnaast een browser-side fingerprintfallback. Een sterke sequentiële P1-fingerprint kan een foutieve AEG `Idle`-status degraderen tot inconsistent en de status als **waarschijnlijk actief** tonen. Als de fase-reconstructie tijdelijk onbruikbaar is, kan een tweede fail-safe alleen bij een geldige woningbalans, een persistente niet-toegewezen belasting van 0,9–2,9 kW en afwezigheid van Tesla, droger, Quooker en actieve ruimteverwarming dezelfde inferred-status zetten.

## Confidence en veiligheidsregels

- `NONE`: geen bruikbaar bewijs.
- `LOW`: eerste bewijs, nog niet geschikt voor Live Stroom.
- `MEDIUM`: minimaal 2 bewijsmetingen en voldoende faseconsistentie.
- `HIGH`: minimaal 4 bewijsmetingen en hoge faseconsistentie.
- Een geschat vermogen wordt alleen gepubliceerd bij `MEDIUM` of `HIGH` én boven de algemene actieve-verbruiksdrempel van 20 W.
- Bij onvoldoende bewijs blijft `power_w = null` als het apparaat actief is. De UI toont dan `—` en laat het verbruik onderdeel van `Overig` blijven.
- Een inferred actieve status uit de fingerprintfallback krijgt nooit automatisch een verzonnen wattage; het verbruik blijft dus in `Overig` totdat een voldoende betrouwbare vermogensschatting beschikbaar is.
- De persistente residual-fallback vereist minimaal twee samples over ten minste vier minuten en wordt uitgeschakeld zodra de afgeleide woningbalans ongeldig is.

## Publicatie en Live Stroom

`Energie | Wasmachine & Droger publicatie | v1.1.1` leest uitsluitend het gedeelde Logic-model en `EM2_State` en publiceert iedere 5 minuten `data/laundry-analysis.json`. Hiervoor worden geen extra apparaten gepolld.

De browser-overlay `live-energy-laundry-model-v2.8.118.js` voegt verse, voldoende betrouwbare schattingen samen met de bestaande Energy Core-state en bevat de conflict/fallbacklogica voor de wasmachine. `live-energy-appliance-state-v2.8.97.js` vertaalt de resulterende status naar de Live Stream.

Wanneer een betrouwbare vermogensschatting beschikbaar is, trekt de bestaande Live Stroom-renderer dit vermogen af van `Overig`. Daarmee blijft de woningbalans intact en ontstaat geen dubbeltelling. Een alleen inferred actieve status verandert de wattageverdeling niet.

## Fail-safe gedrag

Ontbrekende, oude of onvoldoende betrouwbare modeldata wordt nooit als wattage gebruikt. De Energy Core-hoofdstream blijft leidend, behalve wanneer de directe AEG-status aantoonbaar conflicteert met voldoende sterke elektrische evidence. In dat geval wordt uitsluitend de status naar `WAARSCHIJNLIJK_ACTIEF` verheven; de bron, conflictstatus, methode en confidence worden expliciet in `raw.meta.laundry_fingerprint_fallback` vastgelegd.

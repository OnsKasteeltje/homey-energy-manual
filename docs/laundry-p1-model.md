# Wasmachine & droger — automatisch P1-model

## Doel

De wasmachine en droger leveren in Homey wel programma-/apparaatstatus, maar geen afzonderlijk actueel vermogen. Daarom wordt hun elektrische bijdrage niet als echte apparaatmeting gepresenteerd. In plaats daarvan leert een apart P1-model het typische overgangsvermogen van beide apparaten uit geïsoleerde start/stop-overgangen.

## Architectuur

- `Energie | Wasmachine & Droger analyse | v1.3.0` is de leerlaag.
- Het model wordt gedeeld opgeslagen in Homey Logic als `LAUNDRY_ENERGY_MODEL_JSON`; de laatste analyse-sample staat in `LAUNDRY_ENERGY_LAST_SAMPLE_JSON`.
- Statuswissels van wasmachine/droger worden event-first bemonsterd. De periodieke 5-minutenroute gebruikt `EM2_State` en doet geen extra `getDevices()`.
- Alleen geïsoleerde overgangen worden als bewijs gebruikt. Grote gelijktijdige veranderingen in PV, Tesla, boiler of Quatt worden gefilterd.
- Het model bepaalt per apparaat dominante fase, typisch overgangsvermogen, aantal bewijsmetingen, faseconsistentie en confidence.

## Confidence en veiligheidsregels

- `NONE`: geen bruikbaar bewijs.
- `LOW`: eerste bewijs, nog niet geschikt voor Live Stroom.
- `MEDIUM`: minimaal 2 bewijsmetingen en voldoende faseconsistentie.
- `HIGH`: minimaal 4 bewijsmetingen en hoge faseconsistentie.
- Een geschat vermogen wordt alleen gepubliceerd bij `MEDIUM` of `HIGH` én boven de algemene actieve-verbruiksdrempel van 20 W.
- Bij onvoldoende bewijs blijft `power_w = null` als het apparaat actief is. De UI toont dan `—` en laat het verbruik onderdeel van `Overig` blijven.

## Publicatie en Live Stroom

`Energie | Wasmachine & Droger publicatie | v1.1.1` leest uitsluitend het gedeelde Logic-model en `EM2_State` en publiceert iedere 5 minuten `data/laundry-analysis.json`. Hiervoor worden geen extra apparaten gepolld.

De browser-overlay `live-energy-laundry-model-v2.8.70.js` voegt alleen verse, voldoende betrouwbare schattingen samen met de bestaande Energy Core-state. `live-energy-appliance-state-v2.8.71.js` markeert zo'n waarde zichtbaar als **geschat** en vermeldt de betrouwbaarheid. Hierdoor kan een P1-afleiding niet worden verward met een echte apparaatmeter.

Wanneer een betrouwbare schatting beschikbaar is, trekt de bestaande Live Stroom-renderer dit vermogen af van `Overig`. Daarmee blijft de woningbalans intact en ontstaat geen dubbeltelling.

## Fail-safe gedrag

Ontbrekende, oude of onvoldoende betrouwbare modeldata wordt nooit als wattage gebruikt. De Energy Core-hoofdstream blijft leidend voor de actuele apparaatstatus. De P1-modeloverlay mag uitsluitend vermogen toevoegen; hij mag een actuele Homey-status niet zelfstandig op actief zetten.

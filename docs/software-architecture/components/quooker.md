---
component: quooker
title: Quooker Detector
version: 0.5
status: active
architecture_status: implemented
last_verified: 2026-10-03
source:
  - Canonical runtime source: apps/homey/observability/quooker/quooker-detector-v0.5.live-homey.js
  - Pure classifier: apps/homey/observability/quooker/quooker-detector-v0.5.mjs
  - Replay tests: tests/replay/quooker-detector-v0.5.test.mjs
  - Homey Advanced Flow: EM v2 | 01 Quooker Detector | v0.5 LIVE OBSERVE-ONLY
  - Homey Flow ID: 939a347f-0b19-4c3d-98d3-77faa01fce0b
owner: EMS
---

# Quooker Detector

## 1. Doel

De Quooker-detector classificeert de operationele toestand van de Quooker zonder fysieke aansturing. De Cooker-switch blijft autoritatief voor OFF/ON; P1-fasevermogen wordt uitsluitend gebruikt om een verwarmingspuls te herkennen en het momentane Quooker-vermogen te schatten.

De detector publiceert alleen afgeleide toestand en diagnostiek naar Homey Logic. De aparte flow `EM v2 | 60 Actuator | Quooker v0.2 LIVE` blijft de enige fysieke Quooker-writer.

## 2. Actieve runtime

- Flow: `EM v2 | 01 Quooker Detector | v0.5 LIVE OBSERVE-ONLY`
- Flow ID: `939a347f-0b19-4c3d-98d3-77faa01fce0b`
- status: enabled, not broken
- v0.4 Flow ID `e291cf14-0b92-4cef-ae8b-a699692b6c9a`: disabled rollback
- cadence: elke 15 seconden plus Cooker ON/OFF triggers
- physical writes: geen

De cutover is uitgevoerd met v0.4 eerst uit en daarna v0.5 aan. Er is daardoor maximaal één actieve detectorversie.

## 3. Waarom v0.5 nodig was

Op 2026-10-03 bleek v0.4 onvoldoende onderscheidend omdat alleen L3 werd beoordeeld. Rond 13:17 lokaal veroorzaakte een EV-herstart een stap van ongeveer +1,6 kW op alle drie fasen; die mag geen Quooker worden. Rond 13:24 lokaal trad een korte stap van ongeveer +1,64 kW vrijwel uitsluitend op L3 op; die past wel bij de Quooker.

De replaytests modelleren deze vastgestelde signatures; de fixtures worden niet als exacte ruwe samples gepresenteerd.

## 4. Heating signature v0.5

Startcriteria:

```text
1300 W <= deltaL3W <= 1900 W
abs(deltaL1W) <= 350 W
abs(deltaL2W) <= 350 W
```

Holdcriteria:

```text
1100 W <= deltaL3W <= 2050 W
abs(deltaL1W) <= 500 W
abs(deltaL2W) <= 500 W
```

Een L3-signature die tegelijk een grote beweging op L1 of L2 heeft wordt afgewezen met `REJECT_SIDE_PHASE_MOVEMENT`.

## 5. 90-seconden fail-safe

Een HEATING-classificatie mag maximaal 90 seconden actief blijven. Daarna volgt `HEATING -> ON_IDLE` met reden `HEATING_MAX_DURATION_FAILSAFE`; de actuele drie fasen worden dan de nieuwe baseline. Dit is alleen detector-safety en stuurt de fysieke Quooker niet uit.

## 6. Baselinegedrag

- OFF + verse P1-sample: L1/L2/L3 worden baseline;
- OFF zonder nieuwe P1-sample: bestaande baseline blijft behouden;
- ON_IDLE: baseline volgt de actuele drie-fasenachtergrond;
- HEATING: baseline blijft bevroren;
- einde HEATING of 90 s fail-safe: actuele drie fasen worden nieuwe baseline;
- migratie v0.4 -> v0.5: ontbrekende L1/L2-baselines worden bij de eerste geldige ON-sample geïnitialiseerd zonder direct HEATING te classificeren.

De publieke `EM_Quooker_Baseline_L3_W` blijft voor Core-compatibiliteit bestaan. L1/L2-baselines leven in `EM_Quooker_Diagnostic`.

## 7. Homey API/load

v0.5 gebruikt geen `Homey.logic.getVariables()` en geen `Homey.devices.getDevices()`. Per run gebruikt hij één targeted Cooker-read en één targeted Diagnostic Logic-read. P1 wordt gericht gelezen zolang Cooker ON is, bij switchtransitie, ontbrekende baseline of wanneer de OFF-baseline ouder is dan circa 55 seconden. Logic-writes zijn targeted.

## 8. Publiek Logic-contract

```text
EM_Quooker_Switch_On
EM_Quooker_Active
EM_Quooker_Power_W
EM_Quooker_Status
EM_Quooker_Last_Sample
EM_Quooker_Baseline_L3_W
EM_Quooker_Last_Transition
EM_Quooker_Transition_History
EM_Quooker_Last_Heating_At
EM_Quooker_Last_Heating_Power_W
EM_Quooker_Diagnostic
```

Primaire statussen zijn `OFF`, `ON_IDLE` en `HEATING`.

## 9. Safety-invarianten

1. Cooker switch is autoritatief voor OFF/ON.
2. HEATING vereist een geïsoleerde L3-stap.
3. Grote L1/L2-bewegingen worden afgewezen.
4. HEATING heeft een harde maximale duur van 90 s.
5. Geen brede Logic- of device-collection reads.
6. Geen fysieke Quooker-write.
7. De Quooker-actuator blijft sole physical writer.
8. Maximaal één detectorversie is enabled.

## 10. Validatie

Voor promotie zijn op de Pi negen Node-regressietests uitgevoerd: 9/9 PASS. De Homey v0.5-source is vóór cutover exact tegen GitHub teruggelezen. v0.4 is daarna disabled en v0.5 enabled; beide flows waren bij read-back `broken=false`.

## 11. Rollback

v0.4 blijft disabled rollback: `e291cf14-0b92-4cef-ae8b-a699692b6c9a`. Rollback vereist eerst v0.5 uit en daarna v0.4 aan.

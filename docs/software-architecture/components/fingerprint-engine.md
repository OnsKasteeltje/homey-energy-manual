---
component: fingerprint-engine
title: Fingerprint Engine
version: 0.1
status: active
architecture_status: implemented_partial
last_verified: 2026-08-25
source:
  - Homey: EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING
  - Homey: EM v2 | 01a Quooker | P1 Event Heartbeat v0.2
  - Homey: Energie | Wasmachine & Droger analyse | v1.4.2
  - Homey: EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)
owner: EMS
---

# Fingerprint Engine

## 1. Doel

De Fingerprint Engine vormt de herkenningslaag voor huishoudelijke verbruikers die niet allemaal een directe, betrouwbare vermogensmeting beschikbaar stellen. De engine combineert waar mogelijk autoritatieve apparaatstatus, P1-faseveranderingen, bekende lasten en gevalideerde ground-truth gebeurtenissen.

De architectuur maakt expliciet onderscheid tussen een echte runtime-detector en een alleen gevalideerde fingerprint-dataset. Een apparaat mag pas als productiedetector worden beschreven wanneer er actieve runtime-logica bestaat die status of vermogen publiceert.

## 2. Maturity-model

| Niveau | Betekenis | Gebruik |
| --- | --- | --- |
| M0 — Ground truth | Alleen handmatig gemarkeerde gebeurtenissen | datasetopbouw |
| M1 — Fingerprint candidate | Herhaalbaar patroon gevonden | analyse, niet publiceren als waarheid |
| M2 — Validated fingerprint | Meerdere ground-truth events ondersteunen dezelfde signatuur | website/SHADOW-herkenning toegestaan |
| M3 — Runtime detector | Actieve Homey-logica publiceert status/vermogen | productiestatus toegestaan |
| M4 — Control-grade | Detector is robuust genoeg voor fysieke regelbeslissingen | alleen na aparte safety-validatie |

Huidige classificatie:

- Quooker: M3 Runtime detector.
- Wasmachine: M3 voor statusbron; P1-energiemodel aanvullend en confidence-gated.
- Droger: M3 voor statusbron; P1-energiemodel aanvullend en confidence-gated.
- Waterkoker: M2 validated fingerprint; geen zelfstandige runtime-detectorflow vastgesteld.
- Vaatwasser: M2 validated fingerprint; geen zelfstandige runtime-detectorflow vastgesteld.
- ATAG/Bertazzoni oven: M1/M2 dataset/fingerprint, afhankelijk van herkenningsdoel; geen zelfstandige runtime-detectorflow vastgesteld.

## 3. Bronstrategie

De engine hanteert bronprioriteit:

1. autoritatieve device-state indien beschikbaar;
2. directe device-meting;
3. event-assisted P1-fingerprint;
4. geïsoleerde P1-fasetransitie;
5. algemene heuristiek/dataset-match.

Een zwakkere bron mag een sterkere autoritatieve bron niet overschrijven.

## 4. Quooker

De Quooker-detector gebruikt de Cooker `onoff`-status als autoritatieve ON/OFF-bron. P1/L3 wordt uitsluitend gebruikt als heating-assist en vermogensschatting. De P1 Event Heartbeat zet slechts `EM_Quooker_P1_Event_Seen=true`; de detector leest P1 alleen wanneer dat event is gezien.

Statusmodel:

- `OFF`
- `ON_IDLE`
- `HEATING`

De huidige heating-signatuur is een L3-delta van 1400–1750 W ten opzichte van een alleen-in-OFF geleerde baseline. Core accepteert detectorstate alleen wanneer de laatste sample vers genoeg is.

## 5. Wasmachine en droger

`Energie | Wasmachine & Droger analyse | v1.4.2` gebruikt event-first Homey-status en een gedeeld P1-fasemodel.

Autoritatieve runtime-status komt uit AEG-signalen:

- `measure_applianceState`
- `measure_cyclePhase`
- `measure_timeToEnd`
- `measure_connectionState`

Voor de droger geldt een expliciete normalisatie: `ANTICREASE` met 0 minuten resterend telt als gereed/inactief, ook wanneer `applianceState` nog `RUNNING` meldt.

Het P1-model leert alleen uit geïsoleerde ON/OFF-overgangen. Een transition wordt verworpen wanneer:

- wasmachine en droger tegelijk toggelen;
- tijd tussen samples > 8 minuten is;
- bekende Tesla/boiler/Quatt/PV-verandering samen > 450 W is;
- beste fase-delta < 40 W of > 3500 W is;
- faseselectie onvoldoende onderscheidend is.

Per apparaat worden maximaal 30 evidence-events bewaard. De dominante fase, mediane transition-wattage en faseconsistentie bepalen confidence:

- `NONE`: geen evidence;
- `LOW`: onvoldoende bewijs;
- `MEDIUM`: minimaal 2 events en faseconsistentie >= 0,67;
- `HIGH`: minimaal 4 events en faseconsistentie >= 0,75.

Live geschat wattage mag alleen gebruikt worden vanaf `MEDIUM` of `HIGH` confidence. De output moet herkenbaar blijven als `P1_TRANSITION_MODEL` en mag niet als directe apparaatmeting worden gepresenteerd.

## 6. Dataset-only fingerprints

Waterkoker, vaatwasser en ovens hebben gevalideerde ground-truth/fingerprintmomenten, maar zijn niet aangetroffen als zelfstandige actieve Homey-runtime-detectors. Hun huidige rol is daarom analyse/websiteherkenning en niet control-grade statusbron.

Deze scheiding voorkomt dat documentatie een historische fingerprint verwart met een live detector.

## 7. Confidence-contract

Iedere toekomstige generieke detector hoort minimaal te publiceren:

- `appliance`
- `status`
- `active`
- `estimated_power_W`
- `source`
- `confidence`
- `last_sample_at`
- `evidence_count`
- `model_version`
- `control_eligible`

`control_eligible` staat standaard op `false` voor fingerprint-gebaseerde detectie, tenzij daarvoor afzonderlijk safety-validatie is uitgevoerd.

## 8. Isolatie van bekende lasten

P1-fingerprint-learning moet bekende grote lasten uitfilteren. Minimaal worden Tesla, boiler, Quatt en PV als bekende context meegenomen. Quooker-heating wordt door Core eveneens als bekende gemeten last behandeld zodra de detector vers en actief is.

Doel: een verandering in een bekende last mag niet als nieuwe appliance-fingerprint worden geleerd.

## 9. Idempotency

Een detector mag dezelfde source-event/revision niet meerdere keren als nieuw evidence-event opslaan. Evidence-lijsten zijn begrensd. Statuspublicatie mag geen fysieke writes veroorzaken.

## 10. Safety

Fingerprint-detectie is observatie, geen actuator. Een detector mag nooit rechtstreeks een apparaat schakelen. Een toekomstig control-pad moet via een aparte decision- en actuatorlaag lopen met freshness-, confidence-, revision- en single-writer-guards.

## 11. Validatie

Een fingerprint promoveert pas naar een hoger maturity-niveau wanneer:

1. ground-truth events reproduceerbaar zijn;
2. false positives over representatieve perioden zijn beoordeeld;
3. bekende-load interferentie is getest;
4. freshness en stale gedrag bekend zijn;
5. confidence-regels expliciet zijn;
6. websiteweergave onderscheid maakt tussen direct gemeten en geschat vermogen.

## 12. Open punten

- Waterkoker naar een echte event-assisted runtime-detector brengen.
- Vaatwasser runtime-detector formaliseren.
- Oven-fingerprints per apparaat scheiden en confidence kwantificeren.
- Een generiek `EM2_Appliance_Detections` contract invoeren zodat website en Core niet per detector eigen variabelen hoeven te interpreteren.

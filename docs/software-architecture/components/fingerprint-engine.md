---
component: fingerprint-engine
title: Fingerprint Engine
version: 0.2
status: active
architecture_status: diagnostics_only
last_verified: 2026-08-29
source:
  - Homey: EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING
  - Homey: EM v2 | 01a Quooker | P1 Event Heartbeat v0.2
  - Homey: Energie | Wasmachine & Droger analyse | v1.4.2
  - Homey: EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)
owner: EMS
---

# Fingerprint Engine

## 1. Doel

De Fingerprint Engine is vanaf 2026-08-29 geen reguliere Live Energy-attributielaag meer. Fingerprints worden uitsluitend gebruikt voor diagnostiek, analyse, incidentele validatie en datasetopbouw voor huishoudelijke verbruikers die niet rechtstreeks meetbaar zijn.

De reguliere Live Energy View volgt de **direct-first attribution rule**: een apparaat krijgt alleen een eigen live component wanneer direct vermogen of een betrouwbare directe apparaatstatus beschikbaar is. Fingerprint-only loads vallen qua vermogen onder `Overige`.

## 2. Maturity-model

| Niveau | Betekenis | Gebruik |
| --- | --- | --- |
| M0 — Ground truth | Alleen handmatig gemarkeerde gebeurtenissen | datasetopbouw |
| M1 — Fingerprint candidate | Herhaalbaar patroon gevonden | analyse |
| M2 — Validated fingerprint | Meerdere ground-truth events ondersteunen dezelfde signatuur | diagnose/SHADOW-validatie |
| M3 — Runtime detector | Actieve logica kan status/vermogen afleiden | alleen gebruiken wanneer daar buiten Live View expliciet behoefte aan is |
| M4 — Control-grade | Detector is robuust genoeg voor fysieke regelbeslissingen | alleen na aparte safety-validatie |

Huidige classificatie:

- Quooker: directe `onoff`-status beschikbaar; status mag daarom direct worden gebruikt. P1-heating fingerprint blijft diagnostisch.
- Wasmachine: directe AEG-status beschikbaar; deze status mag rechtstreeks worden gebruikt. P1-energiemodel is niet meer nodig voor reguliere live wattage-attributie.
- Droger: directe AEG-status beschikbaar; deze status mag rechtstreeks worden gebruikt. P1-energiemodel is niet meer nodig voor reguliere live wattage-attributie.
- Waterkoker: M2 validated fingerprint; geen eigen reguliere Live Energy-attributie.
- Vaatwasser: M2 validated fingerprint; geen eigen reguliere Live Energy-attributie.
- ATAG/Bertazzoni oven: M1/M2 dataset/fingerprint; geen eigen reguliere Live Energy-attributie.

## 3. Bronstrategie voor Live Energy

De reguliere live bronprioriteit is:

1. directe device-vermogensmeting;
2. betrouwbare directe device-state voor actief/inactief;
3. anders geen individuele live attributie en vermogen onder `Overige`.

Een status-only device krijgt geen geschat wattage. P1-fingerprint-, fasetransitie- of heuristische schattingen worden niet gebruikt om de reguliere Live Energy View verder uit te splitsen.

## 4. Quooker

De Cooker `onoff`-status is de autoritatieve ON/OFF-bron. Deze directe status kan als live status worden gebruikt. De bestaande P1/L3 heating-assist en baseline/fingerprintlogica is diagnostisch en hoeft niet continu actief te zijn voor de Live Energy View.

Historisch statusmodel:

- `OFF`
- `ON_IDLE`
- `HEATING`

De heating-signatuur en heartbeat blijven bruikbaar voor incidentanalyse of gerichte validatie, maar mogen niet als reden dienen om een continue fingerprint-runtimebelasting te behouden wanneer direct statusgebruik volstaat.

## 5. Wasmachine en droger

Autoritatieve runtime-status komt rechtstreeks uit AEG-signalen:

- `measure_applianceState`
- `measure_cyclePhase`
- `measure_timeToEnd`
- `measure_connectionState`

Voor de droger blijft de normalisatie gelden dat `ANTICREASE` met 0 minuten resterend als gereed/inactief telt, ook wanneer `applianceState` nog `RUNNING` meldt.

De historische `Energie | Wasmachine & Droger analyse | v1.4.2` leerde P1-fasemodellen en geschatte transition-wattages. Deze flow staat tijdens de throttling-baseline uit en is voor de reguliere Live Energy View functioneel overbodig geworden. Als het model later opnieuw voor analyse wordt gebruikt, gebeurt dat expliciet en tijdelijk; niet als permanente live-attributielaag.

## 6. Dataset-only fingerprints

Waterkoker, vaatwasser en ovens blijven bruikbare ground-truth/fingerprintdatasets. Hun rol is diagnose en analyse. Zolang geen directe meet- of betrouwbare statusbron beschikbaar is, wordt hun vermogen niet afzonderlijk uit `Overige` gehaald.

## 7. Confidence-contract voor diagnostiek

Wanneer fingerprintanalyse tijdelijk wordt uitgevoerd, hoort de output minimaal te publiceren:

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

`control_eligible` staat standaard op `false`. Diagnostische output wordt niet gebruikt voor reguliere live vermogensallocatie.

## 8. Isolatie van bekende lasten

Bij tijdelijke P1-fingerprint-learning moeten bekende grote lasten nog steeds worden uitgefilterd. Minimaal Tesla, boiler, Quatt en PV worden als bekende context meegenomen. Dit is een analyse-eis en geen reden om de fingerprint-engine permanent te laten draaien.

## 9. Idempotency en load-governance

Een detector mag dezelfde source-event/revision niet meerdere keren als nieuw evidence-event opslaan. Evidence-lijsten zijn begrensd. Statuspublicatie mag geen fysieke writes veroorzaken.

Fingerprintflows hebben vanaf 2026-08-29 een **opt-in diagnostics lifecycle**: standaard uit wanneer directe meting/status of `Overige` voldoende is. Een tijdelijke heractivatie wordt in de Homey API/Load Map opgenomen en na de validatie weer uitgezet.

## 10. Safety

Fingerprint-detectie is observatie, geen actuator. Een detector mag nooit rechtstreeks een apparaat schakelen. Een toekomstig control-pad vereist een aparte decision- en actuatorlaag met freshness-, confidence-, revision- en single-writer-guards.

## 11. Validatie

Een fingerprint kan voor diagnose alleen worden vertrouwd wanneer:

1. ground-truth events reproduceerbaar zijn;
2. false positives over representatieve perioden zijn beoordeeld;
3. bekende-load interferentie is getest;
4. freshness en stale gedrag bekend zijn;
5. confidence-regels expliciet zijn.

Dit verleent geen recht op reguliere Live Energy-attributie; daarvoor blijft een directe meet- of statusbron vereist.

## 12. Besluit 2026-08-29

De eerdere roadmap om waterkoker, vaatwasser en oven-fingerprints door te promoveren naar permanente runtime-detectors voor de website is vervallen. Nieuwe prioriteit is eenvoud en Homey-loadreductie: direct meetbare/statusbare apparaten afzonderlijk; alle overige energie onder `Overige`; fingerprints alleen op aanvraag voor analyse.

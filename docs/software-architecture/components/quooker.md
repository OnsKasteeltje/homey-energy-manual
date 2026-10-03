---
component: quooker
title: Quooker Detector
version: 0.4
status: active
architecture_status: implemented
last_verified: 2026-10-03
source:
  - Canonical source: src/homey/observability/quooker/quooker-detector-v0.4.live-homey.js
  - Pure classifier: src/homey/observability/quooker/quooker-detector-v0.4.mjs
  - Homey Advanced Flow: EM v2 | 01 Quooker Detector | v0.4 LIVE OBSERVE-ONLY (`e291cf14-0b92-4cef-ae8b-a699692b6c9a`)
  - Homey Advanced Flow: EM v2 | 00 Core Tick | v0.11p PINNED SOURCE
owner: EMS
---

# Quooker Detector

## 1. Doel

De Quooker-detector classificeert de operationele toestand van de Quooker zonder een extra volledige Homey device-snapshot te introduceren.

De architectuur gebruikt twee verschillende bronnen met expliciete verantwoordelijkheden:

- de Homey `onoff` capability van de Cooker-switch is autoritatief voor aan/uit;
- P1 fase L3 wordt alleen gebruikt om te bepalen of de Quooker op dat moment daadwerkelijk verwarmt en om het geschatte Quooker-vermogen af te leiden.

De detector stuurt de Quooker niet aan. Hij publiceert uitsluitend afgeleide toestand en diagnostiek naar Homey Logic, waarna Core deze informatie in dezelfde centrale EMS-state opneemt.

## 2. Runtime en 2026-10-03 herstel

Op 2026-10-03 bleek de detector uit de Homey-runtime verdwenen te zijn. Alleen de Quooker Adapter en LIVE Actuator waren nog aanwezig. Daardoor bleven de legacy detectorvariabelen, waaronder `EM_Quooker_Power_W`, stale/0 terwijl de fysieke Quooker aantoonbaar verwarmde.

De gemeten testcase van 2026-10-03:

```text
10:11:00 lokaal  target ON / Cooker ON
10:11:05         P1 L3 ≈ -1290 W
10:11:10         P1 L3 ≈  +346 W
delta            ≈ +1636 W
```

Dit bevestigt de bestaande ~1.58–1.65 kW heating signature.

v0.4 herstelt de detector als aparte observe-only flow. De flow draait elke 15 seconden en wordt daarnaast direct getriggerd bij Cooker ON/OFF. Terwijl de Cooker ON is wordt P1 L3 elke run gericht gelezen; terwijl de Cooker OFF is wordt de L3-baseline maximaal eenmaal per ~55 seconden ververst.

## 3. Architectuurregel: geen volledige device-snapshot

De detector gebruikt geen `Homey.devices.getDevices()`.

Per run leest hij de Cooker gericht. P1 L3 wordt alleen aanvullend gericht gelezen wanneer dat nodig is:

```text
Cooker ON                    = Cooker + P1 L3
Cooker switchtransitie       = Cooker + P1 L3
baseline ontbreekt           = Cooker + P1 L3
Cooker OFF, baseline <55 s   = alleen Cooker
Cooker OFF, baseline >=55 s  = Cooker + P1 L3
full device snapshot         = nooit
```

Dit houdt de detector responsief tijdens ON/heating en lichtgewicht tijdens OFF.

## 4. Autoritatieve ON/OFF-bron

De Cooker-switch is leidend:

```text
cookerOn = Homey Cooker onoff
```

Daaruit volgt direct:

| Switch | Mogelijke detectorstatus |
|---|---|
| OFF | `OFF` |
| ON | `ON_IDLE` of `HEATING` |

P1/L3 mag de switchstatus niet overrulen.

Daarom kan een P1-piek nooit zelfstandig de status `HEATING` geven wanneer de Cooker-switch uit staat.

## 5. P1/L3 heating signature v0.4

Wanneer de switch aan staat leest de detector iedere 15-secondenrun gericht `measure_power.l3`.

De v0.4 signature gebruikt start- en hold-hysterese:

```text
START_MIN_W = 1300 W
START_MAX_W = 1900 W
HOLD_MIN_W  = 1100 W
HOLD_MAX_W  = 2050 W
```

Met:

```text
deltaW = L3_W - baseline_L3_W
```

De baseline wordt nooit door een actieve heating-puls heen geleerd.

Heating start wanneer:

```text
1300 W <= deltaW <= 1900 W
```

Een eenmaal actieve heating-puls blijft geldig zolang:

```text
1100 W <= deltaW <= 2050 W
```

De bredere hold-band voorkomt klapperen door PV-rampen terwijl het element aantoonbaar actief is.

Bij een geldige heating signature wordt:

```text
status  = HEATING
active  = true
powerW  = round(deltaW)
```

Wanneer de switch aan staat maar de signature niet actief is:

```text
status  = ON_IDLE
active  = false
powerW  = 0
```

## 6. Baseline-learning v0.4

De baseline is nu bewust kortlopend:

- bij Cooker OFF wordt de meest recente L3-achtergrond als baseline vastgelegd;
- bij OFF→ON blijft die laatste niet-heating baseline behouden zodat een direct inschakelend element niet zijn eigen baseline wordt;
- bij Cooker ON + ON_IDLE volgt de baseline de actuele L3-achtergrond;
- tijdens HEATING blijft de baseline bevroren;
- zodra HEATING stopt wordt de actuele L3-waarde de nieuwe ON_IDLE-baseline.

Hierdoor volgt de detector PV-rampen en andere L3-belastingen beter dan de oude langzame EWMA-baseline.

## 7. Sampling v0.4

De aparte P1-heartbeat is niet meer nodig. Eén Advanced Flow heeft drie entry-paden:

- elke 15 seconden;
- Cooker ON;
- Cooker OFF.

De HomeyScript leest altijd de Cooker gericht. P1 L3 wordt gericht gelezen wanneer de Cooker ON is, bij een switchtransitie, bij ontbrekende baseline of wanneer de OFF-baseline ouder is dan ~55 seconden. Er wordt nooit `Homey.devices.getDevices()` gebruikt.

## 8. Gepubliceerde Logic-state

De detector onderhoudt onder andere:

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

De primaire statuswaarden zijn:

```text
OFF
ON_IDLE
HEATING
```

## 9. Transitiehistorie

Bij iedere statuswijziging wordt een transition-record opgeslagen met onder andere:

```text
at
from
to
switchOn
l3W
deltaW
powerW
```

De detector bewaart maximaal acht recente transitions in `EM_Quooker_Transition_History`.

Dit is bedoeld voor runtime-diagnostiek en fingerprintvalidatie, niet als lange-termijn historieopslag.

## 10. Integratie in Core

Core v0.10.13 leest de detectoroutputs uit dezelfde Logic-snapshot als de overige EMS-variabelen.

Core beschouwt Quooker-data als vers wanneer:

```text
age(EM_Quooker_Last_Sample) <= 150 s
```

Bij stale detectorstate publiceert Core de Quooker niet als actief.

Core neemt onder andere over:

```text
active
switchOn
powerW
status
fresh
lastSample
baselineL3W
lastTransition
lastHeatingAt
lastHeatingPowerW
transitionHistory
```

De Core-publicatie markeert de bron expliciet als:

```text
source   = HOMEY_SWITCH_PLUS_P1_L3
inferred = true
```

## 11. Energie-balans

Wanneer de Quooker als `HEATING` is geclassificeerd, wordt het geschatte Quooker-vermogen toegevoegd aan de bekende gemeten loads in Core:

```text
knownMeasuredLoadW
  = Tesla
  + Boiler
  + Quatt
  + Quooker
```

Daarmee wordt het residual/`Overig`-vermogen niet ten onrechte opgeblazen met een herkende Quooker-load.

De Quooker-detector zelf heeft geen directe control-impact op flexbudgetten zoals Tesla of boiler; de belasting wordt wel correct verklaard in de centrale huisbalans.

## 12. Safety en control

De detector is observe-only:

```text
physicalWritePerformed = false
```

De detector zelf schrijft nooit fysiek. De aparte `EM v2 | 60 Actuator | Quooker v0.2 LIVE` blijft de enige fysieke Quooker-writer.

Belangrijke invarianten:

1. Switch is autoritatief voor ON/OFF.
2. P1 mag alleen heating binnen een ingeschakelde Quooker bevestigen.
3. Geen volledige `getDevices()` snapshot.
4. Geen fysieke Quooker-write.
5. Stale detectorstate wordt door Core niet als actief beschouwd.
6. De baseline volgt alleen niet-heating achtergrond; tijdens HEATING is hij bevroren.

## 13. Validatie

De detector is gebaseerd op eerder handmatig gevalideerde Quooker heating-events en runtime observaties waarbij de Quooker-switch en P1/L3 gezamenlijk zijn gecontroleerd.

v0.4 is op 2026-10-03 gevalideerd tegen de gemeten ochtendpuls van circa +1636 W, daarna live gezet als observe-only Advanced Flow `e291cf14-0b92-4cef-ae8b-a699692b6c9a`. De eerste runtimecheck liet zien dat de oude stale baseline (`0,1 W`) direct werd vervangen door de actuele L3-achtergrond rond `-2383 W`, terwijl `EM_Quooker_Power_W=0` bleef zolang het element niet verwarmde.

## 14. Bekende beperkingen

- De power estimate is gebaseerd op L3-delta ten opzichte van een learned baseline, niet op een dedicated Quooker energiemeter.
- Gelijktijdige L3-belastingen kunnen de confidence verminderen; de autoritatieve Cooker-switch en korte niet-heating baseline beperken dit risico.
- De huidige transition history is beperkt tot acht entries.
- Fingerprint thresholds zijn device-/installatiespecifiek en moeten opnieuw gevalideerd worden bij elektrische configuratiewijzigingen.

## 15. Gerelateerde documentatie

Zie ook:

- `../flows/quooker-flow.md`
- `core.md`
- `fingerprint-engine.md` zodra die centrale module is gemigreerd

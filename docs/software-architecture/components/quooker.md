---
component: quooker
title: Quooker Detector
version: 0.3
status: active
architecture_status: implemented
last_verified: 2026-08-25
source:
  - Homey Advanced Flow: EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING
  - Homey Standard Flow: EM v2 | 01a Quooker | P1 Event Heartbeat v0.2
  - Homey Advanced Flow: EM v2 | 00 Core Tick | v0.10.13 (EV electrical context)
owner: EMS
---

# Quooker Detector

## 1. Doel

De Quooker-detector classificeert de operationele toestand van de Quooker zonder een extra volledige Homey device-snapshot te introduceren.

De architectuur gebruikt twee verschillende bronnen met expliciete verantwoordelijkheden:

- de Homey `onoff` capability van de Cooker-switch is autoritatief voor aan/uit;
- P1 fase L3 wordt alleen gebruikt om te bepalen of de Quooker op dat moment daadwerkelijk verwarmt en om het geschatte Quooker-vermogen af te leiden.

De detector stuurt de Quooker niet aan. Hij publiceert uitsluitend afgeleide toestand en diagnostiek naar Homey Logic, waarna Core deze informatie in dezelfde centrale EMS-state opneemt.

## 2. Actuele runtime

Actieve flows:

| Flow | Status | Functie |
|---|---|---|
| `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING` | actief | classificatie OFF / ON_IDLE / HEATING |
| `EM v2 | 01a Quooker | P1 Event Heartbeat v0.2` | actief | zet alleen `EM_Quooker_P1_Event_Seen=true` bij P1 power change |

De detector draait elke minuut en heeft daarnaast een handmatige start-entry.

## 3. Architectuurregel: geen volledige device-snapshot

De detector gebruikt geen `Homey.devices.getDevices()`.

Per normale minuutrun leest hij gericht precies één device:

```text
Cooker switch
```

Alleen wanneer de P1-heartbeat aangeeft dat er sinds de vorige detectorrun een relevante P1-change is geweest, wordt aanvullend de P1-meter gericht gelezen.

Daarmee ontstaat:

```text
normale run        = 1 targeted Cooker read
run na P1-event    = 1 targeted Cooker read + 1 targeted P1 read
full snapshot      = nooit
```

Dit is bewust gescheiden van de centrale Core Tick, die zijn eigen single-reader snapshot gebruikt.

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

## 5. P1/L3 heating signature

Wanneer de switch aan staat én een P1-event is gezien, leest de detector `measure_power.l3`.

De huidige signature gebruikt:

```text
MIN_DELTA_W = 1400 W
MAX_DELTA_W = 1750 W
```

Met:

```text
deltaW = max(0, L3_W - baseline_L3_W)
```

Heating is geldig wanneer:

```text
1400 W <= deltaW <= 1750 W
```

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

## 6. Baseline-learning

De L3-baseline wordt alleen conservatief aangepast wanneer de Quooker-switch uit staat.

Huidige parameters:

```text
BASELINE_MAX_STEP_W = 400 W
BASELINE_MAX_W      = 900 W
ALPHA               = 0.30
```

Een nieuwe OFF-sample mag dus alleen in de baseline worden opgenomen wanneer:

```text
L3 <= 900 W
abs(L3 - vorigeBaseline) <= 400 W
```

De update is een eenvoudige exponentially weighted update:

```text
baseline = 0.70 * oudeBaseline + 0.30 * L3
```

Dit voorkomt dat een grote gelijktijdige L3-verbruiker de Quooker-baseline snel vervormt.

Wanneer bij de eerste geldige ON-sample nog geen baseline bestaat, wordt tijdelijk gestart met:

```text
baseline = L3 - 1575 W
```

## 7. P1 Event Heartbeat

De Standard Flow `EM v2 | 01a Quooker | P1 Event Heartbeat v0.2` reageert op:

```text
P1 measure_power_changed
```

De enige actie is:

```text
EM_Quooker_P1_Event_Seen = true
```

Deze flow:

- leest geen apparaten;
- berekent geen fingerprint;
- schrijft geen fysieke actuator;
- triggert geen zware analyse.

De detector consumeert en reset deze vlag bij de volgende minuutrun.

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

Er bestaat geen automatische Quooker-writer in deze detectorarchitectuur.

Belangrijke invarianten:

1. Switch is autoritatief voor ON/OFF.
2. P1 mag alleen heating binnen een ingeschakelde Quooker bevestigen.
3. Geen volledige `getDevices()` snapshot.
4. Geen fysieke Quooker-write.
5. Stale detectorstate wordt door Core niet als actief beschouwd.
6. Baseline-learning gebeurt alleen bij switch OFF.

## 13. Validatie

De detector is gebaseerd op eerder handmatig gevalideerde Quooker heating-events en runtime observaties waarbij de Quooker-switch en P1/L3 gezamenlijk zijn gecontroleerd.

De operationele detectorcode zelf is op 2026-08-25 opnieuw gecontroleerd tegen de live Homey-flow.

## 14. Bekende beperkingen

- De power estimate is gebaseerd op L3-delta ten opzichte van een learned baseline, niet op een dedicated Quooker energiemeter.
- Gelijktijdige L3-belastingen kunnen de confidence verminderen, hoewel de autoritatieve switch en conservatieve baseline-learning false positives beperken.
- De huidige transition history is beperkt tot acht entries.
- Fingerprint thresholds zijn device-/installatiespecifiek en moeten opnieuw gevalideerd worden bij elektrische configuratiewijzigingen.

## 15. Gerelateerde documentatie

Zie ook:

- `../flows/quooker-flow.md`
- `core.md`
- `fingerprint-engine.md` zodra die centrale module is gemigreerd

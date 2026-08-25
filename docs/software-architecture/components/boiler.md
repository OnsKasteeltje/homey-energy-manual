---
component: boiler
title: Warm Water / Boiler Control
version: 0.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-25
source:
  - homey://advancedflow/40d45aeb-174e-4a83-9a42-71ae46065cb4
  - homey://advancedflow/2b9284f6-1d41-453e-a8f9-10c634f56fe5
  - homey://advancedflow/5538f1c9-9a21-4328-9896-942952f5c55f
  - homey://advancedflow/543664be-d07a-4099-92d1-07878b73215d
  - homey://flow/b0863953-0a3d-4155-93d8-85f5a71271d5
  - homey://flow/0d32a9d6-f17a-49cf-848c-1e7bc85e8ab6
  - docs/software-architecture/components/core.md
---

# Warm Water / Boiler Control

## 1. Doel

De warmwaterarchitectuur bewaakt het dagelijkse warmwaterdoel, berekent opportunity- en catch-up-intents in SHADOW en houdt de operationele bronkeuze `WW_Boilermodus` als handmatige bronwaarheid aan. De huidige productieomgeving voert nog geen automatische slimme WW-actuator uit.

## 2. Actuele runtime-status

De actuele situatie is bewust hybride in architectuur, maar **niet** in fysieke aansturing:

- Core v0.10.13 berekent `EM2_WW_State` en `EM2_Control_WW` in SHADOW;
- `WW Post-Goal Opportunity v0.4` draait actief iedere 15 minuten en is PURE SHADOW;
- `WW Seasonal Source Advisor v0.3` draait actief dagelijks om 20:30 en is PURE SHADOW;
- `Warm Water Actuator v0.8 HYBRID` bestaat als kandidaat, maar is uitgeschakeld;
- `Warm Water Actuator v0.6` is eveneens uitgeschakeld en PURE SHADOW;
- fysieke boilerwrites vinden nog plaats via eenvoudige tijdflows: 10:00 AAN fallback en 19:00 idempotent UIT.

Daarom geldt momenteel:

```text
smart WW decisioning = SHADOW
hybrid smart actuator = DISABLED
physical production writes = legacy fixed-time flows
```

## 3. Bronwaarheid

`WW_Boilermodus` is de operationele bronwaarheid:

- `true` = elektrische boiler geselecteerd;
- `false` = CV geselecteerd.

De seizoensadvisor mag deze variabele nooit automatisch wijzigen. Ook het post-goal pad gebruikt seizoensadvies niet als runtime gate.

## 4. Dagdoel en state

De actuele WW-state wordt in Core opgebouwd als `EM2_WW_STATE_V0.8`. Belangrijke regels:

- primair doel: `OP_TEMPERATUUR_ONCE_PER_DAY`;
- goal-latch geldt per lokale kalenderdag;
- confirmed heating gebruikt boiler AAN + vermogen > 1500 W;
- fallback accounting gebruikt bevestigde verwarmingsminuten;
- fallbackdoel = 240 minuten confirmed heating indien het temperatuurdoel niet aantoonbaar wordt bereikt;
- deadline = 19:00;
- na goal reached kan alleen een gevalideerde post-goal opportunity optreden, nooit een MUST-heropwarming.

## 5. SHADOW control policy

Core publiceert `EM2_CONTROL_WW_V0.11`. De beslissing kent onder andere:

- `BOILER_ON`;
- `BOILER_OFF`;
- `HOLD`.

Prioriteit is `MUST`, `SHOULD` of `MAY`. Deze output is read-only en voert zelf geen device-write uit.

De belangrijkste volgorde is:

1. verkeerde bronmodus / na 19:00;
2. dagdoel bereikt;
3. gevalideerde post-goal opportunity;
4. catch-up MUST;
5. ochtend-wachtvenster;
6. flex-export opportunity;
7. negatieve of goedkope prijs met guards;
8. PV-forecast opportunity;
9. run-lock;
10. stop bij ongunstige import/prijs;
11. anders HOLD.

## 6. Post-goal opportunity

`EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` draait iedere 15 minuten.

Eigenschappen:

- PURE SHADOW;
- geen device reads;
- geen device writes;
- alleen actief als het dagdoel al bereikt is;
- `WW_Boilermodus` moet boiler toestaan;
- minimum vertraging na goal is configureerbaar, standaard 60 minuten;
- thermische ruimte wordt benaderd via standbyverlies + avondgebruikprior;
- economische opportunity via verse contractprijscontext of voldoende PV-flexbudget;
- maximale prioriteit is `SHOULD`;
- `mandatoryReheat=false`;
- de goal-latch wordt nooit gewist.

## 7. Seasonal Source Advisor

`EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` draait dagelijks om 20:30.

Deze advisor:

- vergelijkt elektrische boiler versus CV op bruikbare kWh-kosten;
- gebruikt historische P1-, prijs- en boilerdata;
- simuleert een 1,9 kW boiler binnen 09:30–19:00;
- hanteert een rolling window en hysterese;
- vereist meerdere bevestigingsdagen vóór een switchadvies;
- stuurt hooguit een notificatie;
- gebruikt claim-before-send idempotency voor notificaties;
- schrijft nooit devices;
- schrijft nooit `WW_Boilermodus`.

De menselijke handmatige bronkeuze blijft dus leidend.

## 8. Fysieke productieacties

Op dit moment zijn de feitelijk actieve fysieke writes eenvoudiger dan de SHADOW policy.

### 10:00 ochtend fallback

Actieve Standard Flow:

`Boiler aan | ochtend fallback v1.1`

- trigger: exact 10:00;
- conditie: boiler staat UIT;
- actie: boiler AAN.

### 19:00 nachtgrens

Actieve Standard Flow:

`EM v2 | 60 Control | Boiler Night OFF v0.2 idempotent`

- trigger: exact 19:00;
- conditie: boiler staat AAN;
- actie: boiler UIT.

Deze twee flows zijn momenteel de operationele fysieke write-laag voor de boiler.

## 9. HYBRID actuator kandidaat

`Warm Water Actuator v0.8 HYBRID` is uitgeschakeld en heeft geen periodieke trigger. Hij bevat reeds de gewenste guards voor toekomstige cut-over:

- State schema;
- WW-state schema;
- Control schema;
- revision alignment;
- <=10 minuten freshness;
- Core guards;
- `WW_Boilermodus` broncheck;
- aparte kill-switch `EM2_WW_Hybrid_Enabled`;
- HOLD schrijft nooit fysiek;
- geen device-read vóór alle guards slagen;
- idempotent NOOP wanneer huidige on/off al gelijk is aan doel.

De kill-switch default is `false`.

## 10. One-writer doelarchitectuur

De gewenste eindtoestand is:

```text
Core WW State / Control
        ↓
validated actuator guard layer
        ↓
exact één automatische boiler-writer
```

De huidige situatie voldoet daar nog niet volledig aan, omdat de slimme actuator disabled is en de fysieke writes nog via afzonderlijke tijdflows plaatsvinden.

## 11. Idempotency

Huidige bescherming:

- 19:00 OFF-flow schrijft alleen wanneer boiler daadwerkelijk AAN staat;
- HYBRID kandidaat heeft `NOOP_ALREADY_TARGET`;
- Seasonal Advisor claimt notificatie vóór side effect en arbitreert 750 ms;
- post-goal output is logisch-only en nooit MUST;
- Core WW-control is read-only.

## 12. Fail-safe gedrag

De HYBRID kandidaat blokkeert fysieke writes bij:

- schema mismatch;
- revision mismatch;
- stale State/Control;
- falende Core guards;
- ongeldige action/priority;
- CV-bronmodus bij `BOILER_ON`;
- kill-switch uit;
- ontbrekende boiler of onoff-capability.

## 13. Bekende beperkingen

- De actieve 10:00 fallback houdt nog geen rekening met `WW_Boilermodus` in de Standard Flow zelf.
- De slimme SHADOW policy en de feitelijke fysieke productiewrites zijn nog niet dezelfde keten.
- De HYBRID actuator is nog niet actief gevalideerd als enige automatische writer.
- `Warm Water Observer v0.2` is uitgeschakeld en verouderd; WW-state wordt nu in Core beheerd.

## 14. Cut-over criterium

Voor activatie van HYBRID moeten minimaal gelden:

1. runtime-validatie van State/WW/Control alignment;
2. bewijs dat `WW_Boilermodus=false` nooit een `BOILER_ON` write oplevert;
3. kill-switch fail-safe test;
4. dubbele trigger/idempotency test;
5. bevestiging dat legacy 10:00/19:00 fysieke writers gecontroleerd worden uitgefaseerd of expliciet compatibel blijven;
6. één-writer architectuur aantoonbaar actief.

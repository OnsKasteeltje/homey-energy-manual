---
component: boiler
title: Warm Water / Boiler Control
version: 0.2.1
status: active
architecture_status: implemented-production
last_verified: 2026-09-13
source:
  - docs/architecture/CURRENT-EMS-STATE.md
  - homey://advancedflow/40d45aeb-174e-4a83-9a42-71ae46065cb4
  - homey://advancedflow/39c39cc5-12bb-4494-ba45-bad47a656696
  - homey://advancedflow/8bf53fdb-76f4-47db-8ccb-773ac515f06e
  - docs/software-architecture/components/planner-power-intent.md
---

# Warm Water / Boiler Control

## 1. Doel

De warmwaterarchitectuur combineert Pi-planning met Homey execution/safety. WW comfort blijft een harde constraint boven optimalisatie. De actuele productiearchitectuur gebruikt niet langer alleen legacy fixed-time physical writes: de slimme WW adapter/gate/actuatorketen is live.

## 2. Productieketen

```text
Pi hardened dynamic planner
        ↓
Pi /control/current
        ↓
Homey PI Dynamic Planner Bridge v1.3.0 REALTIME-PV DEADLINE-GUARD [READY]
        ↓
EM2_Power_Intent v0.2 / targets.ww.target_on
        ↓
WW Power Adapter v0.2 TARGETED-READ SHADOW
        ↓
WW Power Adapter Gate v0.2 TARGETED-READ
        ↓
Warm Water Actuator v0.9 TARGETED-READ LIVE
        ↓
Boiler
```

De Pi planner en bridge schrijven geen physical devices. Homey blijft executor en lokale safetylaag. Dezelfde actuele PI bridge produceert de canonieke Power Intent voor zowel EV als WW; de domeinspecifieke adapters/gates/actuators splitsen daarna de fysieke uitvoering.

## 3. WW planning

WW comfort is een harde constraint.

De Pi planner:

- plant de resterende benodigde verwarming vóór de harde 19:00 deadline;
- geeft bruikbare PV-perioden voorrang;
- kan shoulders van een PV-window gebruiken wanneer een aangesloten Tesla de centrale PV-piek beter kan absorberen;
- plant geen onnodige repeat heating nadat het dagelijkse doel is bereikt;
- gebruikt aanvullende multiday lookahead voor feasibility waar nodig.

De productie-interface vanuit Power Intent blijft binair:

- `target_on = true` → boiler ON gewenst;
- `target_on = false` → boiler OFF gewenst;
- `target_on = null` → HOLD.

Een numeriek `WW_target_W` is nog geen daadwerkelijk productiecontract.

## 4. Bronmodus

`WW_Boilermodus` blijft een lokale operationele safety/boundary:

- `true` = elektrische boiler mag worden aangestuurd;
- `false` = CV-bron geselecteerd; boiler-ON writes zijn geblokkeerd.

De live actuator controleert deze bronmodus vóór device access.

## 5. WW Power Adapter Gate v0.2

Actuele gate:

`EM v2 | 80 Validation | WW Power Adapter Gate v0.2 TARGETED-READ`

Deze flow is enabled en niet broken.

De gate wordt getriggerd door wijziging van `EM2_WW_Power_Adapter`, gebruikt targeted Logic reads en vereist exact:

- `EM2_POWER_INTENT_V0.2`;
- `EM2_WW_POWER_ADAPTER_V0.2`;
- geldige `target_on` semantiek;
- sourceRevision alignment tussen intent en adapter;
- adapter `valid=true`;
- adapter read-only/SHADOW metadata;
- correcte `onoff` mapping;
- geen device writes in adapter.

Alleen bij volledige match publiceert de gate `finalStatus = PASS`; anders faalt hij gesloten met een null-command.

## 6. Warm Water Actuator v0.9 LIVE

Actuele fysieke writer:

`EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE`

Live status per 13 september 2026:

- enabled;
- niet broken;
- event-driven door `EM2_WW_Adapter_Gate`;
- sole WW physical writer.

De actuator gebruikt targeted Logic reads en raakt de boiler pas na alle guards.

Vereiste guards:

1. LIVE kill-switch/arm actief;
2. `WW_Boilermodus = true`;
3. juiste intent/adapter/gate schema's;
4. exact sourceRevision alignment;
5. gate `PASS` en `valid=true`;
6. intent/gate maximaal 10 minuten oud;
7. command is boolean ON/OFF of expliciete HOLD.

`HOLD` doet geen device-read/write.

Bij ON/OFF wordt de boiler uitsluitend via het exacte boiler-ID gelezen. Als de actuele `onoff` al gelijk is aan het doel, volgt `NOOP_ALREADY_TARGET`; anders wordt exact één capability-write uitgevoerd en als `WRITE_OK` gerapporteerd.

## 7. Single-writer invariant

De actuele architectuur vereist:

```text
planner = geen device writer
Power Intent = geen device writer
WW adapter = geen device writer
WW gate = geen device writer
Warm Water Actuator v0.9 = enige fysieke WW writer
```

Legacy of testflows die de boiler automatisch fysiek zouden kunnen schrijven mogen niet parallel concurreren met deze actuator. Zij moeten disabled, uitgefaseerd of aantoonbaar compatibel zijn.

## 8. Fail-safe gedrag

De live actuator blokkeert fysieke writes bij onder meer:

- kill-switch niet actief;
- CV-bronmodus;
- schema mismatch;
- revision mismatch;
- gate FAIL;
- stale intent/gate;
- ongeldig command;
- boiler/device-read fout;
- ontbrekende `onoff` capability.

Bij `HOLD` is er expliciet geen physical write.

## 9. Validatie

Tijdens gecontroleerde Pi cutover-validatie op 12 september 2026 is een current-slot WW target ON geïnjecteerd.

Geobserveerd:

- boiler `onoff = true`;
- vermogen circa 2.03 kW;
- stroom circa 8.97 A;
- na terugkeer naar normale Pi target ging de boiler terug naar `onoff = false`, 0 W.

Resultaat: **Pi → Homey → boiler ON en OFF beide PASS.**

Op 13 september 2026 is de actieve Homey flow inventory opnieuw gecontroleerd. Daarin staan de actuele PI Dynamic Planner Bridge v1.3.0, WW Power Adapter v0.2, WW Power Adapter Gate v0.2 en Warm Water Actuator v0.9 als de productiecomponenten van deze keten.

## 10. Documentatiedrift die hiermee is opgeheven

Het eerdere model waarin smart WW control uitsluitend SHADOW was en fysieke writes alleen via 10:00/19:00 fixed-time flows liepen, is niet meer de actuele productiearchitectuur. De live v0.9 actuator en WW gate zijn nu leidend voor de slimme controlketen.

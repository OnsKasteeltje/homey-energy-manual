---
component: planner-power-intent
title: 24h Energy Planner and Power Intent
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-25
sources:
  - Homey Advanced Flow: EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | Actuator Commands v0.1 SHADOW
---

# 24h Energy Planner and Power Intent

## 1. Doel

Deze laag vertaalt de actuele EMS-toestand en contractcontext naar twee verschillende soorten output:

1. een 24-uurs SHADOW-planning voor Tesla, warm water en een toekomstige Victron-accu;
2. een numerieke, revision-aligned Power Intent die de actuele Core-policy projecteert naar actuator-neutrale doelen zoals `EV_target_W`.

De laag is uitsluitend adviserend/translationeel. Geen van de beschreven flows voert fysieke writes uit.

## 2. Architectuurgrens

De keten is:

`Core / Contract Context -> 24h Planner (advies)`

`Core Decision + WW Control + Public State -> Power Intent -> apparaat-specifieke adapters -> toekomstige fysieke writers`

De 24h Planner is dus geen runtime-actuatorcontroller. Power Intent is evenmin policy-owner; het projecteert bestaande Core-beslissingen naar numerieke doelen.

## 3. 24h Energy Planner v0.2 SHADOW

De planner draait iedere 15 minuten met 45 seconden vertraging en kan handmatig gestart worden.

### 3.1 Simulatiescenario

Het huidige vaste SHADOW-scenario is:

- Victron MultiPlus-II 48/5000/70-50;
- 3 x Pylontech US5000;
- 14.4 kWh nominale capaciteit;
- aangenomen SOC-band 20-90%;
- 3.3 kW AC charge/discharge limiet;
- 95% charge- en 95% discharge-efficiency;
- round-trip efficiency 90.25%;
- bruikbaar simulatievenster 10.08 kWh.

Deze waarden zijn uitsluitend simulatie-aannames en zijn geen commissioningwaarden.

### 3.2 Tesla

De planner verzint geen laadvermogen of throughput. Bij een actieve Tesla-deadline gebruikt hij de bestaande deadline/latest-start als hard planningsvenster en rangschikt hij prijs-slots binnen dat venster.

Daarmee is de planner economisch adviserend, maar niet bevoegd om laadstroom te bepalen.

### 3.3 Warm water

Voor warm water gebruikt de planner het reeds gemodelleerde boilerniveau van circa 1.9 kW. Het resterende fallback-volume wordt omgerekend naar kWh en verdeeld over goedkope 15-minutenslots vóór 19:00.

### 3.4 Batterij

Batterijplanning is expliciet theoretisch. Charge/discharge-kandidaten en economische pairs worden berekend uit prijsverschillen en het aangenomen rendement.

Omdat actuele SOC, gedetailleerde base-load en een echte 15-min PV-forecast ontbreken, mag `theoreticalUpperBoundEuro` nooit als gerealiseerde besparing worden geïnterpreteerd.

## 4. Power Intent v0.2 SHADOW

Power Intent wordt getriggerd door wijziging van `EM2_Public_State` en is idempotent per source revision.

Voor een geldige output moeten vier revisions gelijk zijn:

- Public State revision;
- Core State revision;
- Decision sourceRevision;
- WW Control sourceRevision.

Bij mismatch is `valid=false`, `status=REVISION_MISMATCH` en het EV-doel fail-closed 0 W.

## 5. Numeriek EV-target

Power Intent v0.2 maakt `targets.ev.target_W` op basis van de bestaande Core Decision.

### Deadline

Bij `TESLA_CHARGE_DEADLINE`:

`target_W = remaining_kWh / hours_to_deadline * 1000`

Alleen als zowel resterende energie als een geldige toekomstige deadline beschikbaar zijn.

### Export-opportunity

Bij `TESLA_CHARGE_OPPORTUNITY` met minimaal 800 W flexbudget:

`target_W = flexExportBudget_W`

### Prijs-opportunity

Als geen exportbudget beschikbaar is maar prijs negatief/goedkoop is:

`target_W = discretionaryImportBudget_W`

### Geen geldige opportunity

Dan is `target_W = 0`.

Power Intent converteert bewust niet naar ampère. Elektrische clamping hoort bij de apparaatadapter.

## 6. Warmwater-target

Warmwater wordt nog als binaire intentie geprojecteerd:

- `BOILER_ON -> target_on=true`
- `BOILER_OFF -> target_on=false`
- `HOLD -> target_on=null`

Er wordt nog geen numeriek `WW_target_W` gegenereerd.

## 7. EV Power Adapter v0.1 SHADOW

De aparte EV Power Adapter accepteert zowel `EM2_POWER_INTENT_V0.1` als `V0.2` en is daarmee compatibel met de actuele producer.

De adapter:

- leest geen devices zelf;
- gebruikt alleen elektrische context uit `EM2_State`;
- bepaalt W/A op basis van geobserveerd vermogen per requested A, of theoretisch `voltage x active phases`;
- gebruikt 6 A minimum en 16 A maximum;
- past een deadband toe ter grootte van circa `W_per_A x 6A`;
- schrijft nooit fysiek naar Easee.

Voorbeeldstatussen:

- `OK_IDLE`
- `OK_DEADBAND_IDLE`
- `OK_TRANSLATED`
- `WAITING_FOR_ELECTRICAL_CONTEXT`
- `REVISION_MISMATCH`

## 8. Bekende integratie-afwijking

`EM v2 | 60 Adapter | Actuator Commands v0.1 SHADOW` valideert momenteel uitsluitend:

`intent.schema === EM2_POWER_INTENT_V0.1`

De live Power Intent producer schrijft echter `EM2_POWER_INTENT_V0.2`.

Daarom is deze generieke adapter op dit moment schema-incompatibel en zal hij voor de actuele Power Intent `INVALID_POWER_INTENT` publiceren.

Dit is geen probleem voor de aparte EV Power Adapter, omdat die zowel v0.1 als v0.2 accepteert. Voor een toekomstige generieke actuator-cut-over moet `Actuator Commands` eerst expliciet naar Power Intent v0.2 worden bijgewerkt en gevalideerd.

## 9. Single-writer boundary

De beoogde architectuur blijft:

- Core owns policy/arbitration;
- Power Intent owns neutral numeric/binary intent;
- adapters own translation, electrical clamping, guards and dedupe;
- slechts één expliciete fysieke writer per actuator mag actief zijn.

Een fysieke writer mag pas worden geactiveerd via een gecontroleerde atomic cut-over waarbij de bestaande productiewriter wordt uitgefaseerd.

## 10. Safety invariants

Deze laag moet altijd voldoen aan:

- geen device writes;
- geen netwerkcalls vanuit Power Intent/adapters;
- geen policy-arbitrage in adapters;
- revision alignment vóór numerieke targets;
- fail-closed bij ontbrekende of onbekende input;
- geen verzonnen Tesla throughput;
- geen claim van gerealiseerde batterijbesparing zonder actuele SOC/load/PV-data;
- één fysieke writer per actuator bij toekomstige ACTIVE-integratie.

## 11. Huidige status

| Onderdeel | Status |
|---|---|
| 24h Planner v0.2 | ACTIVE SHADOW |
| Power Intent v0.2 | ACTIVE SHADOW |
| EV Power Adapter v0.1 | ACTIVE SHADOW, v0.2 compatible |
| Actuator Commands v0.1 | ACTIVE SHADOW, schema mismatch met Power Intent v0.2 |
| EV fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| Victron fysieke writer | NIET ACTIEF |
| WW fysieke writer via nieuwe adapterketen | NIET ACTIEF |

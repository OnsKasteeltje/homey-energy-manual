---
component: planner-power-intent
title: Pi Planner and Power Intent
status: active
architecture_status: implemented-production
last_verified: 2026-09-13
sources:
  - docs/architecture/CURRENT-EMS-STATE.md
  - Homey Advanced Flow: EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2.6 AUTHORITY-GUARD [HOMEY ACTIVE]
  - Pi endpoint: GET /control/current
---

# Pi Planner and Power Intent

## Doel

Deze laag vertaalt forecasts, historie, actuele state en contractpolicy naar een kwartierplanning op de Raspberry Pi en projecteert uitsluitend het actuele geldige slot via Homey naar actuator-neutrale Power Intent.

Productieketen:

`Forecasts + history + live state + FIXED contract policy -> Pi planner -> /control/current -> Homey PI Bridge -> EM2_Power_Intent -> adapters/gates -> actuators`

De planner schrijft geen fysieke devices. Homey blijft executor en lokale safetylaag.

## Runtime authority

`EM2_Planner_Authority` is de enige echte runtime authority selector.

- `PI` → de Pi bridge mag de actuele Pi-command publiceren naar `EM2_Power_Intent`.
- `HOMEY` → de Pi bridge blijft inert en de guarded Homey producer `P1 v0.2.6 AUTHORITY-GUARD` vormt het rollbackpad.

Er mag nooit gelijktijdig een Pi- en Homey-plannerauthority voor dezelfde actuator actief zijn.

## Productiecontract

De planner draait productie onder:

- mode `FIXED`;
- contract-id `ENGIE_3Y_2026_2029`;
- supplier `ENGIE`.

Dynamische prijsdata mag onder dit contract alleen voor shadow, analyse of replay worden gebruikt. Zij mag geen productieactie veroorzaken en er is geen automatische fallback of contract-mode switching naar DYNAMIC.

## Pi planning chain

De reguliere keten bouwt de input in deze volgorde:

1. PV forecast;
2. clean base-load history;
3. base-load forecast;
4. warm-water input;
5. warm-water plan;
6. WW forecast import;
7. quarter-hour shadow plan;
8. hardened dynamic planner v0.3;
9. website shadow representations;
10. publication artifacts.

De chain draait via `ems-forecast-chain.service` (`Type=oneshot`). `inactive (dead)` na een succesvolle run is normaal.

## Dynamic planner v0.3

Het actuele schema is `EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3`.

Belangrijke eigenschappen:

- 96 kwartierslots als 24-uurs actiehorizon;
- plannerOwner `PI`;
- fixed ENGIE contract metadata;
- input freshness checks;
- planner `validUntil`;
- WW comfort feasibility;
- Tesla deadline feasibility;
- fail-closed execution metadata;
- aanvullende multiday lookahead voor WW-feasibility.

De naam 'dynamic planner' verwijst naar dynamische planning van flex-loads; onder het huidige productiecontract betekent dit **niet** dat dynamische energietarieven productie-authority hebben.

## Control endpoint

`GET /control/current` levert schema `EMS_PI_CONTROL_COMMAND_V0.1`.

Voor een READY-command gelden minimaal:

- `status = READY`;
- `readyForCutover = true`;
- `plannerOwner = PI`;
- `executor = HOMEY`;
- contract mode `FIXED`;
- contract id `ENGIE_3Y_2026_2029`;
- plannerinput is fresh;
- huidig kwartierslot is geldig.

Slotsemantiek:

- start uit `slot_start_utc`;
- eind uit `slot_end_utc`, of exact start + 15 minuten indien niet aanwezig;
- huidig slot voldoet aan `start <= now < end`;
- command-validity wordt begrensd door zowel slot-end als planner `validUntil`.

De endpoint is een readiness/command endpoint en vormt geen tweede authority selector naast Homey.

## Homey PI Bridge v1.2.6

Actieve productiebridge:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]`

Eigenschappen:

- enabled, maar inert zolang `EM2_Planner_Authority != PI`;
- leest `http://192.168.1.42:3100/control/current`;
- valideert schema, READY/cutover, owner/executor, FIXED ENGIE metadata en freshness;
- projecteert naar `EM2_POWER_INTENT_V0.2`;
- schrijft geen fysieke devices;
- failt gesloten naar 0/off wanneer de Pi-command niet bruikbaar is;
- houdt persistent bridge diagnostics bij;
- bevat een executor-side Tesla deadline guard als laatste safetylaag.

## Tesla policy

Opportunity charging gebruikt residual PV na WW-reservering.

Actuele invariant:

- minimum start = 3×6 A;
- minimum stable run = 3×6 A;
- nominaal minimumvermogen = 4140 W bij 3×230 V;
- opportunity start vereist minimaal één positief 15-minuten-slot;
- elk volgend kwartier wordt opnieuw onafhankelijk beoordeeld;
- korte anti-flap/session bescherming hoort bij executor, niet bij de plannerwindow;
- deadline/MUST mag netenergie gebruiken indien nodig;
- deadline-forcing mag niet vóór `latest_start_at` ontstaan.

De Homey bridge mag at/after de earliest safe latest-start een actieve aangesloten Tesla naar het geconfigureerde deadline maximum projecteren. Vóór dat punt blijft de Pi-PV-target onaangetast.

## Warm water policy

WW comfort staat boven optimalisatie.

De Pi:

- plant resterende benodigde opwarming vóór 19:00;
- geeft bruikbare PV-perioden voorrang;
- kan shoulders van een PV-window gebruiken zodat Tesla de centrale piek kan absorberen;
- plant geen onnodige repeat heating nadat het dagelijkse doel is bereikt.

De actuele Power Intent interface voor WW blijft binair `target_on=true/false/null`; numeriek `WW_target_W` is geen productiecontract zolang de producer dit niet werkelijk levert.

## Power Intent

Canonical output: `EM2_POWER_INTENT_V0.2`.

Bij Pi-authority bevat de intent onder meer:

- `plannerOwner: PI`;
- `executor: HOMEY`;
- `authoritySelector: PI`;
- contract metadata FIXED/ENGIE;
- `targets.ev.target_W`;
- `targets.ww.target_on`;
- fail-closed status en safety metadata.

De intent blijft logic-only en schrijft geen devices.

## HOMEY rollback producer

Rollbackproducer:

`EM v2 | 20 Power Intent | P1 v0.2.6 AUTHORITY-GUARD [HOMEY ACTIVE]`

Deze producer:

- doet niets tenzij selector `HOMEY` is;
- gebruikt canonieke Homey state/decision/control revisions;
- faalt gesloten bij revision- of semantic mismatch;
- schrijft uitsluitend `EM2_Power_Intent`;
- projecteert PI bridge diagnostics uitsluitend als observability wanneer beschikbaar.

## Adapter/writer boundary

Power Intent is niet de fysieke writer.

EV:

`EM2_Power_Intent -> EV Adapter -> EV Gate -> EV Actuator -> Easee`

WW:

`EM2_Power_Intent -> WW Adapter -> WW Gate -> Warm Water Actuator -> Boiler`

Per actuator mag maximaal één fysieke writer actief zijn.

## Huidige status

| Onderdeel | Status |
|---|---|
| Pi hardened dynamic planner v0.3 | ACTIVE PRODUCTION PLANNER |
| `/control/current` | ACTIVE PRODUCTION COMMAND ENDPOINT |
| Planner authority selector | `EM2_Planner_Authority` |
| PI Bridge v1.2.6 | ACTIVE, gated by selector |
| Homey P1 v0.2.6 | ACTIVE ROLLBACK PRODUCER, gated by selector |
| Contract policy | FIXED / ENGIE_3Y_2026_2029 |
| Dynamic prices | SHADOW / ANALYSIS ONLY |
| Tesla opportunity | residual PV, START6/RUN6 |
| Tesla deadline | hard constraint; no forcing before latest-start |
| WW planning | PV-first with hard comfort/deadline constraint |
| EV physical writer | Homey EV actuator |
| WW physical writer | Homey WW actuator |
| Victron physical writer | NOT INTEGRATED |

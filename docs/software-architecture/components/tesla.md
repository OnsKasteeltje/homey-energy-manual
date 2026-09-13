---
component: tesla
title: Tesla Charging Control
version: 3.1.0
status: active
architecture_status: implemented-production
last_verified: 2026-09-13
source:
  - docs/architecture/CURRENT-EMS-STATE.md
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6
  - Homey Advanced Flow: EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6
  - Homey Advanced Flow: EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION
  - Homey Advanced Flow: EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.3.0 REALTIME-PV DEADLINE-GUARD [READY]
---

# Tesla Charging Control

## Doel

De Tesla-laadfunctie gebruikt de Pi voor planning en Homey voor executor/safety. Het oude autonome `Tesla laden v2.7.15` productiepad is niet meer de actuele control-architectuur. De productie-EV-keten loopt via Pi planner → Power Intent → EV adapter/gate → single actuator.

## Productiepad

```text
Pi hardened dynamic planner v0.3
        ↓
Pi /control/current + bounded realtime EV envelope v0.3
        ↓
Homey PI Dynamic Planner Bridge v1.3.0 REALTIME-PV
        ↓
EM2_Power_Intent v0.2
        ↓
EV Power Adapter v0.1.5
        ↓
EV Power Adapter Gate v0.2.6
        ↓
EV Power Actuator v0.2.7
        ↓
Easee / Tesla
```

Homey blijft de lokale executor en safetylaag. De planner en bridge schrijven zelf geen physical devices.

## Runtime authority

`EM2_Planner_Authority` bepaalt wie Power Intent mag produceren.

- `PI` → Pi bridge authority.
- `HOMEY` → guarded Homey P1 v0.2.6 rollback producer.

Deze selector voorkomt dubbele planner authority.

## Opportunity charging

Opportunity charging is PV-gedreven.

Actuele regels:

- Pi bepaalt policy en bounded realtime envelope;
- Homey mag alleen binnen dat Pi-envelope realtime moduleren;
- live P1 is netto na huidig EV-verbruik;
- counterfactual EV-surplus is `max(0, -P1_W + EV_actual_W)`;
- WW wordt niet teruggeteld: werkelijk WW-verbruik zit al in P1;
- startminimum = 3×6 A;
- runminimum = 3×6 A;
- nominaal minimumvermogen = 4140 W bij 3×230 V;
- realtime current blijft begrensd door Pi/deadline maxA;
- korte anti-flap/session protection blijft een executor concern.

Een goedkope of negatieve prijs mag onder het huidige FIXED-contract geen Tesla-opportunity creëren.

## Deadline charging

Een expliciete deadline is een harde MUST-constraint.

- PV blijft waar mogelijk eerste bron.
- Netenergie mag worden gebruikt wanneer dat noodzakelijk is om de deadline te halen.
- Geforceerd deadline-laden mag niet vóór `latest_start_at` worden geïntroduceerd.
- De Homey PI bridge v1.3.0 bevat een executor-side deadline guard als laatste safetylaag.
- De guard gebruikt canonieke Tesla connectivity/chargeState en remaining-energy/deadlinecontext.
- At/after de earliest safe latest-start kan de guard een aangesloten Tesla naar het geconfigureerde deadline maximum projecteren.
- De deadline guard draait na realtime-PV-projectie en heeft daarmee voorrang wanneer deadline-laden vereist is.

## EV Power Adapter

Actuele adapter:

`EM v2 | 60 Adapter | EV Power v0.1.5 DEADLINE-CAP OPPORTUNITY16 START6 RUN6`

De adapter vertaalt `targets.ev.target_W` naar een uitvoerbare stroomopdracht. Hij introduceert geen nieuwe EMS-policy en mag het upstream vermogensbudget niet verhogen.

Actuele mappingcontract:

`FLOOR_3P230_START6_RUN6_FAIL_CLOSED`

Daarmee geldt conceptueel:

`requested_A = floor(target_W / (3 × 230))`

met minimaal 6 A voor een positieve uitvoerbare laadopdracht en maximaal de toegestane capability/configuratiegrens.

## EV Gate

Actuele gate:

`EM v2 | 80 Validation | EV Power Adapter Gate v0.2.6 START6`

De gate bewaakt onder meer:

- Power Intent schema;
- adapter schema;
- source/state revision alignment;
- freshness;
- electrical mapping semantics;
- fail-closed gedrag.

Een coherente positieve opdracht wordt niet uitsluitend geblokkeerd omdat observability-only Easee telemetry health als `STALE` staat. Device-health blijft diagnostisch; onafhankelijke schema/revision/mapping safetychecks blijven hard.

## EV actuator

Actuele fysieke writer:

`EM v2 | 60 Actuator | EV Power v0.2.7 START6 RUN6 LIVE + EASEE SESSION`

Deze actuator is de enige automatische fysieke Easee-writer in de productiearchitectuur. Hij verzorgt session start/resume, current setting, idempotency en fail-closed stop/pause op basis van de gevalideerde gate-output.

Bij een geldige opdracht van 0 A normaliseert de actuator de Easee expliciet terug naar 0 A (`NORMALIZE_AUTOSTART_TO_ZERO`). Dit is relevant wanneer de Tesla opnieuw wordt aangesloten en Easee tijdelijk autonoom hervat met een eerder beschikbare laadstroom.

Legacy automatische Tesla-flows mogen niet parallel physical writes uitvoeren. Handmatige flows mogen alleen blijven bestaan wanneer zij expliciet handmatig zijn en niet concurreren met automatic control.

## Reconnect en periodieke reconciliation

Op 13 september 2026 is het reconnect-gedrag expliciet gecontroleerd in GitHub en daarna in de actieve Homey-runtime.

Er bestaat geen aparte Tesla/Easee reconnect-trigger die uitsluitend bij opnieuw aansluiten de EMS-opdracht afdwingt. De gewenste correctie ontstaat via de normale periodieke control-keten:

```text
Tesla opnieuw aangesloten
        ↓
Easee kan tijdelijk autonoom hervatten
        ↓
PI Dynamic Planner Bridge draait elke minuut
        ↓
nieuw EM2_Power_Intent met nieuw generatedAt
        ↓
EV Adapter → EV Gate → EV Actuator
        ↓
actuator dwingt actuele EMS-opdracht opnieuw fysiek af
```

Daarmee geldt:

- bij actuele EMS-opdracht 0 A schrijft de actuator opnieuw `target_charger_current = 0` en wordt een autonome Easee-herstart weer gepauzeerd;
- bij een positieve realtime-PV-opdracht wordt de binnen het Pi-envelope berekende stroom opnieuw afgedwongen;
- wanneer de deadline guard eigenaar is, wordt juist het deadline-target opnieuw afgedwongen;
- reconnect-reconciliation gebruikt dus dezelfde single-writer productiechain en introduceert geen tweede controller of directe Easee-writer.

Live validatie op 13 september 2026 na opnieuw aansluiten eindigde met Easee `Paused`, `plugged_in_paused`, `target_charger_current = 0`, offered current 0 A en measure_power 0 W. Dit bevestigde de gebouwde periodieke reconciliation bij een actuele 0 A-opdracht.

## START6 validatie

Op 12 september 2026 is gecontroleerd bewezen dat een gepauzeerde Easee/Tesla-sessie direct kan starten op 3×6 A. Gemeten waarden lagen rond 6.01/6.03/6.05 A en circa 4.235 kW totaal.

Dit is de basis voor START6/RUN6 in productie.

Een eerdere gecontroleerde Pi cutover-test op 7 A bewees daarnaast de volledige ON/OFF-keten Pi → Homey → Easee/Tesla.

## Contract policy

De productie-EMS staat op:

- `FIXED`;
- `ENGIE_3Y_2026_2029`;
- supplier `ENGIE`.

Dynamische prijsdata mag alleen voor shadow/analyse/replay worden gebruikt. Automatische fallback of mode-switching naar DYNAMIC is niet toegestaan.

## Fail-safe gedrag

Bij ongeldige/stale Pi-command, schemafout, revision mismatch of ongeldige adapter/gate mapping wordt de EV-target fail-closed 0 W / 0 A.

De Pi planner zelf schrijft geen Easee-device. De fysieke writer blijft Homey.

## Architectuurgrens

Actuele invariant:

```text
planner policy != device writer
Power Intent != device writer
adapter != device writer
gate != device writer
exact één EV actuator = physical writer
```

Het oude documentatiemodel waarin `Tesla laden v2.7.15` de productiecontroller was en EV Power Adapter uitsluitend SHADOW was, is vervallen.

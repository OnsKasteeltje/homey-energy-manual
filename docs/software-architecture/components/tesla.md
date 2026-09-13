---
component: tesla
title: Tesla Charging Control
version: 3.2.0
status: active
architecture_status: implemented-production
last_verified: 2026-09-13
source:
  - docs/architecture/CURRENT-EMS-STATE.md
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power
  - Homey Advanced Flow: EM v2 | 80 Validation | EV Power Adapter Gate
  - Homey Advanced Flow: EM v2 | 60 Actuator | EV Power v0.2.12 LIVE WIRING + DEADLINE GATE AUTHORITY
  - Homey Advanced Flow: EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.3.0 REALTIME-PV DEADLINE-GUARD
---

# Tesla Charging Control

## Doel

De Tesla-laadfunctie gebruikt de Pi voor planning en Homey voor executor/safety. Het oude autonome Tesla-productiepad is niet meer de actuele control-architectuur. De productie-EV-keten loopt via Pi planner → Power Intent → EV adapter → EV gate → single actuator → Easee/Tesla.

## Productiepad en authority

```text
Pi hardened dynamic planner v0.3
        ↓
Pi /control/current + bounded realtime EV envelope
        ↓
Homey PI Dynamic Planner Bridge v1.3.0
        ↓
EM2_Power_Intent v0.2
        ↓
EV Power Adapter
        ↓
EV Power Adapter Gate
        ↓
EV Power Actuator v0.2.12 flow
  └─ actuator logic v0.2.11
        ↓
Easee / Tesla
```

Homey blijft de lokale executor en safetylaag. Planner, bridge, adapter en gate schrijven geen physical devices. Exact één EV actuator is de automatische fysieke writer.

`EM2_Planner_Authority` bepaalt wie Power Intent mag produceren. `PI` is de normale productie-authority; `HOMEY` is alleen de guarded rollback-route. Dubbele planner authority is niet toegestaan.

## Opportunity charging

Opportunity charging is PV-gedreven. Pi bepaalt policy en bounded realtime envelope; Homey mag alleen binnen dat envelope realtime moduleren. Live P1 is netto na huidig EV-verbruik. Counterfactual EV-surplus is conceptueel `max(0, -P1_W + EV_actual_W)`. Start- en runminimum zijn 3×6 A, nominaal circa 4.14 kW bij 3×230 V. Korte anti-flap/session protection blijft een executor concern.

Onder het actuele FIXED-contract mag een goedkope of negatieve marktprijs op zichzelf geen Tesla-opportunity creëren.

## Deadline charging is een MUST-constraint

Een expliciete Tesla-deadline is een harde comfort-/availability-constraint. PV blijft waar mogelijk eerste bron, maar netenergie mag worden gebruikt wanneer dat noodzakelijk is om het doel op tijd te halen. Geforceerd deadline-laden wordt pas geactiveerd wanneer de remaining-energy/time-to-deadline berekening dit vereist.

De PI Dynamic Planner Bridge v1.3.0 projecteert bij een actieve deadline een expliciet `NUMERIC_DEADLINE_TARGET`, met source `REMAINING_KWH_OVER_TIME_TO_DEADLINE`, remaining kWh, deadline en `deadlineMaxA`. Wanneer de deadline het slot bezit, is realtime PV-modulatie bewust niet de owner van het slot.

### Tijdzonecontract

Gebruikersdeadlines worden geïnterpreteerd in `Europe/Amsterdam`. Interne/API-timestamps worden als UTC ISO-8601 met `Z` behandeld. De contractregel is: lokale invoer één keer naar UTC converteren; intern absolute instants vergelijken; voor UI-weergave UTC één keer terug naar Europe/Amsterdam converteren. Een lokale tijd mag nooit alleen door het toevoegen van `Z` als UTC worden behandeld.

Voorbeeld uit de live validatie van 13 september 2026: `2026-09-13T21:30:00.000Z` is 23:30 lokale zomertijd.

## Freshness: safety versus observability

De belangrijkste architectuurles van 13 september 2026 is dat niet iedere stale timestamp dezelfde betekenis heeft.

Normale opportunity/PV-control blijft conservatief: stale of incoherente control-input kan fail-closed 0 A betekenen. Tijdens een aantoonbaar geldige actieve deadline geldt echter een andere authority-regel: een **verse PASS gate** met coherent semantic token, geldig adaptercontract, geldige elektrische command-range en een last-known connected/non-fault Tesla-state is voldoende authority om het deadline-target te blijven uitvoeren.

Daarom zijn tijdens zo'n geldige deadline stale `intent.generatedAt`, `adapter.generatedAt` en `state.sampledAt` op zichzelf **degraded observability**, geen automatische stopreden. Dit voorkomt dat verouderde Easee/upstream telemetry een harde deadline verbreekt terwijl de actuele safety gate de opdracht nog expliciet heeft gevalideerd.

De actuator rapporteert dit als degraded mode, onder andere met:

- `READY_SESSION_CONTROL_DEGRADED_DEADLINE_AUTHORITY`;
- `WRITE_OK_DEGRADED_DEADLINE_AUTHORITY`;
- `NOOP_DEGRADED_DEADLINE_AUTHORITY`;
- `degradedReason = STALE_UPSTREAM_ACCEPTED_BY_FRESH_GATE`.

### Wat blijft altijd hard fail-closed

Deadline authority is geen bypass van safety. Hard stoppen blijft verplicht bij schema mismatch, semantic-token/revision mismatch, stale gate authority, gate != PASS, ongeldig adaptercontract, ongeldige elektrische/numerieke opdracht, expliciete `offline/error/fault/disconnected/unplugged` state, ontbrekende connectivity, verlopen/ongeldige deadline, write/runtime failure of een andere situatie waarin veilige authority niet aantoonbaar is.

Belangrijk: de oplossing is **niet** de freshness-timeout willekeurig vergroten en ook niet stale checks verwijderen. Freshness is contextafhankelijk gemaakt.

## EV Power Adapter en Gate

De adapter vertaalt `targets.ev.target_W` naar een uitvoerbare stroomopdracht zonder nieuwe EMS-policy te introduceren. Conceptueel geldt `requested_A = floor(target_W / (3 × 230))`, met 6 A als minimum voor een positieve 3-fase opdracht en de geconfigureerde maximumgrens als cap.

De gate valideert schema, semantic/control revision alignment, mapping semantics, contract/safety flags, freshness en finale PASS/FAIL authority. Tijdens deadline-control is `gate.updatedAt` de kritieke freshness voor execution authority. Device-health en andere telemetry blijven daarnaast diagnostisch zichtbaar.

## EV actuator v0.2.11 / flow v0.2.12

De fysieke writer gebruikt actuatorlogica v0.2.11. De Homey Advanced Flow daaromheen is v0.2.12. Dit onderscheid is bewust: v0.2.11 bevat de deadline-gate-authority policy; v0.2.12 repareert twee flow-wiring artifacts zonder de safetylogica opnieuw te veranderen.

De actuator is de enige automatische fysieke Easee-writer. Hij verzorgt current setting, session control, idempotency en fail-closed gedrag. Een geldige 0 A-opdracht normaliseert de Easee expliciet naar 0 A. Positieve current wordt door de post-session writer fysiek afgedwongen.

### Live-enable invariant

`EM2_EV_Actuator_Live_Enabled` is een echte execution gate. Wanneer deze `false` is, rapporteert de actuator `SHADOW_NO_WRITE` en mag hij geen fysieke Easee-write uitvoeren. Een productieflow mag deze vlag daarom niet als side-effect vlak vóór de actuator naar `false` zetten.

Op 13 september werd precies zo'n achtergebleven cutover-artifact gevonden: een action card zette `EM2_EV_Actuator_Live_Enabled=false` en stuurde daarna de actuator aan. Daardoor was Pi correct, deadline-target 16 A correct en Gate PASS, maar de actuator bleef bewust in shadow. Flow v0.2.12 corrigeert dit wiring-probleem.

### Geen hardcoded actuatorversie in session routing

Een tweede gevonden artifact was een session condition die uitsluitend `EM2_EV_ACTUATOR_V0.2.9` accepteerde. Daardoor kon een nieuwere geldige actuatorstatus nooit de positieve session-write route bereiken.

De v0.2.12 flow gebruikt daarom een versie-onafhankelijke v0.2.x contractcheck en accepteert de functionele ready-statussen `READY_SESSION_CONTROL` en `READY_SESSION_CONTROL_DEGRADED_DEADLINE_AUTHORITY`. Routing moet op contract/capability/statussemantiek vertrouwen, niet op een verouderde exacte implementatieversie.

## Incident 2026-09-13: diagnoseketen

De live storing begon met een Tesla die tijdens een actieve deadline stopte. De Pi bleef 11,040 W / 16 A vragen en Gate bleef PASS. Een oudere actuator schreef toch 0 A wegens `STALE_INPUT`. Dat bewees dat de fout downstream van de planner zat.

De herstelvolgorde was:

1. v0.2.10 splitste control freshness en state freshness zodat stale Easee-state tijdens een geldige deadline niet automatisch stopte;
2. live bewijs toonde daarna `STALE_CONTROL_INPUT`: de adaptertimestamp was circa 13 minuten oud terwijl Gate actueel PASS was;
3. v0.2.11 maakte een verse PASS gate met coherent safetycontract de execution authority voor een geldige deadline en degradeerde stale upstream timestamps naar observability;
4. handmatige flow-trigger gaf vervolgens `SHADOW_NO_WRITE`, waarmee werd bewezen dat `EM2_EV_Actuator_Live_Enabled=false` nog een onafhankelijke blokkade was;
5. export van de echte Advanced Flow vond zowel de `Live=false` setter als een hardcoded v0.2.9 session gate;
6. v0.2.12 repareerde beide wiring artifacts;
7. na deploy rapporteerde de hoofdactuator `READY_SESSION_CONTROL_DEGRADED_DEADLINE_AUTHORITY` met target 16 A en Gate PASS;
8. de post-session writer rapporteerde `WRITE_OK_DEGRADED_DEADLINE_AUTHORITY`, `targetA=16` en `physicalWritePerformed=true`;
9. onafhankelijke live device-validatie bevestigde Easee `Charging`, offered 16 A, target 16 A, circa 16.1/16.18/16.2 A op de drie fasen en ongeveer 11.14 kW laadvermogen.

Dit is de volledige end-to-end PASS: **Pi policy → Power Intent → adapter → fresh PASS gate → live actuator → post-session physical write → Easee/Tesla werkelijk laden**.

## Diagnostische methode

Bij een toekomstige EV-controlstoring wordt niet direct code aangepast. Lokaliseer eerst de laag waar intended state en actual state uit elkaar gaan:

```text
1. Pi /control/current
   └─ klopt target_A / target_W / deadline ownership?
2. EM2 Power Intent
   └─ klopt NUMERIC_DEADLINE_TARGET en policyProjection?
3. Adapter
   └─ klopt requested_A en contract?
4. Gate
   └─ PASS? fresh? semantic token coherent?
5. Actuator status
   └─ LIVE/SHADOW? READY/FAIL? concrete reason?
6. Post-session status
   └─ WRITE_OK/NOOP/ABORT?
7. Easee live device state
   └─ target current, offered current, phase currents, power, charging state
```

Een planner die 16 A vraagt bewijst niet dat de auto laadt. Een actuatorstatus die READY is bewijst evenmin dat de fysieke write is uitgevoerd. De eindvalidatie moet altijd de echte Easee/device-state bevatten.

Bij Homey rate limiting worden calls geminimaliseerd. Gebruik waar mogelijk Pi/GitHub/local exports, één gerichte Homey read en exact read-back hashing bij deployments. Een Advanced Flow deployment wordt pas als geslaagd beschouwd wanneer de read-back hash exact gelijk is aan de candidate hash.

## Reconnect en periodieke reconciliation

Er is geen tweede automatische reconnect-controller nodig. Na opnieuw aansluiten loopt de normale periodieke single-writer control-keten opnieuw. Bij target 0 A normaliseert de actuator Easee naar 0 A; bij opportunity charging wordt de geldige bounded opdracht afgedwongen; bij deadline ownership wordt het deadline-target afgedwongen.

## START6 validatie

Op 12 september 2026 is bewezen dat een gepauzeerde Easee/Tesla-sessie direct kan starten op 3×6 A. Gemeten waarden lagen rond 6.01/6.03/6.05 A en circa 4.235 kW totaal. Dit is de basis voor START6/RUN6.

## Contract policy

De productie-EMS staat op `FIXED`, contract `ENGIE_3Y_2026_2029`, supplier `ENGIE`. Dynamische prijsdata mag voor shadow/analyse/replay worden gebruikt, maar mag de fixed-contract productiepolicy niet impliciet omschakelen.

## Architectuurinvarianten

```text
planner policy != device writer
Power Intent != device writer
adapter != device writer
gate != device writer
fresh PASS gate = deadline execution authority only under explicit validated conditions
stale observability != automatisch unsafe
exact één EV actuator = physical writer
READY != bewezen physical write
end-to-end PASS vereist live device validation
```

Legacy automatische Tesla-flows mogen niet parallel physical writes uitvoeren. Handmatige flows mogen alleen bestaan wanneer zij expliciet handmatig zijn en niet concurreren met automatic control.

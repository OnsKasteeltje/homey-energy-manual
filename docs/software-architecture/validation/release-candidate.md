---
component: validation
title: Release Candidate Criteria
version: 0.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-25
---

# Release Candidate Criteria

## Doel

Een Release Candidate is een reproduceerbare baseline waarin productiegedrag, recovery, idempotency en observability voldoende zijn gevalideerd om wijzigingen gecontroleerd te bevriezen.

## RC-gates

1. **Architectuurconformiteit** — actuele code/config is gedocumenteerd; diagrammen volgen code; geen SHADOW-functionaliteit wordt als ACTIVE gepresenteerd.
2. **Single-writer ownership** — per fysieke actuatorfunctie exact één automatische productiewriter; disabled/legacy kandidaatwriters zijn aantoonbaar niet concurrerend.
3. **Freshness/fail-closed** — stale P1, stale price context, source-skew en revision mismatch gedragen zich volgens contract.
4. **Restart recovery** — na Homey/app-restart keren contracttype, WW-modus, Tesla lifecycle-state, dedup/lease-state en relevante publisher-state zonder handmatige reparatie terug of degraderen veilig.
5. **Idempotency** — dubbele ticks/starts leiden niet tot dubbele fysieke writes, notificaties of history/audit-records. Voor Tesla beschermt de actieve run lease de controller tegen vrijwel gelijktijdige starts.
6. **Publisher/frontend contract** — schema/revisions/freshness worden geaccepteerd door de frontend en stale data wordt zichtbaar gedegradeerd.
7. **Rollback** — voor iedere nieuwe ACTIVE-writer bestaat een expliciet pad terug naar de vorige bewezen writer of SHADOW/read-only toestand.

## RC-PASS-definitie

Een punt is pas PASS wanneer de gemeten runtime-uitkomst is vastgelegd. Configuratie-inspectie kan aantonen dat een guard bestaat, maar vervangt geen runtime-test wanneer fysieke bijwerking, lease/idempotency of restartgedrag het risico vormt.

## Huidige baseline-status

De architectuurdocumentatie omvat zowel actieve als SHADOW/planned onderdelen. Tesla-productie is actief; de generieke Power Intent/Actuator Adapter-keten blijft SHADOW. Slimme WW-control blijft SHADOW terwijl legacy boilerwriters fysieke ownership behouden. Victron blijft planned. Daardoor zijn deze SHADOW/planned onderdelen geen blocker voor een RC van de huidige productiebaseline zolang zij geen fysieke writes uitvoeren.

## Regression triggers

Een nieuwe RC-validatie is vereist bij wijziging van fysieke writer ownership, safety/freshness guards, deadline/MUST-logica, public schema major/minor met breaking semantics, contracttype-routing, restart persistence of idempotency/lease-mechanismen.

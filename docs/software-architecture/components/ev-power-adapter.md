---
component: ev-power-adapter
title: EV Power Adapter
version: 0.1
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-26
sources:
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - docs/software-architecture/components/planner-power-intent.md
  - docs/software-architecture/decisions/ADR-004-power-intent-contract.md
  - docs/software-architecture/decisions/ADR-005-adapters-no-ems-policy.md
  - docs/software-architecture/decisions/ADR-006-single-writer.md
  - docs/software-architecture/decisions/ADR-007-shadow-before-active.md
---

# EV Power Adapter

## 1. Doel

Vertalen van numerieke `EV_target_W` Power Intent naar een theoretisch uitvoerbare Easee-laadopdracht zonder EMS-policy te dupliceren.

## 2. Scope

De adapter valideert Power Intent, koppelt deze aan revision-aligned elektrische context, vertaalt watt naar laadstroom en publiceert de berekende opdracht. In v0.1 blijft `deviceWrites=false`.

## 3. Inputs

- `EV_target_W` uit Power Intent als enige upstream power-intent.
- source revision / schema voor alignment en dedupe.
- elektrische context uit `EM2_State`, waaronder actieve fasen en bruikbare voltage/vermogen-per-A context.

Legacy requested-A signalen zijn geen upstream intent.

## 4. Outputs

Een SHADOW actuatorcommand met minimaal target-W, berekende stroom, status/reject-reason, source revision en `deviceWrites=false`.

## 5. State model

Conceptuele states: `IDLE`, `TRANSLATED`, `WAITING_FOR_ELECTRICAL_CONTEXT`, `REVISION_MISMATCH`, `FAIL_CLOSED`.

## 6. Beslislogica

Bij target 0 W wordt geen laadopdracht berekend. Bij positief target wordt W/A afgeleid uit geobserveerde elektrische context of theoretisch uit spanning × actieve fasen. De uitkomst wordt begrensd door 6 A minimum en 16 A maximum. Onder de uitvoerbare minimumgrens wordt fail-safe/deadband gedrag toegepast.

De adapter bepaalt geen opportunity, prijs-, prioriteits- of deadlinebeleid.

## 7. Procesflow

`Power Intent -> revision/schema validation -> electrical context -> W/A translation -> min/max/deadband -> dedupe -> publish SHADOW command`.

## 8. Foutafhandeling

Ontbrekende/ongeldige context, schema mismatch of revision mismatch resulteert in fail-closed output en geen device write.

## 9. Idempotency

Dedupe gebeurt op relevante source revision/input schema en toekomstige fysieke writes moeten aanvullend door de single-writer lease/write-gate beschermd zijn.

## 10. SHADOW/ACTIVE-status

v0.1 is ACTIVE SHADOW. `deviceWrites=false`; Easee ontvangt vanuit deze adapterketen geen commando.

## 11. Validatie

Voor promotie naar ACTIVE zijn minimaal nodig: runtime A/B tegen actuele laadcontext, minimum/maximum/deadband cases, revision mismatch, ontbrekende context, duplicate-start/idempotency en bewijs dat de legacy writer atomair kan worden uitgefaseerd.

## 12. Bekende beperkingen

Werkelijke device-write integratie en cut-over zijn nog niet actief. Kalibratie van geobserveerd vermogen per A blijft afhankelijk van representatieve runtime-data.

## 13. Bronbestanden

Zie YAML-frontmatter. De actuele Homey-flow/configuratie is leidend boven deze beschrijving.

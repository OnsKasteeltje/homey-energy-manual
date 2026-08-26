---
component: ww-power-adapter
title: Warm Water Power Adapter
version: 0.1
status: shadow
architecture_status: planned-shadow
last_verified: 2026-08-26
sources:
  - docs/software-architecture/components/planner-power-intent.md
  - docs/software-architecture/components/boiler.md
  - docs/software-architecture/decisions/ADR-004-power-intent-contract.md
  - docs/software-architecture/decisions/ADR-005-adapters-no-ems-policy.md
  - docs/software-architecture/decisions/ADR-006-single-writer.md
  - docs/software-architecture/decisions/ADR-007-shadow-before-active.md
---

# Warm Water Power Adapter

## 1. Doel

Vertalen van een warmwater Power Intent naar een uitvoerbare boileropdracht zonder EMS-policy opnieuw uit te voeren.

## 2. Scope

De adapter vormt de toekomstige boundary tussen `WW_target_W`/warmwater-intent en de fysieke boilerwriter. De eerste implementatie blijft SHADOW en schrijft niet naar het device.

## 3. Inputs

- warmwater Power Intent als enige upstream actuator-intent;
- source revision/schema;
- uitsluitend device-/elektrische context die nodig is voor veilige vertaling.

Opportunity-, prijs-, deadline- en minimum-draaitijdbeleid blijven upstream eigendom van Core/WW-policy.

## 4. Outputs

Een SHADOW actuatorcommand met requested target, vertaalde boileractie, status/reject-reason, source revision en `deviceWrites=false`.

## 5. State model

Conceptuele states: `IDLE`, `ON_REQUESTED`, `OFF_REQUESTED`, `HOLD`, `REVISION_MISMATCH`, `FAIL_CLOSED`.

## 6. Beslislogica

De adapter vertaalt uitsluitend de ontvangen intent naar de ondersteunde fysieke boileractie en past noodzakelijke safety/device guards toe. Hij introduceert geen eigen beslisregels voor wanneer warm water energetisch gewenst is.

Zolang Power Intent nog binair `target_on` levert, wordt dat overgangscontract ondersteund. Bij introductie van numeriek `WW_target_W` wordt watt het primaire upstream contract en blijft de fysieke boilervertaling lokaal in deze adapter.

## 7. Procesflow

`WW Power Intent -> revision/schema validation -> device constraints -> translate -> dedupe -> publish SHADOW command`.

## 8. Foutafhandeling

Onbekende intent, schema/revision mismatch of ontbrekende essentiële context resulteert in fail-closed gedrag en geen fysieke write.

## 9. Idempotency

Herhaalde identieke intent voor dezelfde source revision mag geen dubbele fysieke actie veroorzaken. Bij toekomstige ACTIVE-status wordt dit aan de single-writer write-gate afgedwongen.

## 10. SHADOW/ACTIVE-status

De adapterarchitectuur is vastgelegd voor SHADOW. Fysieke writes via deze nieuwe route zijn niet toegestaan totdat runtime-validatie en gecontroleerde cut-over zijn afgerond.

## 11. Validatie

Minimaal vereist: ON/OFF/HOLD of numerieke target-cases, revision mismatch, duplicate input, restart recovery, bewijs van geen dubbele boilerwrites en A/B vergelijking met de bestaande actieve boilerregeling.

## 12. Bekende beperkingen

Power Intent publiceert momenteel nog een binaire warmwaterintent; numeriek `WW_target_W` is nog geen volledig gevalideerd productiecontract. De adapter blijft daarom overgangscompatibel maar policy-vrij.

## 13. Bronbestanden

Zie YAML-frontmatter. De actuele Homey-flow/configuratie is leidend boven deze beschrijving.

---
component: opportunity-engine
title: Opportunity Engine
version: 0.1.0
status: shadow
architecture_status: implemented
last_verified: 2026-08-25
source:
  - docs/software-architecture/components/core.md
  - docs/software-architecture/components/price-adapter.md
  - docs/software-architecture/components/planner-power-intent.md
  - docs/energie-manager.md
---

# Opportunity Engine

## 1. Doel

De Opportunity Engine is de logische functie die beschikbare elektrische flexibiliteit koppelt aan niet-verplichte Tesla- en warmwateracties. Het is geen zelfstandige fysieke actuator en heeft geen eigen device-writer.

## 2. Scope

De actuele opportunity-logica is verdeeld over Core, contract-aware decision, WW post-goal advisor en Power Intent. Deze module beschrijft het gezamenlijke contract en de prioriteiten.

## 3. Inputs

- verse P1 import/export;
- `flex_export_budget_w` na grid- en Quatt-reserve;
- `discretionary_import_budget_w`;
- contract/price-context inclusief negative/cheap classificatie en freshness;
- Tesla connected/deadline/remaining energy;
- WW goal/state/post-goal eligibility;
- actuele revision-context.

## 4. Outputs

- Tesla opportunity intent / numeriek `EV_target_W` in SHADOW;
- WW opportunity candidate, maximaal `SHOULD` na dagdoel;
- HOLD/fail-closed wanneer budget/context niet geldig is.

## 5. State model

De engine heeft geen zelfstandig persistent state-machineobject. De relevante toestand wordt gedragen door Core state, Decision, WW state/control, Price Context en Power Intent, gekoppeld via source revision.

## 6. Beslislogica

Prioriteit is bindend:

1. safety en lokale hardwarebeveiliging;
2. comfort-baseload;
3. MUST/deadline/catch-up doelen;
4. export-opportunity;
5. negatieve/goedkope prijs-opportunity binnen importbudget;
6. HOLD/rest naar net of toekomstige batterijpolicy.

Een opportunity mag een MUST-doel nooit verdringen. Voor export-opportunity is verse P1 de autoritatieve bron. Voor prijs-opportunity moet prijscontext vers en bruikbaar zijn.

## 7. Procesflow

Zie `flows/opportunity-flow.md`.

## 8. Foutafhandeling

- stale/ongeldige P1 → exportbudget 0 W;
- stale/degraded prijscontext → prijsarbitrage uit, P1-opportunity kan blijven bestaan;
- revision mismatch → Power Intent ongeldig, EV target 0 W;
- onbekende intent → HOLD/fail-closed.

## 9. Idempotency

Power Intent en downstream adapters dedupliceren op source revision. Een identieke Core-revision mag niet leiden tot herhaalde fysieke writes; de huidige opportunityroute is bovendien SHADOW buiten de bestaande productiecontrollers.

## 10. SHADOW/ACTIVE-status

De centrale opportunity-policy en numerieke Power Intent-keten zijn SHADOW. Tesla heeft daarnaast bestaande productie-opportunitylogica in de aparte Tesla writer. WW post-goal opportunity is advisory/SHADOW. Er is nog geen generieke Opportunity Engine-writer.

## 11. Validatie

Validatie vereist minimaal: verse export → kandidaat; import zonder prijsvoordeel → geen opportunity; stale P1 → geen exporttarget; stale prijscontext → geen prijsarbitrage; MUST-deadline → opportunity ondergeschikt; revision mismatch → 0 W target.

## 12. Bekende beperkingen

De opportunityfunctie is nog over meerdere flows/modules verdeeld. Een toekomstige consolidatie mag alleen plaatsvinden zonder tweede writer te introduceren en na regressietests op Tesla- en WW-prioriteiten.

## 13. Bronbestanden

Zie YAML-frontmatter. De actuele live bron bestaat uit Core/Decision/Power Intent/Homey flows; deze module is de genormaliseerde architectuurbeschrijving daarvan.

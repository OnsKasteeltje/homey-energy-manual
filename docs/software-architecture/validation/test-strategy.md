---
component: validation
title: Teststrategie Softwarearchitectuur
version: 0.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-25
---

# Teststrategie Softwarearchitectuur

## Doel

Validatie bewijst dat code, runtimegedrag, public state, websiteweergave en documentatie dezelfde architectuur beschrijven. Tests worden uitgevoerd op de laag waar het risico ontstaat; een SHADOW-resultaat telt niet als fysieke actuatorvalidatie.

## Testlagen

1. **Static/config validation** — flow enabled/broken status, schema's, manifest, frontmatter en repository checks.
2. **Contract validation** — revision alignment, JSON Schema, freshness, fail-closed gedrag en producer/consumer compatibility.
3. **Runtime smoke tests** — expliciete flow-run, state transitions, idempotency en lifecyclegedrag.
4. **E2E tests** — gebruiker/config ingress → Homey → Core/control → Publisher → website en, waar van toepassing, fysieke actuator/readback.
5. **Restart/recovery tests** — Homey/app/repository publicatie herstart zonder handmatige state-reparatie.
6. **Shadow-to-active tests** — eerst read-only/SHADOW, vervolgens gecontroleerde writer-cut-over met rollbackpad.

## Algemene invarianten

- maximaal één fysieke writer per actuatorfunctie;
- dubbele Core ticks/flow-starts veroorzaken maximaal één fysieke actie en één audit/history-effect;
- stale P1 sluit flex-export fail-closed;
- afgeleide house/PV-invaliditeit mag directe device-metingen niet ongeldig maken;
- MUST/deadline gaat vóór economische opportunity;
- revision mismatch produceert geen nieuw fysiek target;
- website/config mag nooit rechtstreeks een device schrijven;
- procesdiagrammen worden bij relevante codewijziging opnieuw tegen de code gecontroleerd.

## Componentgerichte minimumtests

| Component | Minimumvalidatie |
|---|---|
| Core | single-reader, P1 freshness, source-skew, revision output |
| Publisher | revision/heartbeat publish, retry, public state contract |
| Tesla | deadline, opportunity, target stop, run lease, no duplicate Easee write |
| Boiler | mode gate, deadline, legacy writer ownership, HYBRID disabled/no duplicate writer |
| Price | FIXED zonder PBTH; DYNAMIC met verse context; stale fail-closed voor prijsarbitrage |
| Opportunity | MUST precedence, exportbudget, price budget, revision mismatch |
| Fingerprints | ground-truth windows, false-positive controle, confidence gate, no actuator write |
| Victron | vóór ACTIVE: readback, stale/reboot/idempotency/setpoint guard |

## Bewijsvoering

Een PASS vermeldt inputconditie, timestamp/revision, verwachte output, gemeten output en fysieke readback indien de test een actuator betreft. Alleen 'flow gestart' is onvoldoende voor een fysieke E2E-PASS.

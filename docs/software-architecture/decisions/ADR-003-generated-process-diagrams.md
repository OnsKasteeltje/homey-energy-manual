---
title: ADR-003 - Process diagrams are generated from the process model
date: 2026-08-26
status: accepted
---

# ADR-003 - Process diagrams are generated from the process model

## Context

Hand-maintained diagrams can drift from implementation and create contradictory architecture documentation.

## Besluit

Process diagrams are generated from versioned process models and are not maintained independently as free-form Mermaid sources in publication content.

## Alternatieven

Manual diagram maintenance was rejected because it permits silent divergence from code and process contracts.

## Consequenties

Diagram changes must originate from the process model or its generator. CI rejects legacy hand-maintained Mermaid where generation is required.

## Validatie / heroverweging

`generate_process_diagrams.py --check` and publication QA enforce the rule.

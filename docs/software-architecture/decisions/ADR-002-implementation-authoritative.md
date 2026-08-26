---
title: ADR-002 - Implementation is authoritative over documentation
date: 2026-08-26
status: accepted
---

# ADR-002 - Implementation is authoritative over documentation

## Context

Architecture documentation can become stale when implementation changes faster than prose or diagrams.

## Besluit

The current implementation, contracts and configuration are authoritative. Documentation may only describe behavior that is implemented or explicitly marked as planned/SHADOW.

## Alternatieven

Treating architecture documents as prescriptive truth was rejected because runtime behavior must never be inferred from outdated documentation.

## Consequenties

Every relevant documentation change records source paths and `last_verified`. Differences between implementation and documentation are defects to be corrected before release.

## Validatie / heroverweging

CI QA and code review verify source references, architecture status and runtime validation evidence.

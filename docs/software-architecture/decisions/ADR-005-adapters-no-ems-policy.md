---
title: ADR-005 - Device adapters contain no EMS policy
date: 2026-08-26
status: accepted
---

# ADR-005 - Device adapters contain no EMS policy

## Context

Policy duplicated inside adapters makes control behavior difficult to reason about and can conflict with the planner.

## Besluit

Device adapters contain only contract validation, electrical/device translation, safety constraints, idempotency and write execution. They do not decide opportunity, priority, price strategy or deadline policy.

## Alternatieven

Embedding local optimisation in adapters was rejected because it creates multiple policy owners.

## Consequenties

EMS policy remains upstream. Adapter behavior becomes deterministic for a given intent and device state.

## Validatie / heroverweging

Code review and adapter tests verify that policy inputs other than the explicit intent contract are not used to derive demand.

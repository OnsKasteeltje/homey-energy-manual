---
title: ADR-006 - Single writer per physical device
date: 2026-08-26
status: accepted
---

# ADR-006 - Single writer per physical device

## Context

Multiple physical write routes can cause duplicate actions, race conditions and hard-to-debug device state.

## Besluit

Each physical device has exactly one active write owner. Upstream components publish intent or state but never bypass the designated adapter/controller write route.

## Alternatieven

Allowing multiple flows to write directly to the same device was rejected because ordering and idempotency cannot be guaranteed globally.

## Consequenties

Legacy write routes must be disabled or remain SHADOW before a new adapter becomes ACTIVE. Lease/idempotency protection remains mandatory at the writer boundary.

## Validatie / heroverweging

RC tests verify single-writer behavior, duplicate-start handling and absence of duplicate physical writes.

---
title: ADR-007 - SHADOW before ACTIVE
date: 2026-08-26
status: accepted
---

# ADR-007 - SHADOW before ACTIVE

## Context

New control paths can be logically correct yet unsafe or operationally incompatible with live device behavior.

## Besluit

Every new physical control path must first run in SHADOW with `deviceWrites=false`, publish its calculated output, and collect runtime evidence before ACTIVE promotion.

## Alternatieven

Direct activation after static testing was rejected because it skips observation under real household conditions.

## Consequenties

Promotion requires explicit runtime validation evidence and a rollback path. SHADOW output must be observable enough for A/B comparison with the active path.

## Validatie / heroverweging

Release-candidate gates record SHADOW evidence and an explicit PASS before enabling physical writes.

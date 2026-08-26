---
title: ADR-004 - Power Intent is the only upstream power-control contract
date: 2026-08-26
status: accepted
---

# ADR-004 - Power Intent is the only upstream power-control contract

## Context

Multiple device-specific requested-current or legacy control signals create duplicated policy and inconsistent prioritisation.

## Besluit

`EV_target_W`, `WW_target_W` and equivalent device power intents are the only upstream power-control contracts accepted by device power adapters. Legacy requested-A logic is not an upstream control contract.

## Alternatieven

Passing amperage or device-specific commands through the EMS was rejected because it couples policy to device implementation details.

## Consequenties

The planner decides power intent in watts. Adapters translate intent into electrically and device-valid commands without re-running EMS policy.

## Validatie / heroverweging

Adapter tests must demonstrate that outputs depend on Power Intent plus device/electrical constraints only.

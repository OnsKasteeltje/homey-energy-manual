# Quooker — Core integration prerequisite

Status: **BLOCKED FOR DIRECT EVENT-DRIVEN USE**

Date: 2026-08-29

## Project decision

The current Quooker signal path must **not** be used directly as an event-driven source for Core v0.11b or the Core Snapshot Aggregator.

`EM_Quooker_Last_Sample` is currently coupled to the frequent P1/heartbeat path. Using that variable directly as an aggregator trigger would cause a high-frequency wake-up and refresh of the Quooker input group. That would add avoidable Logic reads and fan-out, undermining the Homey low-load/throttling objective.

Therefore Quooker integration is explicitly **blocked until the producer/commit-marker design has been adapted**.

## Required adaptation before use

Before Quooker may be enabled as an event-driven Core input, provide a low-frequency semantic commit marker that changes only when the effective Quooker state meaningfully changes. The design must:

- decouple the Core/aggregator trigger from the frequent P1 heartbeat;
- avoid a trigger on every `EM_Quooker_Last_Sample` update;
- preserve the existing Quooker freshness information separately;
- refresh the Quooker group only on meaningful semantic changes, with a low-frequency reconciliation path as safety net;
- avoid retry loops and broad polling;
- demonstrate no material increase in Homey CPU load or 429/rate-limit frequency.

## Current SHADOW behavior

Until that change is implemented and validated, the v0.11b SHADOW aggregator must not wire `EM_Quooker_Last_Sample` as an event trigger. Quooker values may only be collected through the deliberately low-frequency reconciliation path used for SHADOW/parity testing.

This is a **hard prerequisite for production cut-over of Core v0.11b**. Quooker must not be treated as implementation-ready merely because its Logic variables already exist.
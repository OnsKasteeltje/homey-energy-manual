---
component: operations
title: EV Control Observability
version: 0.1
status: active
architecture_status: implemented
last_verified: 2026-08-28
---

# EV Control Observability

## Purpose

Provide a permanent, externally readable and control-neutral view of the EV control chain so runtime validation never depends on temporary Homey probe flows.

## Runtime flow

`EM v2 | 81 Observability | EV Control Status v0.1`

Homey Advanced Flow ID: `f6edba38-ddf1-45e5-890e-c183aa2055d5`

The flow is event-driven on changes of either:

- `EM2_EV_Adapter_Gate`
- `EM2_EV_Actuator_Status`

A 2-second settle is applied before reading one Logic snapshot. The flow performs no device reads and no physical device writes.

## Published contract

The flow publishes `docs/data/ev-control-status.json` with schema `EM2_EV_CONTROL_STATUS_V0.1`.

The payload exposes:

- current Power Intent revision;
- `EV_target_W` and EV intent status;
- adapter `requested_A` and adapter revision;
- current `EM2_State` revision;
- EV Gate PASS/FAIL plus source/intent/state/core revisions;
- actuator status, actuator revision, LIVE flag, target current and whether the actuator reports a physical write;
- a derived `coherent` boolean that is true only when intent, adapter, state and all Gate revisions match.

The file is observability-only. It is not an EMS input and must never be consumed as a control dependency.

## Safety boundary

This observability path MUST NOT:

1. enable LIVE control;
2. start the EV actuator;
3. write to Easee or any other device;
4. weaken Gate checks;
5. become an upstream input to Power Intent, Adapter, Gate or Actuator.

For a positive EV LIVE smoke, the externally published status must show a fresh positive `targetW`, the expected `requestedA`, Gate `PASS`, and `coherent=true` before LIVE is enabled.

## Load behaviour

Each event performs one `Homey.logic.getVariables()` call. Publication uses a cached GitHub blob SHA: steady state is one GitHub PUT for a changed status; a GitHub GET is used only for cache initialization or conflict recovery. Duplicate payloads are skipped.

Because revision coherence is safety evidence, a new natural Gate revision may legitimately produce one status publication. This exception is documented in the Homey API/Load Map and must be reviewed if throttling evidence points at this path.

## Temporary-flow policy

Temporary EV/Tesla runtime probes, LIVE-switch flows and one-shot current test flows are not part of the architecture. Once a test is completed, they must be deleted rather than left disabled. The permanent observability contract above replaces their readback purpose.

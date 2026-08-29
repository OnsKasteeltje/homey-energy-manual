# Homey → GitHub bulk migration batch — 2026-08-28

## Rule

Bulk **capture** is allowed without a smoke test. Runtime **promotion/change** remains gated: deploy one flow or one tightly coupled chain, run one targeted smoke, record explicit PASS/FAIL, and continue only on PASS.

> Current runtime note: this inventory started on 2026-08-28 and contains historical versions. The authoritative current critical baseline is `src/homey/runtime-sync-baseline-2026-08-30.md`. Older names below must not be interpreted as the active production version where superseded.

## Current critical production baseline

- Core: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`
- Power Intent: `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD`
- Planner: `EM v2 | 45 Planner | 24h Energy Plan v0.4.7 SHADOW LOW-LOAD`
- Planner Shadow Publisher: `EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD`
- WW state: `EM v2 | 15 State | Warm Water Observer v0.2`
- WW adapter: `EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW`
- WW gate: `EM v2 | 80 Validation | WW Power Adapter Gate v0.2 TARGETED-READ`
- WW actuator: `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE`
- EV goal input: `EM v2 | 10 Input | EV Deadline Goal Adapter v0.1`
- EV adapter: `EM v2 | 60 Adapter | EV Power v0.1.1 TARGETED-READ SHADOW`
- EV gate: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ`
- EV actuator: `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP`

These names/versions were reconciled against Homey on 2026-08-30. See the runtime sync baseline for Homey flow IDs and safety notes.

## Previously captured / source-managed history

The following entries record earlier migration checkpoints and are retained as history, not as the active production baseline:

- Core: `EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)`
- Power Intent: `EM v2 | 20 Power Intent | P1 v0.2.2 (Public decoupled)`
- Planner: `EM v2 | 45 Planner | 24h Energy Plan v0.4.4 SHADOW LOW-LOAD`
- Publisher: `EM v2 | 40 Data | Publisher v1.0.7 (GitHub managed)`
- Decision: `EM v2 | 40 Decision | Contract-aware v0.2`
- Context: `EM v2 | 30 Context | Contract Price Adapter v0.8`
- Context: `EM v2 | 30 Context | Price + PV v0.6.1 SHADOW`
- Adapter: `EM v2 | 60 Adapter | EV Power v0.1 SHADOW`
- Actuator: `EM v2 | 60 Actuator | EV Power v0.2 LIVE OWNERSHIP`
- Adapter: `EM v2 | 60 Adapter | WW Power v0.1 SHADOW`
- Actuator: `EM v2 | 60 Control | Warm Water Actuator v0.8 HYBRID`

## Supporting group source capture — completed 2026-08-30

The following supporting flows were read directly from Homey as one capture batch and transferred to GitHub source control. Runtime enabled/disabled state and trigger contracts are recorded in `src/homey/captures/supporting-flows-2026-08-30.md`; HomeyScript bodies are stored alongside it under `src/homey/captures/`.

- `EM v2 | 05 Config | EMS Settings Sync v0.3 low-load`
- `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered`
- `EM v2 | 06 Freshness | Day-Night Normalizer v0.1.1`
- `EM v2 | 70 Planner | WW Scheduling SHADOW v0.2`
- `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW`
- `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent`
- `EM v2 | 70 History | Control Audit v0.4 low-load`
- `EM v2 | 70 History | Day Series v0.6.1 TARGETED LOCAL SAMPLER`
- `EM v2 | 72 History | Immutable Day Archive v0.1`
- `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first`

Capture is documentation/source-management only. No Homey flow was started, enabled, disabled, or changed as part of this batch.

## Remaining active/relevant capture set

1. Other `80/81 Validation/Observability` flows not already included in the critical WW/EV control baseline.
2. Standard EMS flows such as Boiler Night OFF / morning fallback only where still part of the active architecture.

## Explicit exclusions from active source-of-truth

Do not promote as active production source:

- `[ROLLBACK]`
- `[FAILED-DIRECT-API]`
- `[RETIRED DUPLICATE]`
- `TEMP ... [DONE]`
- superseded Tesla legacy controller flows

These may later be archived under `archive/` or `tests/fixtures/` where useful for regression evidence.

## Load-map requirement

For every captured flow, record during refactor: trigger frequency, collection reads (`getVariables`, `getDevices`), targeted reads, Logic writes, device writes, HTTP/inter-app calls, downstream variable-change triggers, idempotency, and expected event fan-out. Migration priority should favor reduction of broad collection reads and multiplicative change-event cascades.

# Homey EMS Core runtime source

This directory is the versioned source baseline and change staging area for the Homey Advanced Flow **EM v2 | 00 Core Tick**.

- Homey Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- **Current verified live Homey runtime (2026-09-04): `EM v2 | 00 Core Tick | v0.11i PINNED SOURCE`**
- **Exact live source baseline: `core-v0.11i.live-homey.js`**
- Live trigger topology: every 5 minutes plus manual start.
- Live publication version: `EM2_CORE_STATE_V0.11i`; publication schema `2.12`.
- Safety: Core performs no physical device writes; physical control remains downstream of Power Intent / adapter / gate / actuator ownership.

## Current live v0.11i

Direct Homey inspection on 2026-09-04 verified the complete Advanced Flow and its HomeyScript. The exact executable HomeyScript was captured directly from that live flow as `src/homey/core/core-v0.11i.live-homey.js`. This file is the authoritative Core source for current documentation and future patches until a newer live Core is explicitly reconciled.

Important runtime characteristics observed directly in v0.11i:

- Core still performs one broad `Homey.logic.getVariables()` enumeration every 5-minute Core run, alongside targeted reads of ten named devices. This remains a Homey-load/throttling concern for later Pi migration.
- Core consumes `WW_Boilermodus` directly and must preserve contract-selection / WW-source separation.
- Planner input includes `EM2_ContractPrice_Context`, `EM2_Contract_Type` and `TEMP_PBTH_JSON_BUFFER`.
- Legacy M7 context variables remain fallback context.
- Quooker Logic variables remain part of state/diagnostics and `knownMeasuredLoadW`; P1 remains authoritative for flex budget.
- Planner compatibility includes `EM2_ENERGY_PLAN_24H_V0.4.9` and `EM2_ENERGY_PLAN_24H_V0.5.0`; v0.5.0 is the current live planner.
- Planner Tesla deadline admission uses `plannerTeslaProjectedGridW = gridW + 4140 W` and requires projected grid `<= 4000 W`; MUST latest-start catch-up retains precedence.
- WW logic contains the bounded thermostat-verification path and does not infer a temperature goal merely from low power.
- AEG laundry semantics treat explicit idle/ready/finished states as inactive even if stale cycle/time-to-end values remain.

## Source parity

**PASS — 2026-09-04.** `src/homey/core/core-v0.11i.live-homey.js` was written from the HomeyScript action of live Core flow `227f8d3b-7551-46dd-837d-1b8c69add824`, not reconstructed from candidate patches or historical documentation.

The live Advanced Flow still contains an old note card mentioning v0.11g / commit `bd4edecc`. That note is stale metadata; current runtime identity comes from the flow name and executable HomeyScript (`PUB_VERSION='EM2_CORE_STATE_V0.11i'`).

The authoritative current reconciliation record is:

`docs/architecture/homey-runtime-baseline-2026-09-04.md`

The previous `homey-runtime-baseline-2026-08-30.md` and `core-v0.11f.live-homey.js` remain historical audit evidence only.

## Change rule

Never reconstruct or simplify the Core script while deploying a change. Start from the **complete current live flow**, make the smallest reviewable diff, validate that all existing functional sections are retained, and only then deploy the complete script to the existing Advanced Flow.

Before any Core Homey mutation:

1. capture/fetch the complete live Advanced Flow;
2. preserve it as the rollback unit;
3. apply only the reviewed patch to that complete runtime;
4. compare the resulting full script against the captured live baseline;
5. perform one Advanced Flow update only;
6. smoke only when Homey is not rate-limited.

For fan-out optimisation, timestamps/heartbeat metadata must not create downstream Logic change events when the semantic state or control intent is unchanged. Public-state publication freshness is transport metadata and must not be used as an internal control trigger.

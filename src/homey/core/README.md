# Homey EMS Core runtime source

This directory is the versioned source baseline and change staging area for the Homey Advanced Flow **EM v2 | 00 Core Tick**.

- Homey Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Historical captured runtime: `core-v0.10.14.js`
- **Current verified live Homey runtime (2026-08-30): `EM v2 | 00 Core Tick | v0.11f (Planner Tesla Headroom)`**
- **Exact live source baseline: `core-v0.11f.live-homey.js`**
- Live trigger topology: every 5 minutes plus manual start.
- Live publication version: `EM2_CORE_STATE_V0.11f`; publication schema `2.12`.
- Safety: Core performs no physical device writes; physical control remains downstream of Power Intent / adapter / gate / actuator ownership.

## Current live v0.11f

Direct Homey inspection on 2026-08-30 verified the complete Advanced Flow and its HomeyScript. The exact HomeyScript was subsequently captured directly from that same live flow and committed unchanged as `src/homey/core/core-v0.11f.live-homey.js`. This file is the authoritative Core source for documentation and future patches until a newer live Core is explicitly reconciled.

v0.11f retains the established WW and thermostat-verification semantics and changes Planner Tesla admission to projected-grid headroom:

`plannerTeslaProjectedGridW = gridW + 4140 W`

Planner Tesla deadline admission is allowed only when projected grid remains `<= 4000 W`. MUST latest-start catch-up retains precedence.

Important runtime characteristics observed directly in the live script:

- Core still performs one broad `Homey.logic.getVariables()` enumeration every 5-minute Core run, alongside targeted device reads. This remains a separate Homey-load/throttling concern.
- Core consumes `WW_Boilermodus` directly and must therefore preserve contract-selection / WW-source separation.
- Core consumes `EM2_ContractPrice_Context`, `EM2_Contract_Type` and `TEMP_PBTH_JSON_BUFFER` for Planner input; it does not consume `EMS_ContractType` directly.
- Core still reads legacy M7 context variables as fallback context.
- Live v0.11f includes Quooker Logic variables in state/diagnostics and `knownMeasuredLoadW`; P1 remains authoritative for flex budget.
- Planner WW uses v0.4.9 slot intent subject to realtime Core safety.
- Planner Tesla admission uses projected-grid headroom; MUST deadline catch-up remains authoritative.

## Source parity

**PASS — 2026-08-30.** `src/homey/core/core-v0.11f.live-homey.js` was written from the HomeyScript action of live Core flow `227f8d3b-7551-46dd-837d-1b8c69add824`, rather than reconstructed from patches or documentation. GitHub readback confirms the file contains `PUB_VERSION='EM2_CORE_STATE_V0.11f'` and the v0.11f projected-grid admission logic.

A user-provided manual copy of the same live HomeyScript was also retained as independent reconciliation evidence during the session. Older v0.11c/v0.11d preparation and smoke files remain audit/history only and must not be treated as current live runtime.

The authoritative runtime/status reconciliation record is:

`docs/architecture/homey-runtime-baseline-2026-08-30.md`

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

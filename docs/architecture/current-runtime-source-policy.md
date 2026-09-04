# Current runtime source policy

Status: **normative for current-state software documentation and Pi migration work**.

This policy prevents historical Homey preparation, candidate, patch, smoke, rollback and validation material from being interpreted as the current EMS architecture.

## Authority order

When generating or updating current-state architecture documentation or preparing the Pi EMS migration, use sources in this order:

1. `docs/architecture/homey-runtime-baseline-2026-09-04.md` for runtime classification and current component ownership.
2. Exact reconciled live runtime source files named by that baseline.
3. Current production source files explicitly named by the runtime baseline.
4. Design/preparation Markdown only for historical rationale or explicitly future work.

The previous `docs/architecture/homey-runtime-baseline-2026-08-30.md` is historical audit evidence and is no longer the current runtime authority.

If a historical file conflicts with the current runtime baseline or exact live runtime source, the current baseline/live source wins.

## Core

Current live Core is:

- Flow: `EM v2 | 00 Core Tick | v0.11i PINNED SOURCE`
- Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Exact source: `src/homey/core/core-v0.11i.live-homey.js`
- Publication version: `EM2_CORE_STATE_V0.11i`
- Schema: `2.12`

The old note card in the live Advanced Flow referring to v0.11g / commit `bd4edecc` is stale metadata; the executable HomeyScript action and flow name are authoritative for current runtime identity.

Older Core candidate, patch, precheck, regression, smoke and baseline files are historical development evidence unless the current runtime baseline explicitly references a fact from them. They are **not** current Core source.

Current Core documentation must preserve these live facts:

- five-minute Core cadence;
- Core performs no physical device writes;
- Core reads the ten named devices used by the current runtime and still performs one broad `Homey.logic.getVariables()` enumeration per run;
- `WW_Boilermodus` is a direct safety-critical input;
- Planner price inputs include contract-price context, contract type and the PBTH price buffer;
- legacy M7 variables remain fallback context;
- Quooker Logic data is present in state/diagnostics and `knownMeasuredLoadW`;
- P1 remains authoritative for flex budget and fails closed when stale;
- Planner compatibility includes v0.4.9 and v0.5.0 slot contracts;
- Planner Tesla admission uses projected grid headroom `gridW + 4140 W <= 4000 W` while MUST latest-start catch-up retains precedence;
- WW goal/thermostat logic includes confirmed-heating and bounded low-power verification;
- AEG laundry semantics treat explicit idle/ready/finished states as inactive even when retained cycle/time-to-end signals exist.

## Current orchestration/config/context

Current-state documentation must use the 2026-09-04 runtime baseline classifications. In particular:

- Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER remains an active shadow component.
- Planner v0.5.0 SHADOW LOW-LOAD is the active planner; exact source is `src/homey/planner/energy-plan-24h-v0.5.0.live-homey.js`.
- Settings Sync v0.4.1 TARGETED 15-MIN LOW-LOAD is the current config sync; exact source is `src/homey/config/ems-settings-sync-v0.4.1.live-homey.js`.
- Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD is the current contract-price bridge.
- Publisher v1.0.13 CONTROL EVIDENCE LOW-LOAD is the current public-state publisher; exact source is `src/homey/publication/publisher-v1.0.13.live-homey.js`.
- Planner Shadow publisher v0.4 remains a current publication component.

Older contract/price variants, rollback flows, replaced Tesla flows, TEMP/DONE/ONE-SHOT flows and validation-only flows must never be drawn as current production ownership unless the runtime baseline is updated to promote them.

## Current EV chain

Current EV ownership is:

- Power Intent: `EM v2 | 20 Power Intent | P1 v0.2.4 DUAL-SEMANTIC LOW-LOAD`.
- Shadow adapter: `EM v2 | 60 Adapter | EV Power v0.1.2 MIN7 TARGETED-READ SHADOW`, exact source `src/homey/adapters/ev-power-v0.1.2.live-homey.js`.
- Validation gate: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.2 MIN7 TARGETED-READ`, exact source `src/homey/validation/ev-power-adapter-gate-v0.2.2.live-homey.js`.
- Physical writer: `EM v2 | 60 Actuator | EV Power v0.2.3 MIN7 TARGETED-READ LIVE OWNERSHIP`, exact source `src/homey/actuators/ev-power-v0.2.3.live-homey.js`.

The current executable mapping is fixed 3×230 V at 690 W/A with 7 A minimum. Adapter/gate fail closed below that threshold; the actuator accepts 0 A or integer 7–16 A and requires an aligned PASS gate before a non-zero write.

## Diagram rule

Every process diagram labelled as current, live, implemented, production or as-is must be derived from the current runtime baseline plus the corresponding current source. Historical/candidate diagrams must be explicitly labelled historical, candidate, future or validation.

## Update rule

Whenever a live Homey component is promoted to a newer version:

1. capture/reconcile the live runtime;
2. store the exact live source in GitHub where applicable;
3. update the current runtime baseline classification and exact source reference;
4. update this policy if current version, ownership or authority changes;
5. perform a post-update Homey inventory and GitHub readback;
6. only then certify Homey/GitHub sync and regenerate current-state documentation or continue Pi migration.

This policy intentionally allows historical Markdown to remain in Git history/repository for auditability without allowing it to contaminate current-state documentation.
# Current runtime source policy

Status: **normative for current-state software documentation**.

This policy prevents historical Homey preparation, candidate, patch, smoke, rollback and validation material from being interpreted as the current EMS architecture.

## Authority order

When generating or updating current-state architecture documentation, use sources in this order:

1. `docs/architecture/homey-runtime-baseline-2026-08-30.md` for runtime classification and current component ownership.
2. Exact reconciled live runtime source files, where available.
3. Current production source files explicitly named by the runtime baseline.
4. Design/preparation Markdown only for historical rationale or explicitly future work.

If a historical file conflicts with the runtime baseline or exact live runtime source, the runtime baseline/live source wins.

## Core

Current live Core is:

- Flow: `EM v2 | 00 Core Tick | v0.11f (Planner Tesla Headroom)`
- Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Exact source: `src/homey/core/core-v0.11f.live-homey.js`
- Publication version: `EM2_CORE_STATE_V0.11f`
- Schema: `2.12`

All Core v0.11a/v0.11b/v0.11c/v0.11d candidate, patch, precheck, regression, smoke and baseline files are historical development evidence unless the runtime baseline explicitly references a fact from them. They are **not** current Core source.

Current Core documentation must preserve these live facts:

- five-minute Core cadence;
- Core performs no physical device writes;
- Core still performs one broad `Homey.logic.getVariables()` enumeration per run;
- `WW_Boilermodus` is a direct safety-critical input;
- Planner price inputs include `EM2_ContractPrice_Context`, `EM2_Contract_Type` and `TEMP_PBTH_JSON_BUFFER`;
- legacy M7 variables remain fallback context;
- Quooker Logic data is present in state/diagnostics and `knownMeasuredLoadW`;
- P1 remains authoritative for flex budget;
- Planner Tesla admission uses projected grid headroom `gridW + 4140 W <= 4000 W` while MUST latest-start catch-up retains precedence.

## Current orchestration/config/context

Current-state documentation must use the runtime baseline classifications. In particular:

- Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER is an active shadow component, not obsolete merely because its name contains SHADOW.
- Planner v0.4.9 SHADOW LOW-LOAD is the active planner.
- Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD is the current config sync.
- Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD is the current contract-price bridge.
- Publisher v1.0.12 and Planner Shadow publisher v0.4 are current publication components.

Older contract/price variants, rollback flows, replaced Tesla flows, TEMP/DONE/ONE-SHOT flows and validation-only flows must never be drawn as current production ownership unless the runtime baseline is updated to promote them.

## Diagram rule

Every process diagram labelled as current, live, implemented, production or as-is must be derived from the current runtime baseline plus the corresponding current source. Historical/candidate diagrams must be explicitly labelled historical, candidate, future or validation.

## Update rule

Whenever a live Homey component is promoted to a newer version:

1. capture/reconcile the live runtime;
2. update the runtime baseline classification;
3. update the exact/current source reference;
4. update this policy only if component ownership or authority order changes;
5. only then regenerate current-state software documentation.

This policy intentionally allows historical Markdown to remain in Git history/repository for auditability without allowing it to contaminate current-state documentation.
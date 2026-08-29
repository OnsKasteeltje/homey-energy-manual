# Core → Power Intent stage 2: public-state decoupling

Status: **PREPARED, NOT DEPLOYED**

Date: 2026-08-29

## Problem

`EM2_Public_State` is intentionally not semantic-suppressed in active Core v0.10.16 because its heartbeat/freshness metadata must continue to advance. Power Intent is currently triggered by `EM2_Public_State` changes. Therefore freshness-only Core publication updates can wake the complete Power Intent / Gate / Adapter chain even when EMS control semantics did not change.

This is the remaining stage-2 fan-out issue already identified in `core-v0.10.15-fanout.patch.md`.

## Goal

Keep `EM2_Public_State` as the externally visible freshness/publication heartbeat, but remove it as an internal control trigger.

Power Intent must execute only when the semantic Core control revision changes, not when publication timestamps or freshness-only metadata change.

## Proposed trigger contract

1. Core remains the single 5-minute telemetry reader.
2. Core continues updating `EM2_Public_State` for publication freshness.
3. Power Intent no longer triggers on `EM2_Public_State changed`.
4. Power Intent triggers on a dedicated semantic Core signal, preferably the existing semantic `EM2_Decision` change event if its revision contract is sufficient; otherwise introduce a compact `EM2_Control_Revision` scalar/string owned by Core.
5. Power Intent still reads the authoritative state/decision/control inputs required for revision-coherence validation before producing output.
6. If the semantic trigger value is unchanged, no Power Intent execution occurs.

## Preferred implementation

Prefer **existing `EM2_Decision changed`** over adding a new variable, provided the runtime payload already carries the Core revision needed by the P1 coherency guard.

If `EM2_Decision` cannot represent all semantic changes that legitimately affect Power Intent, add:

`EM2_Control_Revision`

with a value that changes only when the normalized control-relevant tuple changes, for example:

```text
coreRevision|decisionRevision|wwControlRevision
```

Do not include timestamps, ages, publication counters, generatedAt or heartbeat fields.

## Expected load reduction

Current behaviour can execute the Power Intent cascade after every `EM2_Public_State` refresh, including freshness-only refreshes. Stage 2 removes those non-semantic executions.

The downstream chain affected is:

```text
Power Intent
  -> P1 Pre-EV Gate
  -> EV Power Adapter
  -> EV Adapter Gate
      -> EV Power Actuator (LIVE=false: Logic-only)
      -> EV Control Status observability
```

The exact reduction depends on how often Core control semantics actually change, but steady-state idle periods should drop from one full downstream cascade per 5-minute heartbeat to zero cascades unless the semantic control state changes.

## Safety constraints

- No actuator ownership changes.
- No Easee, boiler, Victron, Quatt or other physical device writes are added.
- EV Actuator LIVE guard and revision-coherence requirements remain unchanged.
- `EM2_Public_State` publication heartbeat remains intact for website/freshness consumers.
- Fail-closed behaviour remains unchanged.
- Do not enable Watchdog, Day Series, Immutable Day Archive or other currently isolated load sources during this change.

## Deployment gate

1. Capture the exact active Power Intent v0.2.2 runtime source before modification.
2. Confirm whether `EM2_Decision` change covers every control-relevant input consumed by Power Intent.
3. Change only the trigger contract; preserve P1 calculations/output schema.
4. Run one targeted SHADOW smoke.
5. Verify a freshness-only `EM2_Public_State` update does **not** execute Power Intent.
6. Verify one real semantic Core change executes Power Intent exactly once and downstream gates/adapters remain coherent.
7. Record explicit PASS/FAIL before any further Homey runtime changes.

## Baseline note

The 1-hour throttling baseline on 2026-08-29 failed because the single permitted minimal Homey status probe still returned `Too many requests`. Therefore this stage-2 change is prepared from GitHub evidence only; no additional Homey polling is part of this preparation.

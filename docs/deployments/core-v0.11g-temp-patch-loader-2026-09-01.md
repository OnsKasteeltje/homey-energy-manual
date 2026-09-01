# Core v0.11g temporary patch-loader deployment — 2026-09-01

Status: **DEPLOYED TEMPORARILY / SHADOW / NO PHYSICAL WRITES**

Flow: `EM v2 | 00 Core Tick | v0.11g TEMP PATCH LOADER`
Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
Cadence: unchanged, every 5 minutes plus manual start card.

## Why temporary

The exact integrated v0.11g candidate was built and fully validated in GitHub CI. During transfer of the large inline HomeyScript payload, an incomplete/corrupted inline payload was detected. It was immediately replaced by a small fail-fast loader rather than leaving an uncertain Core runtime in place.

The loader fetches the canonical exact v0.11f source from GitHub `main`, requires each expected baseline fragment to occur exactly once, applies the same four substitutions used by the offline-tested v0.11g build, then executes the patched source in an async wrapper.

## Four guarded substitutions

1. Core header v0.11f -> v0.11g candidate label.
2. `PUB_VERSION` -> `EM2_CORE_STATE_V0.11g`.
3. v0.4.9-only Planner parser -> validated v0.4.9/v0.5.0 compatibility parser.
4. Planner policy label -> `PLANNER_V0.4.9_V0.5.0_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY`.

## Safety / load

- Core remains SHADOW/read-only and performs no physical device writes.
- Existing Homey device/Logic access inside Core is unchanged.
- No new Homey API reads, triggers, or device writes were introduced by the loader.
- Temporary cost: one raw GitHub GET per 5-minute Core execution.
- Manual smoke-run intentionally not used; validation should rely on the natural Core tick and subsequent GitHub publication.

## Exit criterion

Replace this temporary loader with the exact validated inline v0.11g candidate once the large-payload deployment path can preserve the generated source byte-for-byte. After replacement, remove the extra recurring GitHub GET.

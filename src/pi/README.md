# Raspberry Pi EMS migration preparation

Status: **PREPARED / NOT DEPLOYED / NO PHYSICAL WRITES**  
Last sync: 2026-09-15

## Purpose

This directory is the canonical repository boundary for Raspberry Pi EMS runtime source. The deployed Pi runtime lives under `/home/jeroen/ems/runtime/`; repository source and deployed runtime must remain explicitly traceable to each other.

## Mandatory repository placement guard

Before **every** GitHub change that creates, moves or materially changes Pi runtime code, the contributor or automation must first inspect this file and the current `src/pi/ems-runtime/` tree. Do not invent a new top-level runtime directory merely because it is convenient for one component.

Placement order:

1. classify the responsibility/domain of the component;
2. reuse an existing domain below `src/pi/ems-runtime/` when that domain owns the responsibility;
3. determine the corresponding deployed path below `/home/jeroen/ems/runtime/`;
4. only introduce a new runtime domain when the existing domains demonstrably do not fit;
5. a new runtime domain requires an explicit architecture decision/documentation update in the same change cycle;
6. update deployment definitions and canonical architecture documentation when the runtime/service boundary changes;
7. validate the deployed/runtime path before removing a legacy source location.

Current canonical Pi runtime domains on GitHub are derived from the actual `src/pi/ems-runtime/` tree. At the time of this update these include:

- `datastore/` — persistent/runtime data access responsibilities;
- `planner/` — rolling-horizon planning and planner-specific logic;
- `publisher/` — publication/transport output responsibilities;
- `thermal/` — thermal-domain acquisition, observation and thermal modelling.

These are **domains, not a closed forever list**. Expansion must be deliberate and architecture-documented rather than ad hoc.

### Anti-spaghetti rules

- Do not place new Pi runtime domain logic in generic root `scripts/`.
- Do not use `docs/`, `docs/data/` or generated artifacts as runtime source.
- Do not duplicate the same responsibility in multiple runtime directories.
- Integration/acquisition code and EMS domain interpretation must remain distinguishable, even when they share a domain.
- Runtime output, caches, credentials, OAuth material and other mutable local state are not canonical source and must not be committed as source code.
- `deploy/systemd/` contains deployment/lifecycle definitions; it is not the implementation directory for runtime domain logic.
- A repository checkout update (`git pull`) is not itself a deployment into `/home/jeroen/ems/runtime/`.

For architecture-sensitive changes also check `docs/architecture/CURRENT-EMS-STATE.md` and the relevant document under `docs/software-architecture/`.

## Operational planner source-of-truth rule

For planner components that have been migrated to the Pi, the **active Pi runtime is the operational source of truth**.

- Planner logic is developed and changed first under `/home/jeroen/ems/runtime/planner/...` on the Pi.
- The changed Pi planner is syntax/smoke tested and run in `PURE_SHADOW` before it is considered accepted.
- Only after a successful Pi test is the accepted planner source synchronized back to GitHub under `src/pi/ems-runtime/planner/...` and committed.
- GitHub remains the versioned repository, audit trail, documentation source and publication target; it must not be used to introduce a planner-code change ahead of the Pi runtime.
- Generated planner snapshots under `docs/data/` are observability artifacts and do not make GitHub the planner execution source.
- Runtime/systemd definitions in GitHub must be treated as deployment manifests and checked against the installed Pi units before claiming runtime parity.

## Architecture invariants

The Pi runtime must preserve these invariants:

- P1 remains authoritative for net import/export.
- One consistent state/revision is used downstream.
- Planner and price/context logic remain deterministic and replayable.
- Exactly one automatic writer may own each physical actuator.
- Easee Equalizer remains the independent hard EV load-balancing layer.
- Quatt remains `OBSERVE_ONLY` unless a separately validated control policy is introduced.
- Victron Dynamic ESS remains the primary future battery optimizer; the HEMS orchestrates household flexibility and must not become a competing realtime battery optimizer.
- New Pi control starts read-only/shadow. Physical ownership is transferred only by an explicit atomic cutover with rollback.

## Migration discipline

The machine-readable historical migration inventory is `src/pi/runtime-migration-manifest-v0.1.json`. Its component states may age, so current live implementation and `docs/architecture/CURRENT-EMS-STATE.md` take precedence when they conflict.

A component migration/change is complete only when applicable source, deployed path, deployment definition, architecture documentation and runtime validation agree. Historical or deprecated source may remain temporarily during controlled migration but must be clearly identified and must not silently become a second authority.

## Definition of Done for Pi runtime changes

- placement checked against the canonical runtime domains before coding;
- source path and deployed `/home/jeroen/ems/runtime/...` path are explicit;
- no duplicate runtime responsibility or writer is introduced;
- syntax/smoke/shadow validation is performed where applicable;
- timezone handling uses `Europe/Amsterdam` where local household time is involved;
- deployment/systemd definitions are checked when lifecycle changes;
- `CURRENT-EMS-STATE.md` and relevant component/flow documentation are checked when architecture changes;
- rollback/SHADOW/TEMP functionality is not represented as production;
- legacy location is removed only after the new path is validated.

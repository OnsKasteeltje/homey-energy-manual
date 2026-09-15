# Raspberry Pi EMS migration area

Status: **LEGACY / MIGRATION BOUNDARY — DO NOT USE FOR NEW SOURCE BY DEFAULT**  
Last sync: 2026-09-15

## Authority

The canonical repository placement policy is:

`docs/architecture/repository-structure.md`

That document takes precedence over this README for repository placement.

The target Pi production-source boundary is `services/pi/`, with responsibilities separated into planner, control, state, API, integrations and history. Existing source under `src/pi/` and `src/pi/ems-runtime/` is migration-era source and may remain while it is still operationally required, but its existence must not be used as precedent for new files.

The deployed Pi runtime remains under `/home/jeroen/ems/runtime/`. Repository source and deployed runtime must remain explicitly traceable, but their directory layouts do not have to be identical when the documented deployment mapping intentionally differs.

## Mandatory placement rule

Before every GitHub change that creates, moves or materially changes EMS source:

1. read/check `docs/architecture/repository-structure.md`;
2. classify the touched file by architectural owner and lifecycle;
3. place new source directly in the target structure;
4. apply **Touch it, place it correctly** to materially changed legacy files;
5. if a legacy path cannot safely move in the same change, document why it temporarily remains;
6. update imports, systemd/deployment paths, drift checks, tests and architecture documentation atomically when a move occurs;
7. validate the deployed Pi path before deleting the old source.

Do not create a new `src/pi/...` location merely because related legacy code still exists there.

## Operational planner source-of-truth rule

For planner components already running on the Pi, the active Pi runtime is the operational source of truth during a change cycle:

- change/test the active planner under `/home/jeroen/ems/runtime/planner/...` first;
- syntax/smoke test and use `PURE_SHADOW` where applicable;
- synchronize the accepted implementation back to the **current target repository location** under `services/pi/planner/` when that component is migrated to target structure;
- legacy planner source under `src/pi/ems-runtime/planner/` may temporarily remain only where required for a controlled migration/rollback path;
- GitHub remains the versioned repository, audit trail, documentation source and publication target;
- `git pull` is not deployment into `/home/jeroen/ems/runtime/`.

## Architecture invariants

- P1 remains authoritative for net import/export.
- One consistent state/revision is used downstream.
- Planner and price/context logic remain deterministic and replayable.
- Exactly one automatic writer may own each physical actuator.
- Easee Equalizer remains the independent hard EV load-balancing layer.
- Quatt remains `OBSERVE_ONLY` unless separately validated control is introduced.
- Victron Dynamic ESS remains the primary future battery optimizer.
- New Pi control starts read-only/shadow and transfers ownership only by explicit atomic cutover with rollback.
- Household-local time semantics use `Europe/Amsterdam` and DST-aware timestamps.

## Migration inventory

`src/pi/runtime-migration-manifest-v0.1.json` is historical/migration inventory, not the repository placement authority. Current live implementation, `docs/architecture/CURRENT-EMS-STATE.md`, and `docs/architecture/repository-structure.md` take precedence where older migration material conflicts.

## Definition of done

A Pi-related GitHub change is complete only when, where applicable, implementation, target placement, deployed path, deployment definition, drift validation, tests and canonical architecture documentation agree. Newly obsolete files require an explicit KEEP / ROLLBACK / ARCHIVE / DELETE decision.

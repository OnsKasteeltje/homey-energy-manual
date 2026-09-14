# Contributing to the EMS repository

## Atomic architecture changes

The EMS architecture gate is intentionally strict. To avoid transient CI failures and unnecessary GitHub notification mail, architecture-sensitive changes must reach `main` as one complete, internally consistent commit.

### Required atomic unit

When a change affects Pi runtime, planner behaviour, Tesla/EV logic, warm-water logic, contract/economic policy, datastore boundaries, systemd/deployment behaviour, or the Homey/Pi responsibility split, the same commit must contain all applicable parts:

1. implementation/runtime changes;
2. regression or behaviour tests/fixtures where applicable;
3. the matching update to `docs/architecture/CURRENT-EMS-STATE.md`.

Do **not** push implementation first and architecture documentation in a later commit on `main`.

### Preferred workflow

1. Inspect the current `main` state.
2. Prepare the complete code, tests and architecture-documentation change together.
3. Run the relevant tests and `scripts/ems_architecture_gate.sh` against the intended base revision.
4. Create one atomic commit containing the complete change.
5. Push/update `main` only once for that logical change.
6. Treat the resulting green commit as the deployable revision.

If work genuinely requires several development commits, use a temporary branch and squash the completed work before it reaches `main`. Intermediate development commits must not be used as deployed revisions.

### Why this rule exists

GitHub Actions runs on every relevant push. A temporary commit that changes architecture-sensitive runtime code without the matching canonical documentation is expected to fail the architecture gate, even if a follow-up commit fixes the documentation seconds later. Such failures are noise rather than useful signals.

The gate itself must **not** be weakened to accommodate partial commits. The correct fix is to keep each logical architecture change atomic.

### Exceptions

Pure website publication/data-refresh commits and unrelated documentation changes that do not alter the operational EMS architecture do not require an update to `CURRENT-EMS-STATE.md`.

## Repository placement is part of every GitHub change

The canonical repository-structure policy is documented in `docs/architecture/repository-structure.md`.

Every future GitHub action that creates or materially changes repository content must include a repository-placement check. This is part of the definition of done, not a separate cleanup activity.

### Mandatory placement check

For every materially touched file, determine:

1. which architectural component owns the file;
2. whether its current path matches the target repository structure;
3. whether an incorrectly placed legacy file can safely be moved in the same logical change;
4. whether files made obsolete by the change should be kept as production, retained as rollback, archived, or deleted.

The governing rule is:

> **Touch it, place it correctly.**

New files must use the target structure immediately. Existing legacy paths are migrated incrementally when those files are materially touched. Do not perform unrelated bulk moves merely to satisfy the rule; relocation must remain safe, proportionate and atomic.

If a touched file is intentionally left in a legacy location because moving it would create deployment risk or excessive unrelated churn, that decision must be explicit in the change documentation or commit context.

### Lifecycle hygiene

When touching `TEMP`, `HOTFIX`, `SHADOW`, `TEST`, commissioning or legacy artefacts, make an explicit lifecycle decision: promote/place correctly, retain under tests/tools, archive, or delete.

Do not allow temporary validation or commissioning artefacts to accumulate indefinitely in production paths.

### Atomic moves

A file move that accompanies an architecture-sensitive change must be performed atomically with all required import, systemd, deploy, workflow, test and documentation reference updates. `main` must never contain an intermediate revision in which a path move breaks runtime or deployment behaviour.

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

# Current runtime source policy

Status: **normative for current-state software documentation and Pi migration/cutover work**.

This policy prevents historical Homey preparation, candidate, patch, smoke, rollback and validation material from being interpreted as the current EMS architecture.

## Authority order

For current-state architecture and control documentation, use sources in this order:

1. `docs/architecture/CURRENT-EMS-STATE.md` for canonical architecture and responsibility split.
2. `docs/architecture/homey-runtime-baseline-2026-09-12.md` for current Homey planner-authority and EV/WW execution identities.
3. Exact live Homey flow readback for the named stable Flow IDs when validating runtime behavior.
4. Current Pi runtime source on GitHub `main` for version-controlled Pi behavior.
5. Older baselines/design/preparation Markdown only for historical rationale or explicitly future work.

The previous `homey-runtime-baseline-2026-09-04.md` and `homey-runtime-baseline-2026-08-30.md` are historical audit evidence and are no longer current runtime authority for planner ownership or EV/WW flow versions.

If historical material conflicts with the current canonical state, 2026-09-12 baseline or exact live runtime, the current sources win.

## Planner authority

The sole runtime HOMEY↔PI authority selector is Homey Logic variable:

`EM2_Planner_Authority`

Current production value after the controlled cutover is `PI`.

The active Pi bridge is:

- Flow ID `8bf53fdb-76f4-47db-8ccb-773ac515f06e`;
- `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.4 AUTHORITY-GUARD [READY]`.

The guarded Homey producer is the rollback path when the selector is returned to `HOMEY`.

`planner/control-authority.json` is configuration/diagnostic context and is not a second live authority gate.

## Current EV chain

Current EV ownership is defined by the 2026-09-12 baseline:

- Adapter: `EV Power v0.1.4 DEADLINE-CAP OPPORTUNITY16 START7 RUN6`, Flow ID `953e9b18-3576-4557-b940-ed4a64eb2516`.
- Gate: `EV Power Adapter Gate v0.2.5 OBSERVABILITY-ONLY HEALTH`, Flow ID `ec5e5d34-8205-4cf0-a661-7bf744feb6e0`.
- Physical writer: `EV Power v0.2.6 START7 RUN6 LIVE + EASEE SESSION`, Flow ID `fea23193-a03f-49dd-9780-7e72ee48747d`.
- Device health observer: Flow ID `18a99261-421c-4c5f-a771-36a626b7496a`; health is observability-only at the active gate.
- EV observability: Flow ID `f6edba38-ddf1-45e5-890e-c183aa2055d5`.

Older EV v0.1.2 / gate v0.2.2 / actuator v0.2.3 files remain historical until explicitly reconciled or replaced by current exact live source captures.

## Current WW chain

- Adapter: Flow ID `472d0355-3bb9-4a42-be43-114b57822136`, WW Power v0.2.
- Gate: Flow ID `39c39cc5-12bb-4494-ba45-bad47a656696`, WW Power Adapter Gate v0.2.
- Physical writer: Flow ID `40d45aeb-174e-4a83-9a42-71ae46065cb4`, Warm Water Actuator v0.9 LIVE.

The Pi plans WW; Homey remains the sole physical boiler writer.

## Current Pi control endpoint

Current version-controlled Pi status API source is:

`src/pi/ems-runtime/status-api/server.py`

The endpoint `/control/current` is a technical readiness/command interface. It validates the Pi plan, fixed ENGIE contract and execution context, but runtime planner authority is enforced by Homey `EM2_Planner_Authority`.

Any branch/runtime copy that still requires `control-authority.json` itself to say `plannerOwner = PI` before readiness is **outdated** relative to current `main`.

## Diagram rule

Every process diagram labelled current, live, implemented, production or as-is must be derived from:

- `CURRENT-EMS-STATE.md`;
- the 2026-09-12 runtime baseline;
- exact live flow/source evidence for the component being described.

Historical/candidate diagrams must be explicitly labelled historical, candidate, future or validation.

## Update rule

Whenever a live Homey or Pi control component is promoted:

1. capture/reconcile the exact live runtime;
2. store or update exact version-controlled source where applicable;
3. update `CURRENT-EMS-STATE.md` when architecture/ownership changes;
4. update the dated current runtime baseline when live component identity changes;
5. perform targeted runtime readback and physical/semantic validation as appropriate;
6. verify Pi checkout/runtime drift against GitHub `main` before certifying sync.

A clean working tree alone is not proof of sync if the Pi is on a divergent branch.

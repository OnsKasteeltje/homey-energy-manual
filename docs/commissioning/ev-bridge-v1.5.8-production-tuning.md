# EV Bridge v1.5.8 production tuning — 2026-10-04

Status: **DEPLOYED / EXACT READBACK VERIFIED**

## Scope

Tune the existing single Homey PI Dynamic Planner Bridge after live minute-level
evidence showed that v1.5.7 current regulation is accurate once settled, while
the unified 300-second upward/re-entry dwell can leave material recovered PV
exporting during broken-cloud conditions.

No shadow controller is introduced.

## Stable production target

- Advanced Flow ID: `8bf53fdb-76f4-47db-8ccb-773ac515f06e`
- Existing v1.5.7 name:
  `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.7 PREDICTIVE CURRENT [READY]`
- v1.5.8 name:
  `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.8 PRODUCTION TUNED [READY]`
- Script card ID: `44444444-eeee-4444-8444-444444444444`
- Canonical v1.5.8 source:
  `apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.8.production-tuned.js`

The existing five-card Advanced Flow structure, triggers, notes and stable Flow
ID must be preserved exactly except for flow name and script-card source.

## Production tuning

Unchanged:

- P1 remains authoritative;
- 120-second time-weighted rolling available-power window;
- minimum 90-second rolling coverage;
- OFF→1P threshold 1500 W;
- 1P stop threshold 1100 W;
- 1P/OFF→3P threshold 4400 W;
- 3P leave threshold 3600 W;
- minimum 6 A / maximum 16 A;
- bounded settled current increases: +3 A in 1P, +2 A in 3P;
- physical offered-current/confirmed-phase feedback;
- 250 W phase-entry/minimum-viability margin;
- deadline hard force remains last and 3P;
- Adapter/Gate/Writer contracts remain unchanged;
- writer v0.4.5 remains the sole automatic physical Easee writer.

Changed:

- OFF re-entry dwell: 300 s → **120 s**;
- 1P→3P dwell: 300 s → **180 s**;
- same-phase predictive import preference: +200 W → **+300 W**;
- same-phase down-regulation effective import limit: **+300 W**, so it does not
  immediately undo the +300 W predictive preference.

## Placement

v1.5.8 is new source and is placed directly in the target repository structure
under `apps/homey/control/ev/`. Historical v1.5.7 source remains in its legacy
location for traceability; it is not modified or copied as a second live
controller.

## Deployment transaction

Follow `docs/architecture/pi-homey-flow-deployment.md` and
`docs/architecture/homey-api-access-guidelines.md`:

1. one targeted pre-read of the known stable Flow ID;
2. retain the complete pre-deploy writable body as rollback source;
3. prepare the full candidate outside Homey;
4. perform one update of writable fields only: `name`, `enabled`, `cards`;
5. perform one targeted read-back;
6. compare stable Flow ID, enabled state, card count, unchanged non-script cards,
   exact v1.5.8 script source and production name;
7. on mismatch, restore the exact pre-deploy writable body and stop;
8. do not manually trigger the physical EV actuator as a validation shortcut.

A 429 is a hard stop; no retry or alternate Homey endpoint is permitted.

## Acceptance

Repository acceptance:

- repository structure gate PASS;
- EMS architecture gate PASS;
- v1.5.8 regression PASS;
- existing EV phase/current and writer regressions PASS;
- security scan PASS.

Runtime acceptance after the normal minute trigger:

- Bridge Power Intent uses
  `policyRevision=PI_DYNAMIC_PLANNER_BRIDGE_V1.5.8_PRODUCTION_TUNED`;
- realtime controller reports
  `controllerVersion=EM2_EV_PHASE_CURRENT_CONTROLLER_V0.3`;
- reported dwell values are 120 s OFF re-entry and 180 s 1P→3P;
- `upscaleImportTargetW=300`;
- `currentImportLimitW=300`;
- Adapter/Gate remain aligned and Gate remains PASS for valid control;
- no additional physical writer exists.

## Production cutover result — 2026-10-04

GitHub PR #165 passed the repository structure gate, EMS Architecture Gate,
all canonical/EV regressions and the full EMS Security Scan, then squash-merged
as `af8da3041f5d09abc50b33d5cc3b7b9ad8b7e6e4`.

The Homey deployment then updated only stable Advanced Flow
`8bf53fdb-76f4-47db-8ccb-773ac515f06e` from v1.5.7 to:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.8 PRODUCTION TUNED [READY]`

Targeted post-write readback proved:

- flow ID unchanged;
- enabled = true;
- broken = false;
- card count remained 5;
- every non-script card was byte-for-byte semantically unchanged;
- script-card source exactly matched GitHub `main`;
- no Adapter, Gate or writer flow was changed;
- no physical actuator flow was manually triggered for deployment validation.

The exact pre-deploy v1.5.7 writable body was retained in-memory for immediate
rollback during the transaction; rollback was not required.

## Rollback

Rollback is the exact writable v1.5.7 Advanced Flow body captured by the
pre-deploy targeted read. Rollback does not alter Adapter, Gate, actuator,
planner authority or Pi runtime.

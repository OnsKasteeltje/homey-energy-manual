# Current runtime source policy

Status: **normative for current-state software documentation and Pi migration/cutover work**.

This policy prevents historical Homey preparation, candidate, patch, smoke, rollback and validation material from being interpreted as the current EMS architecture.

## Authority order

1. `docs/architecture/CURRENT-EMS-STATE.md`: canonical current responsibilities and source.
2. Exact **live Homey Advanced Flow** readback (stable Flow ID, enabled, broken, executable script) and current Pi runtime/contract readback for operational assertions.
3. `main` source under `apps/homey/`, `src/homey/`, `services/pi/` and `src/pi/ems-runtime/`, plus dated commissioning evidence for promotion.
4. Dated Homey baselines, candidate patches, historical smoke/rollback notes: **historical evidence**, never current authority without reconciliation.

The 2026-09-12 and earlier Homey runtime baselines no longer define the current EV versions. `src/homey/core/README.md` documents the preserved Core V0.11n rollback and active V0.11p identity. A filename containing `candidate` or `live` does not supersede the exact current Homey flow.

## Planner authority

The single Homey selector remains `EM2_Planner_Authority`. Pi owns current planning and EV deadline lifecycle; Homey remains executor/safety. The current Homey Bridge is:

- Flow `8bf53fdb-76f4-47db-8ccb-773ac515f06e`, **PI Dynamic Planner Bridge V1.5.9**, enabled and not broken at the 2026-10-13 Homey readback.
- Canonical V1.5.9 source: `apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.9.adaptive-upscale.js`.
- Historical V1.5.8 source remains a bounded rollback/comparison baseline.

`planner/control-authority.json` is configuration/diagnostic context, not a second live selector.

## Current EV chain

- Adapter: V0.2.0, Flow `953e9b18-3576-4557-b940-ed4a64eb2516`.
- Gate: V0.3.0, Flow `ec5e5d34-8205-4cf0-a661-7bf744feb6e0`.
- **Single physical Easee writer:** V0.4.6, Flow `fea23193-a03f-49dd-9780-7e72ee48747d`, enabled and not broken at 2026-10-13 readback.
- EV Device Health V0.4 is observability only, not a control owner.
- Tesla deadline ingress since 2026-10-09: private Invoer V2 → Tailscale/Caddy → Pi Status API `/commands/tesla` → local Pi command file. The GitHub fetcher/service/timer were retired.

Older EV source and tests may remain as intentionally retained regressions or rollback evidence. Do not reinstate any former GitHub publisher or second writer.

## Current WW chain

- Adapter: Flow ID `472d0355-3bb9-4a42-be43-114b57822136`, WW Power v0.2.
- Gate: Flow ID `39c39cc5-12bb-4494-ba45-bad47a656696`, WW Power Adapter Gate v0.2.
- Physical writer: Flow ID `40d45aeb-174e-4a83-9a42-71ae46065cb4`, Warm Water Actuator v0.9 LIVE.

The Pi plans WW; Homey remains the sole physical boiler writer.

## Current Pi control endpoint

Current version-controlled Pi status API source is:

`services/pi/api/status/server.py` (deployed Pi Status API source; `src/pi/ems-runtime/` retains related runtime modules)

The endpoint `/control/current` is a technical readiness/command interface. It validates the Pi plan, fixed ENGIE contract and execution context, but runtime planner authority is enforced by Homey `EM2_Planner_Authority`.

Any branch/runtime copy that still requires `control-authority.json` itself to say `plannerOwner = PI` before readiness is **outdated** relative to current `main`.

## Diagram rule

Every process diagram labelled current, live, implemented, production or as-is must be derived from:

- `CURRENT-EMS-STATE.md`;
- current Homey exact flow readback and dated commissioning evidence;
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

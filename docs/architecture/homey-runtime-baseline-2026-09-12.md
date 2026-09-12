# Homey runtime baseline — 2026-09-12

Status: **current production baseline for planner authority and EV/WW execution**

This baseline records the Homey components that are authoritative after the controlled Pi planner cutover and the 2026-09-12 physical EV/WW validation.

## Planner authority

Single runtime selector:

- Logic variable: `EM2_Planner_Authority`;
- active value after cutover: `PI`;
- this is the sole HOMEY↔PI planner-authority gate.

Active Pi intent bridge:

- Flow ID: `8bf53fdb-76f4-47db-8ccb-773ac515f06e`;
- Flow: `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.4 AUTHORITY-GUARD [READY]`;
- enabled;
- inert unless selector is exactly `PI`;
- reads Pi `/control/current`;
- requires `readyForCutover = true` and fresh valid command;
- maps the Pi command into `EM2_POWER_INTENT_V0.2`;
- performs no device writes.

Guarded Homey rollback producer:

- Flow ID: `f24aa42f-cf74-4e17-beb5-b826fc552836`;
- Flow: `EM v2 | 20 Power Intent | P1 v0.2.6 AUTHORITY-GUARD [HOMEY ACTIVE]`;
- remains available for rollback when selector is returned to `HOMEY`.

Legacy producer:

- Flow ID: `19d9d8a6-ec32-4639-be5e-71e9f034d31b`;
- must remain disabled as a competing production authority.

Controlled cutover self-test:

- Flow ID: `63f2041e-1446-45df-9ca4-08239ecb26ba`;
- Flow: `TEMP | Controlled PI cutover self-test v1.2.5`;
- switched HOMEY→PI only after Pi readiness and zero EV/WW targets;
- retained PI only after canonical Pi intent takeover; otherwise automatic rollback.

## EV execution chain

### Adapter

- Flow ID: `953e9b18-3576-4557-b940-ed4a64eb2516`;
- Flow: `EM v2 | 60 Adapter | EV Power v0.1.4 DEADLINE-CAP OPPORTUNITY16 START7 RUN6`;
- enabled;
- START7/RUN6 mapping: 7 A may start a paused session; 6 A may maintain an already-running session.

### Gate

- Flow ID: `ec5e5d34-8205-4cf0-a661-7bf744feb6e0`;
- Flow: `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.5 OBSERVABILITY-ONLY HEALTH`;
- enabled;
- decisive checks: schema, revision alignment, safety/read-only semantics, EV state semantics, electrical mapping, command range and translation;
- `EM2_EV_Telemetry_Health` is diagnostic only and cannot independently veto a coherent EV command.

### Health observer

- Flow ID: `18a99261-421c-4c5f-a771-36a626b7496a`;
- Flow: `EM v2 | 82 Safety | EV Device Health v0.2 LIVE-GATE`;
- enabled;
- no device writes;
- legacy flow name still says LIVE-GATE, but its health output is observability-only at the active v0.2.5 EV gate.

### Actuator

- Flow ID: `fea23193-a03f-49dd-9780-7e72ee48747d`;
- Flow: `EM v2 | 60 Actuator | EV Power v0.2.6 START7 RUN6 LIVE + EASEE SESSION`;
- enabled;
- sole EMS physical Easee writer in the current EV power chain;
- validates coherent fresh gate/adapter/intent/state before a write.

### Observability

- Flow ID: `f6edba38-ddf1-45e5-890e-c183aa2055d5`;
- Flow: `EM v2 | 81 Observability | EV Control Status v0.3 + HEALTH`;
- publishes `docs/data/ev-control-status.json`;
- top-level contract states `observabilityOnly = true`, `controlImpact = NONE` for device health.

## WW execution chain

### Adapter

- Flow ID: `472d0355-3bb9-4a42-be43-114b57822136`;
- Flow: `EM v2 | 60 Adapter | WW Power v0.2 TARGETED-READ SHADOW`;
- enabled;
- maps `EM2_Power_Intent.targets.ww.target_on` to boolean/hold command semantics;
- no device writes.

### Gate

- Flow ID: `39c39cc5-12bb-4494-ba45-bad47a656696`;
- Flow: `EM v2 | 80 Validation | WW Power Adapter Gate v0.2 TARGETED-READ`;
- enabled;
- PASS requires exact intent/adapter schema, revision and command mapping match.

### Actuator

- Flow ID: `40d45aeb-174e-4a83-9a42-71ae46065cb4`;
- Flow: `EM v2 | 60 Control | Warm Water Actuator v0.9 TARGETED-READ LIVE`;
- enabled;
- sole current boiler physical writer for the PI WW power chain;
- requires live arm, boiler source mode, aligned schema/revision, gate PASS and fresh command before touching the device;
- HOLD never touches the boiler.

## Physical validation — 2026-09-12

### EV

Controlled Pi current-slot target:

- 4830 W / 7 A;
- EV gate PASS while device-health observer still reported STALE;
- actuator reported physical write;
- Easee physically charged at 7 A, approximately 4.9 kW;
- later Pi target 0 A physically paused charging again.

Result: **Pi → Homey → EV ON/OFF PASS.**

### WW

Controlled Pi current-slot WW target:

- boiler physically switched ON;
- measured approximately 2031 W / 8.97 A;
- restore to normal Pi target physically switched boiler OFF to 0 W.

Result: **Pi → Homey → boiler ON/OFF PASS.**

## Safety constraints

- Do not manually start the EV actuator as an end-to-end test; its manual start path changes live-arm semantics.
- Do not manually start the WW actuator as a substitute for a planner test; its manual start explicitly arms WW LIVE.
- Unexpected physical behavior during Pi authority: return `EM2_Planner_Authority` to `HOMEY`.
- Pi planner remains read-only with respect to physical devices; Homey actuators remain the physical execution boundary.

## Source reconciliation note

This baseline is based on exact live Homey flow inspection and physical readback on 2026-09-12. Older `src/homey/*` files and the 2026-09-04 baseline that name older EV adapter/gate/actuator versions are historical unless explicitly reconciled to these live flow versions.

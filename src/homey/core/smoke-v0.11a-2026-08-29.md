# Core v0.11a targeted-read smoke — 2026-08-29

## Scope

Controlled deployment of `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)` from Homey baseline v0.10.18.

Only the Core device-read layer was changed:

- removed broad `Homey.devices.getDevices()`;
- added ten stable-ID `Homey.devices.getDevice({id})` reads;
- rebuilt the local `devices` map so downstream Core helpers and policy remain unchanged;
- kept `Homey.logic.getVariables()` unchanged;
- retained the v0.10.18 `EM2_Control_EV` semantic producer;
- no physical device-write path was introduced.

All other EMS flows remained disabled for this experiment.

## Runtime result

- Advanced Flow update: PASS
- Flow name: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`
- Schedule: every 5 minutes
- Enabled: `true`
- Broken: `false`
- One controlled manual start: PASS (Homey accepted and started the flow)
- Source verification after start: PASS; deployed code contains targeted reads and no broad `Homey.devices.getDevices()` call
- Physical device writes: none in Core source / PURE SHADOW contract retained

## Current status

**SMOKE PASS / SOAK IN PROGRESS**

The connector does not expose the string-valued Core Logic outputs directly, so full runtime semantic equality of `EM2_State`, `EM2_Decision`, `EM2_Control_WW`, `EM2_Control_EV` and `EM2_Planner_Input` is not yet independently read back in this smoke. Acceptance therefore remains provisional until natural 5-minute runs and system-load/throttling behavior are observed.

## Rollback

Rollback target remains v0.10.18 unchanged.

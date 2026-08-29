# EV Power Actuator STOP ownership LIVE smoke — 2026-08-29

## Purpose
Validate first physical LIVE ownership scenario for the hardened EV control chain: when the Tesla/Easee starts charging autonomously after plug-in while EMS policy has no valid opportunity or deadline demand, a coherent `EV_target_W = 0` must propagate to `requested_A = 0`, Gate PASS, and the LIVE actuator must stop the charging session.

## Preconditions / readiness
Fresh observability snapshot before LIVE action:

- revision: `3116`
- `EV_target_W = 0 W`
- EV status: `IDLE`
- EV Power Adapter `requested_A = 0 A`
- adapter revision: `3116`
- state revision: `3116`
- Gate status: `PASS`
- Gate source/intent/state/core revisions: all `3116`
- `coherent = true`
- actuator before test: `SHADOW_NO_WRITE`, LIVE=false, no physical write
- Easee/Tesla was physically charging autonomously at approximately 8.5 kW / ~12 A per phase before the test.

## Controlled LIVE procedure
1. A temporary one-shot arm flow was created with fail-closed checks.
2. It could set `EM2_EV_Actuator_Live_Enabled=true` only when:
   - target remained exactly 0 W;
   - requested current remained exactly 0 A;
   - Gate remained PASS;
   - intent/adapter/state/Gate revisions were exactly coherent;
   - relevant state/adapter/Gate data were <=120 s old;
   - adapter remained SHADOW/read-only/no-device-write;
   - Easee was physically charging.
3. The one-shot arm flow started successfully.
4. Exactly one Core sample was started to create a natural fresh semantic revision and allow the normal Power Intent -> Adapter -> Gate -> Actuator chain to run.
5. Easee readback showed `target_charger_current = 0 A` after the actuator action.
6. User physically confirmed: **charging stopped**.
7. Fail-safe cleanup: the existing EV actuator manual start was executed, which resets LIVE=false before executing its SHADOW path.
8. Temporary arm flow was disabled immediately after the test.

## Result
**PASS**

The hardened EV chain demonstrated physical STOP ownership: an autonomous charging session was stopped when the EMS had no charging intent and the full 0 W -> 0 A -> Gate PASS chain was fresh and revision-coherent.

## Safety notes
- No validation criteria were weakened.
- No positive charging current was commanded in this smoke.
- The temporary LIVE arm could not arm on stale, incoherent, non-zero or Gate-failing inputs.
- LIVE was returned to fail-safe false immediately after the physical stop was confirmed.
- Positive-current regulation (`>0 W -> 6..16 A`) remains a separate future smoke requiring a fresh natural positive EV target and Gate PASS/coherence.

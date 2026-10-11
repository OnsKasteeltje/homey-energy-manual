# EV writer v0.4.6 OFF-zero cutover — 2026-10-11

## Scope and source of truth

- Canonical candidate prepared in PR #232; squash commit `a1300607c8c91643418d0393a0e6c87d93325ebd`.
- GitHub Architecture Gate and Security Scan: PASS (including behavior-driven v0.4.6 OFF/zero-current regressions).
- Canonical active HomeyScript: `apps/homey/control/ev/ev-power-v0.4.6.off-zero-idempotent.js`; source blob `347b24fafeb9073d1495a04001703be6a1296d9d`.
- Rollback source: `src/homey/actuators/ev-power/ev-power-v0.4.5.phase-writer-live.js`, previously confirmed byte-for-byte identical to the active HomeyScript immediately before cutover.

## Homey deployment validation

- Existing Advanced Flow ID `fea23193-a03f-49dd-9780-7e72ee48747d` retained.
- Prior name: `EM v2 | 60 Actuator | EV Power v0.4.5 AUTH-ALERT [LIVE]`.
- New name: `EM v2 | 60 Actuator | EV Power v0.4.6 OFF-ZERO-IDEMPOTENT [LIVE]`.
- Preflight: enabled=true, broken=false, four cards, exactly one script action, old script exact match to canonical v0.4.5, candidate exact match to GitHub main.
- Updated only writable name / script-code contents while preserving enabled=true and the three other cards.
- Targeted live readback: PASS for ID, name, enabled=true, broken=false, four card keys, all unchanged non-script cards, script exact match to canonical v0.4.6.
- **No manual flow trigger and no deliberate physical charging test.** Homey naturally executes on its existing Gate change trigger.

## Safety and rollback

The sole physical Easee writer remains the existing Homey actuator. The v0.4.6 implementation retains the bounded phase-transition and Easee authentication/alert behavior, and the fail-closed recovery path for genuinely unconfirmed OFF. The lower EV start-threshold proposal remains unimplemented (OFF→1P 1500 W, 1P stop 1100 W). No Pi planner, adapter/gate, controller, Quooker, or Constrained Replay change accompanies this release.

Rollback if production behavior regresses: targeted Homey read; restore the exact previous v0.4.5 script and prior flow name in the same Flow ID, preserving the other cards and enabled state; perform exact targeted readback. Do not manually trigger the actuator to validate deployment. Stop on Homey 429 rather than retrying blindly.

## Evidence still required

This deployment proves **code promotion**, not **absence of runtime incidents**. Review naturally generated Pi `ev_control_events` and Easee readback after the cutover for `OFF_ZERO_A_HOLD_FAILED:OFF_ZERO_CURRENT_CONFIRM_TIMEOUT`, real OFF→zero-current settling, successful next positive opportunities and safe pause/restore if actual telemetry is not yet zero. Distinguish archived event counts from unique incident counts.
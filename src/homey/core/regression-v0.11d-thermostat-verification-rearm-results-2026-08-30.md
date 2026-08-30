# Core v0.11d thermostat verification re-arm — offline regression results

Status: **OFFLINE A-J PASS / LIVE ACCEPTANCE OPEN**

Date: 2026-08-30

The revised minimal v0.11d latch-reset semantics were re-run outside Homey as a pure state machine. No Homey mutation was performed during this regression.

| Scenario | Result | Evidence |
|---|---|---|
| A first discretionary OFF | PASS | eligible stop starts bounded thermostat verification |
| B continuous OFF | PASS | expiry/abort consumes the current physical-run verification while the stop request remains continuously true; no renewal loop |
| C opportunity return | PASS | a genuine stop-request-clear tick makes the consumed latch false and clears the persisted consumed run key |
| D later same-run OFF | PASS | after the clear tick, a later stop request may start one fresh bounded verification |
| E elapsed time alone | PASS | continuous true stop request does not rearm merely because time passes |
| F thermostat cutoff | PASS | existing <100 W while ON for 10 min rule remains unchanged and latches the daily goal |
| G safety aborts | PASS | P1/grid/import aborts remain immediate and cannot renew while the stop request stays true |
| H MUST precedence | PASS | mode OFF, >=19:00, goal reached and catch-up/MUST paths remain above verification |
| I physical OFF reset | PASS | existing physical-OFF reset remains unchanged |
| J 2026-08-30 replay | PASS | earlier consumed verification + genuine opportunity return + later ~1966 W stop request yields a fresh bounded verification instead of direct OFF |

Result: **10/10 PASS**.

This regression supersedes the earlier explicit episode-state candidate. The actual v0.11d deployment delta is intentionally minimal: scope the existing `thermostatVerifyConsumed` latch to `thermostatVerifyRequested`, so the latch remains anti-renewal while the discretionary stop request is continuously active and clears on a genuine request-clear tick.

Production acceptance remains open until a natural live cycle confirms the intended behavior.
# Core v0.11d thermostat verification re-arm — offline regression results

Status: **OFFLINE A-J PASS / LIVE ACCEPTANCE OPEN**

Date: 2026-08-30

The v0.11d verifier was executed outside Homey as a pure 5-minute-tick state machine using the candidate transition rules. No Homey mutation was performed.

| Scenario | Result | Evidence |
|---|---|---|
| A first discretionary OFF | PASS | false->true stop edge starts one HOLD/MAY/THERMOSTAT_VERIFY episode; rearm false; key/start stable |
| B continuous OFF | PASS | episode expires at 20 min; no renewal while stop stays true |
| C opportunity return | PASS | true->false clear during confirmed >1500 W heating rearms; next false->true edge starts episode 2 |
| D elapsed time alone | PASS | no rearm |
| E heatingConfirmed alone | PASS | no rearm without stop clear |
| F thermostat cutoff | PASS | <100 W while ON for 10 min latches daily goal and ends verification GOAL_CONFIRMED |
| G safety aborts | PASS | stale P1, invalid grid, unsafe import abort immediately; no auto-rearm |
| H MUST precedence | PASS | mode OFF, >=19:00, goal reached, catch-up bypass verification |
| I physical OFF reset | PASS | episode state clears; rearm true; stop baseline false |
| J 2026-08-30 replay | PASS | after an earlier episode and genuine opportunity return, the later ~1966 W OFF edge starts a fresh episode instead of immediate OFF |

Result: **10/10 PASS**.

This validates the isolated v0.11d state-machine semantics only. It does not yet prove the complete Core script. Before deployment, the exact then-live v0.11c full script must be captured, the reviewed re-arm delta applied, and a full-script diff must confirm no changes to cadence, device set, Planner semantics, WW ownership, Tesla logic, Quatt observe-only behavior, 19:00 stop, Publisher cadence/fan-out, or Core's no-device-write rule.

Production acceptance remains open until one natural live run confirms either the real thermostat cutoff -> 10-minute low-power goal latch, or a later same-run discretionary OFF starts a second bounded verification only after a genuine intervening stop-request clear.

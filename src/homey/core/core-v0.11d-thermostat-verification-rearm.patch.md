# Core v0.11d — deployment delta from v0.11c

Status: **REVISED / READY FOR SINGLE-FLOW DEPLOYMENT**

Baseline: live Core v0.11c thermostat-verification logic captured on 2026-08-30.

## Scope

Fix only the same-physical-run thermostat-verification re-arm defect. Preserve cadence, device reads, Planner semantics, WW ownership, Tesla logic, Quatt behavior, 19:00 stop, Publisher behavior and Core read-only/no-device-write rule.

## Minimal implementation

The v0.11c anti-renewal latch is correct while a discretionary stop request remains continuously active. The defect is that the latch remains consumed for the entire physical ON-run after the stop request has genuinely cleared.

Keep the existing run key and consumed-latch structure, but scope `thermostatVerifyConsumed` to a currently active stop request:

```js
const thermostatVerifyConsumed =
  thermostatVerifyRunKey !== '' &&
  prevVerifyConsumedRunKey === thermostatVerifyRunKey &&
  thermostatVerifyRequested;
```

The existing output line remains:

```js
let thermostatVerifyConsumedRunKeyOut =
  thermostatVerifyConsumed ? thermostatVerifyRunKey : null;
```

Consequences:

- continuous stop request: consumed stays true after expiry/abort, so no 20-minute renewal loop;
- genuine stop-request clear: consumed becomes false and the persisted consumed run key clears on that Core tick;
- later new stop request in the same physical ON-run: base eligibility can start one fresh bounded verification;
- physical OFF continues to clear verification state as before;
- MUST/safety precedence is unchanged.

No extra episode-state fields are required for v0.11d. This is intentionally smaller and easier to audit than the earlier candidate state machine.

## Version metadata

Change `PUB_VERSION` from `EM2_CORE_STATE_V0.11c` to `EM2_CORE_STATE_V0.11d` and rename the Advanced Flow to:

`EM v2 | 00 Core Tick | v0.11d (Thermostat Verification Rearm)`

Update the flow note to state that the consumed latch blocks renewal only while the discretionary stop request remains continuously active and is cleared by a genuine request-clear tick.

## Safety invariants

Unchanged:

- max verification window 20 minutes;
- goal evidence remains confirmed heating followed by <100 W for 10 minutes while `boilerOn===true`;
- verification never infers goal;
- mode OFF, >=19:00, reached goal and catch-up/MUST precedence remain above verification;
- stale/invalid P1 and unsafe import abort verification;
- Core performs no physical device writes.

## Offline regression

Re-run A-J against the minimal latch-reset semantics. Required results:

1. initial discretionary OFF can start verification;
2. continuous OFF expires once and cannot renew;
3. request clear resets consumed latch;
4. later same-run OFF can verify again;
5. elapsed time alone does not rearm while request remains true;
6. thermostat low-power goal evidence unchanged;
7. safety abort cannot renew while request remains true;
8. MUST precedence unchanged;
9. physical OFF reset unchanged;
10. 2026-08-30 replay reaches a fresh bounded verification after an intervening request-clear.

This revised delta supersedes the earlier explicit episode-state candidate.
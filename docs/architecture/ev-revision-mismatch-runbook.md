# EV control — Core revision mismatch runbook

Status: production troubleshooting note  
Date established: 2026-09-13  
Scope: Tesla/Easee execution chain on Homey with Pi policy input

## Purpose

This runbook records a failure mode that can make EV charging stop or remain paused even though the deadline/policy layer requests charging. Check this early whenever the Tesla should charge but Easee remains at 0 A, starts briefly and falls back to 0 A, or the EV actuator reports fail-closed.

## Signature / fast recognition

The characteristic signature is a revision mismatch in the EV execution chain:

```text
EV intent target is valid (for example 11040 W / 16 A)
gate.status        = FAIL
actuator.status    = LIVE_FAIL_CLOSED
actuator.reason    = REVISION_MISMATCH
physicalWritePerformed = false
coherent           = false
```

The decisive diagnostic is to compare these revisions together:

```text
intentRevision
adapterRevision
stateRevision
coreRevision
```

Do not start by debugging the Pi planner, deadline arithmetic or Easee when the requested EV target is already correct. First establish whether the Homey execution chain is revision-coherent.

## Incident 2026-09-13

The deadline path correctly requested maximum charging:

```text
targetW     = 11040
requestedA  = 16
evStatus    = NUMERIC_DEADLINE_TARGET
```

But one observed control publication contained:

```text
revision        = 7007
adapterRevision = 7007
stateRevision   = 7008

gate.status     = FAIL
intentRevision  = 7007
stateRevision   = 7007
coreRevision    = 7008

actuator.status = LIVE_FAIL_CLOSED
actuator.reason = REVISION_MISMATCH
coherent        = false
```

This was a Homey execution-coherency problem, not a missing EV request. The fail-closed behaviour was correct: a command built against an older Core state was not allowed to perform a physical write.

## Root cause

The Homey P1 / Power Intent flow did not rebuild the Power Intent on every new `EM2_State` revision. Core could therefore advance to revision N+1 while the EV Power Intent / Adapter / Gate chain still represented revision N.

That created a short but operationally important inconsistency:

```text
Core N+1
   ↓
old Power Intent N
   ↓
EV Adapter N
   ↓
EV Gate compares against Core N+1
   ↓
REVISION_MISMATCH
   ↓
Actuator fails closed → no Easee write / 0 A
```

Because Core state changes frequently, this could recur after an apparently successful charge start. It therefore looked externally like charging was being started and then stopped again.

## Production fix

On 2026-09-13 the Homey Power Intent flow was changed to:

`P1 v0.2.7 STATE-TRIGGER`

The essential change is that `EM2_State` itself triggers rebuilding the Power Intent. A new Core revision therefore propagates through the control chain rather than leaving an intent based on the previous revision.

The existing revision checks and fail-closed behaviour were deliberately retained. The fix is synchronization, **not** weakening the safety gate.

Expected chain after the fix:

```text
EM2_State revision N
   ↓ trigger
Power Intent revision N
   ↓
EV Power Adapter revision N
   ↓
EV Gate revision N / Core revision N → PASS
   ↓
EV Actuator revision N → READY_SESSION_CONTROL
   ↓
Easee command
```

## Validation evidence

After the fix the observed publication was coherent:

```text
revision        = 7008
targetW         = 11040
requestedA      = 16
adapterRevision = 7008
stateRevision   = 7008

gate.status     = PASS
intentRevision  = 7008
stateRevision   = 7008
coreRevision    = 7008

actuator.status = READY_SESSION_CONTROL
actuator.targetA = 16
coherent        = true
```

Easee subsequently changed from paused / 0 A to charging with target and offered current of 16 A. This confirms that the execution path could again reach the charger once revision coherence was restored.

## First checks next time

When EV charging unexpectedly remains/stops at 0 A, use this order:

1. Check the requested target. If `targetW > 0` / `requestedA > 0`, the upstream deadline/policy path is asking for charge.
2. Check `gate.status`, `actuator.status`, `actuator.reason`, and `coherent` in `docs/data/ev-control-status.json`.
3. If `actuator.reason == REVISION_MISMATCH`, compare `intentRevision`, `adapterRevision`, `stateRevision`, and `coreRevision` immediately.
4. Verify that the Homey Power Intent flow is the state-triggered production version (`P1 v0.2.7 STATE-TRIGGER` or its documented successor) and that `EM2_State` changes actually trigger it.
5. Only after revision coherence is confirmed should investigation move downstream to EV Gate/Actuator/Easee or upstream to Pi/deadline calculations.

A healthy sample should look conceptually like:

```text
intentRevision == adapterRevision == gate.intentRevision
stateRevision  == gate.stateRevision == gate.coreRevision
coherent == true
gate.status == PASS
```

For an executable positive target, the actuator should then be ready/live rather than `LIVE_FAIL_CLOSED` for `REVISION_MISMATCH`.

## Safety invariant

Never solve this symptom by removing or relaxing revision validation. Revision matching prevents a physical charger command from being executed against a different Homey/Core state than the one on which the command was based.

Correct remedy:

**make state → intent → adapter → gate propagation coherent.**

Incorrect remedy:

**allow stale revisions through the gate.**

## Search terms

Use these terms when searching repository history, runtime data or incident notes:

`REVISION_MISMATCH`, `coreRevision`, `intentRevision`, `stateRevision`, `adapterRevision`, `coherent false`, `LIVE_FAIL_CLOSED`, `P1 v0.2.7 STATE-TRIGGER`, `EV Gate`, `EV Actuator`, `Tesla 0A`, `Easee paused`, `EM2_State`.

## Related runtime evidence

Primary runtime observability file:

`docs/data/ev-control-status.json`

This runbook should be treated as the first diagnostic reference for EV charging failures where a valid positive target exists but the Homey execution chain does not perform the physical write.

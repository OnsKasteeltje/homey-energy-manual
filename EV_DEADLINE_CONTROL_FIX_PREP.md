# EV deadline control fix — PREP ONLY / NOT DEPLOYED

Status: **PREP ONLY — NOT DEPLOYABLE TO HOMEY YET**
Date: 2026-09-04
Observed live Homey flows:
- Core: `EM v2 | 00 Core Tick | v0.11h PINNED SOURCE`
- Live EV actuator: `EM v2 | 60 Actuator | EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP`

## Incident evidence

1. Easee target current was manually set to 8 A and later changed to 0 A while the cable remained connected.
2. Live actuator diagnostics identified `STALE_INPUT` with live ownership enabled.
3. A new deadline command was accepted with:
   - deadline 08:00 Europe/Amsterdam
   - current SOC 48%
   - target SOC 55%
   - goal 3.85 kWh
   - maxA 8
4. Deadline Goal Adapter computes `latestStart = deadline - goal/(maxA*690W)`; for 3.85 kWh at 8 A this is approximately 07:18:09.
5. Deadline was entered after that time, so Core must classify it as catch-up / `MUST`.
6. Live Core v0.11h does select `TESLA_CHARGE_DEADLINE` when `Date.now() >= latestStart`, but its EV control producer derives `requestedPowerClass` from `flexExportBudgetW` for all modes.
7. Live actuator freshness is 120 s while Core cadence is 300 s, so correct Core output can become stale between normal Core runs.

## Defect A — deadline MUST is incorrectly PV/export limited

Current live Core pattern:

```js
const evMode = intent === 'TESLA_CHARGE_DEADLINE' ? 'DEADLINE'
  : intent === 'TESLA_CHARGE_OPPORTUNITY' ? 'OPPORTUNITY'
  : intent === 'TESLA_BUFFER_EXPORT' ? 'BUFFER_EXPORT'
  : 'HOLD';

const evFlexW = Math.max(0, Number(decision.inputs?.flexExportBudgetW) || 0);
const requestedPowerClass = evMode === 'HOLD'
  ? 0
  : evFlexW < 4140
    ? 1
    : Math.min(16, Math.floor(evFlexW / 690));
```

This is invalid for `DEADLINE`: once latest-start is reached, deadline ownership must override PV/export opportunity constraints.

### Candidate correction

Read and propagate `EV Max laadstroom A` into Core state/goals and use it as the deadline cap.

```js
const deadlineMaxA = Math.max(6, Math.min(16, Math.round(Number(vv('EV Max laadstroom A')) || 16)));
```

Publish it in `state.goals`, `decision.inputs`, and `EM2_Control_EV`.

Replace the common requested-power calculation with mode-specific logic:

```js
const evFlexW = Math.max(0, Number(decision.inputs?.flexExportBudgetW) || 0);

let requestedA = 0;
if (evMode === 'DEADLINE') {
  // latest-start/catch-up is MUST. PV/export no longer limits charging.
  requestedA = deadlineMaxA;
} else if (evMode === 'OPPORTUNITY' || evMode === 'BUFFER_EXPORT') {
  requestedA = evFlexW < 4140 ? 0 : Math.min(16, Math.floor(evFlexW / 690));
}

const requestedPowerClass = requestedA;
```

Important semantic correction: use amperes explicitly (`requestedA`) rather than overloading `requestedPowerClass` with values where `1` can mean a non-actionable below-minimum charging class.

For opportunity charging, below the 3-phase minimum (~4140 W at 6 A) should be **0 A / HOLD**, not class `1`.

## Defect B — actuator freshness shorter than producer cadence

Live actuator:

```js
const FRESH_MS = 120000;
```

Core nominal cadence:

```text
300000 ms (5 minutes)
```

Therefore a normal, healthy input can be older than 120 s for ~60% of the interval between Core ticks. Any unrelated gate-trigger during that interval can cause `STALE_INPUT -> writeA(0)`.

### Candidate correction

Freshness must be greater than the maximum normal producer interval plus execution/jitter allowance.

Recommended first safe value:

```js
const FRESH_MS = 420000; // 7 min = 5 min producer cadence + 2 min margin
```

Do **not** simply disable freshness. Keep fail-closed behavior for genuinely stalled producers.

Better follow-up architecture on Pi: publish explicit heartbeat/lease expiry from the producer and validate that lease instead of inferring validity from a hardcoded consumer timeout.

## Defect C — deadline `maxA` is not end-to-end owned

The deadline input adapter validates and publishes `EV Max laadstroom A`, but live Core v0.11h does not include it in `state.goals` and its EV-control producer does not use it.

Candidate end-to-end contract:

```json
{
  "mode": "DEADLINE",
  "requestedA": 8,
  "deadlineActive": true,
  "deadlineAt": "...",
  "latestStartAt": "...",
  "remainingKWh": 3.85,
  "maxA": 8,
  "priority": "MUST"
}
```

Adapter must never raise current above `maxA` for a deadline command.

## Required offline tests before Homey deployment

### T1 — deadline catch-up ignores PV shortage
Input:
- deadline active
- now >= latestStart
- remaining > 0
- maxA = 8
- flexExportBudgetW = 0
- charger connected

Expected:
- priority `MUST`
- mode `DEADLINE`
- requestedA `8`
- never `0` merely because PV/export is zero

### T2 — opportunity remains PV limited
Input:
- before latestStart
- opportunity active
- flexExportBudgetW = 3500

Expected requestedA: `0`

Input flexExportBudgetW = 5000
Expected requestedA: `7` (floor(5000/690), capped 16)

### T3 — maxA cap
Input:
- deadline catch-up
- maxA = 8

Expected requestedA: never > 8.

### T4 — normal 5-minute cadence does not stale
For a producer update at t=0 and actuator triggers at t=121 s, t=240 s, t=299 s:
Expected: inputs remain fresh.

For no producer update for >420 s:
Expected: fail closed to 0 A.

### T5 — revision/gate safety retained
Schema mismatch, revision mismatch, gate failure or genuinely stale producer must still fail closed.

## Homey deployment gate

Do not deploy until:
1. actual current Homey Core source and actuator source are captured into version-controlled source files;
2. candidate changes are applied to those exact sources;
3. offline tests T1–T5 pass;
4. resulting source hashes are recorded;
5. only then provision/update Homey once;
6. run one controlled 8 A deadline validation, read-only observation afterwards.

## Expected live validation

With a deadline already beyond latest-start and maxA=8:
- next Core tick: `MUST / TESLA_CHARGE_DEADLINE`
- EV control: `requestedA=8`
- gate: PASS
- actuator: write 8 A (or NOOP if already 8)
- Easee: charging, approximately 3×8 A / ~5.5 kW
- no automatic `STALE_INPUT` stop between ordinary 5-minute Core ticks

No physical Homey writes were performed while preparing this document.

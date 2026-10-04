# Constrained Replay V0.1 — deterministic EV export attribution

Status: **CANDIDATE / READ_ONLY — runtime validation required before production baseline**

## Purpose

Constrained Replay V0.1 answers a narrower question than the existing PV
surplus absorption backtest:

> For an observed export interval, was additional EV absorption impossible,
> blocked by a recorded constraint, or feasible but not taken?

The replay is deterministic. It does not ask an LLM to infer feasibility and it
never changes planner, Homey, Gate, actuator or device state.

Canonical source:

`services/pi/history/constrained_replay_v0_1.py`

CLI after normal Pi deployment:

`ems-constrained-replay`

Schema:

`EMS_PI_CONSTRAINED_REPLAY_V0.1`

## V0.1 scope

V0.1 is explicitly:

`scope = EV_EXPORT_ONLY`

This means the classifications are relative to the EV path only. In
particular, `UNAVOIDABLE_EXPORT` means that the modeled EV path could not
absorb more energy under the recorded state/constraints. It does **not** mean
that no future WW, Heating, appliance or battery flexibility could have used
that energy.

WW, Heating, appliances and battery remain outside V0.1 counterfactual
classification.

## Evidence authority

The replay reads only canonical local durable history:

```text
ems-history.sqlite/measurements
        +
ems-history.sqlite/ev_control_events
        +
ems-history.sqlite/semantic_events
        ↓
Constrained Replay V0.1
```

P1 remains authoritative for actual grid import/export.

EV control events provide the recorded Homey execution context, including
requested phase/current, Gate/actuator state and the already-archived realtime
controller evidence such as:

- phase mode;
- requested/offered current;
- EV envelope max current;
- 2-minute rolling available power and readiness;
- phase/current reason;
- mode dwell timestamp;
- physical target settled state;
- deadline-guard state.

Semantic Event History is attached as bounded historical context around replay
windows. It is provenance evidence and is not used to invent a missing control
decision.

Control evidence older than the bounded alignment horizon is not silently
carried forward. Such export becomes `INSUFFICIENT_EVIDENCE`.

## Classifications

### UNAVOIDABLE_EXPORT

Used only when the EV path has no modeled remaining ability to absorb the
export under the recorded physical state. Examples:

- Tesla not connected;
- already at 3P / 16 A;
- residual export is below the next usable current step once the recorded
  import preference is respected.

This classification is always scoped to EV-only V0.1.

### CONSTRAINT_DRIVEN_EXPORT

The EV is potentially relevant, but a recorded constraint explains why the
export could not safely be absorbed at that decision point. Examples:

- OFF re-entry dwell;
- rolling-power signal not ready;
- 1P→3P dwell or phase-transition execution;
- physical target not yet settled;
- bounded same-phase current ramp;
- Pi EV envelope/current cap;
- deadline current cap;
- Gate fail-closed;
- Easee offered current below requested current.

No additional feasible-capture kWh is claimed while such a recorded constraint
is binding.

### REAL_MISSED_OPPORTUNITY

Used conservatively and only when time-aligned durable control evidence shows:

1. Tesla connected;
2. EV opportunity eligible/applied;
3. Gate is not blocking;
4. no recorded phase/dwell/settling/downstream constraint explains the gap;
5. the same recorded available-power state supports a higher safe phase/current
   target than was used.

The replay then computes only the bounded additional energy that could fit in
the observed export interval. This is the deterministic evidence that a later
AI analyst may explain; the LLM is not allowed to manufacture this category.

Actuator/phase-transition failures with a valid positive request may also be
classified as a real missed opportunity, but only with medium confidence and
only up to the smaller of observed export and requested-but-undelivered power.

### INSUFFICIENT_EVIDENCE

Used when required control state is absent, stale or ambiguous. Missing
evidence is never converted into a performance conclusion.

## Temporal rules

V0.1 uses high-resolution operational measurements, not the 15-minute
capacity-planning backtest, because phase dwell/current response cannot be
judged safely at quarter-hour granularity.

Defaults:

- minimum export for classification: 250 W;
- maximum measurement interval: 120 s;
- maximum EV-control evidence age: 90 s;
- 1P mapping: 230 W/A;
- 3P mapping: 690 W/A;
- EV current range: 6–16 A;
- predictive import preference: +300 W;
- phase/minimum viability margin: 250 W;
- default OFF re-entry dwell: 120 s;
- default 1P→3P dwell: 180 s.

Where recorded controller values exist, the replay uses the event-specific
values rather than inventing replacements.

## Output

The report contains:

- observed export;
- export energy per classification;
- bounded additional feasible capture;
- reason-energy attribution;
- grouped export windows;
- phase/current reasons;
- nearby semantic events;
- evidence coverage and explicit limitations.

Default derived output:

`/home/jeroen/ems/data/constrained-replay-v0.1-YYYY-MM-DD.json`

This is derived analysis state. It is not planner input.

## Relationship to PV surplus absorption backtest

The existing `pv_surplus_absorption_backtest.py` remains useful and is not
silently replaced.

It answers a longer-horizon capacity/allocation question such as how much
historical export could technically be absorbed by EV/WW/battery scenarios.

Constrained Replay answers a different post-hoc control-performance question:
given the actual short-timescale state and recorded constraints, why did this
specific export occur and was additional EV capture feasible?

The two analyses may later be combined, but they must not be treated as
interchangeable evidence.

## Control boundary

Hard invariants:

- read-only SQLite access;
- no Homey/network calls;
- no planner decision;
- no Logic write;
- no device write;
- no control contract consumed by runtime control;
- `controlWrites=false` in output.

Future AI integration may expose replay results as evidence, but the AI may
only interpret the deterministic result. It may not rewrite the replay
classification.

## V0.1 acceptance

Repository:

- Architecture Gate PASS;
- direct Python replay regression PASS;
- existing history/replay regressions PASS;
- Security Scan PASS when applicable.

Runtime, after normal Pi deployment:

1. `ems-constrained-replay today --no-write-output` exits 0;
2. source in `/home/jeroen/ems/runtime/history/` matches GitHub;
3. the command reads canonical SQLite read-only;
4. no Homey/API/device call is made;
5. report contains all four classifications in its schema contract even when
   one has zero energy;
6. results for 2026-10-04 are reviewed against the already manually analysed
   EV/PV export behaviour before AI integration is enabled.

## Next step after runtime validation

Only after V0.1 runtime output is validated should the AI evidence builder gain
a bounded `constrainedReplay` field.

The proactive/daily analyst remains a later step. It must consume deterministic
replay results rather than independently guessing missed opportunities.

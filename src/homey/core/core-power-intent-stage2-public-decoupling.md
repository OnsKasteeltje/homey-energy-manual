# Core → Power Intent stage 2: public-state decoupling

Status: **DEPLOYED / FAN-OUT FIX VERIFIED / EV TRIGGER CORRECTION REQUIRED**

Date: 2026-08-29

## Problem

The original stage-2 fan-out issue was that freshness-only updates of `EM2_Public_State` could wake the complete Power Intent / Gate / Adapter chain even when EMS control semantics had not changed.

`EM2_Public_State` must remain useful as an externally visible publication/freshness heartbeat, but it must not be used as an internal control bus.

## Deployed trigger contract

The active runtime now implements the intended public-state decoupling:

1. Core remains the single deliberate 5-minute telemetry reader.
2. Core may continue updating `EM2_Public_State` for publication/freshness purposes.
3. `EM v2 | 20 Power Intent | P1 v0.2.3 TARGETED-READ LOW-LOAD` no longer triggers on `EM2_Public_State changed`.
4. The active P1 trigger is the semantic `EM2_Control_WW` change event.
5. P1 performs only targeted Logic reads for the authoritative State, Decision, Control-WW and prior Power-Intent variables.
6. P1 suppresses duplicate work when the prior output already carries the same source revision and remains valid.
7. The emitted contract explicitly records `triggerContract: EM2_CONTROL_WW_SEMANTIC_REVISION` and `publicStateDependency: false`.

## Runtime verification — 2026-08-29

An exact-ID read of the active Homey Advanced Flow confirmed:

- flow ID `19d9d8a6-ec32-4639-be5e-71e9f034d31b`;
- enabled and not broken;
- trigger variable `EM2_Control_WW`;
- no `EM2_Public_State` trigger dependency;
- targeted Logic reads only;
- no device reads, device writes, network calls or recurring poller inside P1;
- source-revision idempotency remains active.

This verifies the control-side fan-out removal without requiring a new Homey runtime write or actuator smoke.

## Corrective finding — EV semantic trigger regression

A later Tesla runtime diagnosis on 2026-08-29 exposed an important functional regression in the replacement trigger contract.

Core can change the Tesla decision between `HOLD`, `TESLA_BUFFER_EXPORT` and `TESLA_CHARGE_OPPORTUNITY` while `EM2_Control_WW` remains semantically unchanged. Because Power Intent P1 v0.2.3 wakes only on `EM2_Control_WW`, a Tesla-only decision change can fail to recompute `EM2_Power_Intent`.

Observed runtime was consistent with this failure mode: strong P1 export was present while Easee remained explicitly paused at 0 A after earlier charging activity. The downstream EV Adapter, Gate and Actuator were still behaving fail-closed; the missing wake-up is upstream of them.

Therefore the public-state decoupling itself remains correct, but `EM2_Control_WW` is **not sufficient as the sole semantic trigger for combined EV+WW Power Intent**.

Do not restore `EM2_Public_State` as the control trigger.

Preferred correction: introduce a narrow semantic EV-control signal produced only after Core has completed its aligned State/Decision/control writes, or otherwise use a dual semantic trigger with a settle/revision-alignment guard. Any correction must retain targeted reads, semantic suppression and the existing load budget.

The proposed SHADOW signal-conditioning design is documented in:

`src/homey/ev/ev-surplus-smoother-shadow-v0.1.md`

## Publisher-side decoupling

The active `EM v2 | 40 Data | Publisher v1.0.10 SCHEDULED LOW-LOAD` was also read by exact ID and verified as:

- enabled and not broken;
- scheduled every 15 minutes with a small stagger;
- no longer event-triggered by every `EM2_Public_State` change;
- five targeted Logic reads;
- hard minimum 15-minute publication interval;
- revision/heartbeat gate before external publication.

Therefore a normal Core freshness update no longer causes an immediate website-publication wake-up.

## Resulting fan-out boundary

The intended steady-state boundary remains:

```text
Core telemetry tick
  ├─ publication/freshness state → bounded 15-minute Publisher
  └─ semantic control change → Power Intent
       → P1 Pre-EV Gate
       → EV Power Adapter
       → EV Adapter Gate
       → guarded EV actuator path
```

The currently deployed `EM2_Control_WW`-only trigger is an incomplete implementation of the semantic-control branch and requires correction for Tesla-only decision changes.

A timestamp-only/freshness-only public-state change still does not justify a control cascade.

## Safety constraints preserved

- No actuator ownership change was made by this decoupling.
- No Easee, boiler, Victron, Quatt or other physical write was added.
- EV actuator LIVE/revision guards remain unchanged.
- Fail-closed behaviour remains unchanged.
- Watchdog, history/evidence, Quooker diagnostics and other isolated load sources remain subject to staged reintroduction and the load budget.

## Step-4 conclusion

The two original structural fan-out amplifiers remain removed:

1. `EM2_Public_State` is no longer a control trigger for Power Intent.
2. Publisher is no longer event-driven by every public-state update and is bounded to a 15-minute schedule.

However, step 4 now carries a **corrective action**: replace the too-narrow `EM2_Control_WW`-only Power Intent trigger with a narrow semantic trigger contract that covers EV as well as WW without restoring freshness fan-out.

Remaining fan-out candidates are in the OFF isolation set. They must not be re-enabled until they have an explicit load-budget entry and pass staged soak validation.

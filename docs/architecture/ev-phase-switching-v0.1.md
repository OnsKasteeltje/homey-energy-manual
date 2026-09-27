# EV 1P/3P phase switching

Status: phase-aware EV contract and writer v0.4.2 are LIVE; fresh natural 1P↔3P validation of the stale-readback latency correction remains pending.

## Functional contract

The EMS decides only:

- `OFF`
- `1P + A`
- `3P + A`

The EMS does not select L1/L2/L3. In 1P operation the physical phase remains owned by Easee/Equalizer.

Total net P1 power is authoritative for PV opportunity control. Per-phase P1 remains observability/safety context, not EMS phase-selection policy.

## Ownership

```text
P1 / Pi policy
      ↓
EV phase/current policy
      ↓
Power Intent
      ↓
EV Adapter
      ↓
EV Gate
      ↓
sole Homey EV Actuator
      ├─ native Homey: pause/resume/current/circuit cap
      └─ minimal Easee Cloud call: set_phase_mode only
      ↓
Easee / Equalizer local fuse + physical phase selection
      ↓
Tesla
```

No independent Pi/device writer is introduced.

## Pi phase policy

`/control/current.realtime.ev.phasePolicy` exposes:

- schema `EMS_PI_EV_PHASE_POLICY_V0.1`
- allowed modes `OFF | 1P | 3P`
- current range 6..16 A
- 1P start 1500 W
- 1P stop 1100 W
- 3P enter 4400 W
- 3P leave 3600 W
- minimum mode dwell 120 s
- physical phase owner `EASEE_EQUALIZER`

Current sizing:

- 1P: `floor(availableTotalW / 230)`
- 3P: `floor(availableTotalW / 690)`
- clamp 6..16 A

When EV is active, actual commanded EV power is added back to total P1 to reconstruct available PV. Previous SHADOW recommendations are never treated as physical load.

Canonical selector:

`services/pi/planner/ev/ev_phase_selector_shadow_v0.2.mjs`

## Homey SHADOW chain

Deployed into the existing flow IDs:

- Bridge `8bf53fdb-76f4-47db-8ccb-773ac515f06e` → production v1.4.1 FAST-IMPORT-CUTBACK; candidate v1.4.4 PAUSE-AWARE-PHASE-SHADOW
- Adapter `953e9b18-3576-4557-b940-ed4a64eb2516` → v0.1.11 PHASE-SHADOW
- Gate `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` → v0.2.12 PHASE-SHADOW
- physical actuator remains `fea23193-a03f-49dd-9780-7e72ee48747d` v0.2.15 until LIVE promotion

Validated live SHADOW example:

- reconstructed available PV: 4336 W
- previous phase mode: 3P
- result: `3P + 6 A`
- reason: `HOLD`
- 4336 W is below 4400 W enter-3P but above 3600 W leave-3P
- Bridge → Intent → Adapter → Gate all coherent
- phase Gate PASS
- production Gate PASS

This confirms the intended hysteresis behavior.

## Easee phase interface

Homey's Easee app exposes phase mode as readback:

- `Auto`
- `Locked to single phase`
- `Locked to three phase`

The app does not expose a writable phase-mode Flow card.

The official Easee API provides:

`POST /api/chargers/{serialNumber}/commands/set_phase_mode`

with:

- 1 = locked 1P
- 2 = Auto
- 3 = locked 3P

EMS uses only locked 1P or locked 3P for commanded modes.

References:

- https://developer.easee.com/reference/charger_set_phase_mode
- https://developer.easee.com/reference/account_authenticate
- https://developer.easee.com/reference/account_refreshtoken

## Physical commissioning 2026-09-26

Charger: `ECHM6B9F`

Observed settings:

- grid type `TN_3_PHASE`
- main fuse 25 A
- circuit fuse 20 A
- max charger current 16 A

### Locked 1P

Commissioning precondition:

- session `plugged_in_paused`
- offered 0 A
- charger power 0 W
- initial phase mode `Auto`

Commanded locked 1P and confirmed Homey readback:

`Locked to single phase`

After resume/current commissioning, Tesla physically charged at approximately:

- phase 1: ~0 A
- phase 2: ~0 A
- phase 3: ~6 A
- charger power: ~1.4 kW

Physical result: **1x6 A confirmed**.

This proves that Easee/Equalizer selected the actual physical phase; EMS did not choose L3.

### Locked 3P restore

The charger was paused again and commanded to locked 3P.

Homey readback confirmed:

`Locked to three phase`

After resuming at 6 A, charging stabilized at approximately 3x6 A / 4.3 kW.

Physical result: **3P restore confirmed**.

## Commissioning finding: 0 A is not a stable pause

Homey Insights showed repeatedly:

```text
0 A
  ↓ ~1 minute
32 A charger target reset
  ↓ production actuator active
bounded target re-applied
```

With the production actuator temporarily disabled, that reset was able to result in approximately 3x16 A / 11.3 kW.

Therefore dynamic charger current 0 A alone is **not** a safe transition boundary.

Native `Pause Charging` remained stable beyond that reset interval:

- `plugged_in_paused`
- offered 0 A
- measured 0 W

Fail-closed for phase transitions therefore means **pause the charging session**, not merely write 0 A.

## Commissioning finding: resume resets charger current

The Easee app implementation documents and commissioning confirmed that `resume_charging` resets the dynamic charger-current limit.

Observed sequence:

```text
paused, target 6 A
  ↓ resume
target becomes 32 A
  ↓ desired current re-applied
target 6 A
```

The car initially remained at 0 W during the observed reset, but LIVE design must not depend on this timing.

## Canonical transition state machine v0.4

Canonical pure logic:

`src/homey/actuators/ev-power/ev-phase-transition-v0.4.mjs`

Current transition:

```text
PAUSE_SESSION
  ↓ confirmed plugged_in_paused + offered <=1 A + power <=250 W
SET_PHASE_MODE
  ↓ Homey readback confirms requested locked phase
DEADTIME
  ↓ 5 s
SET_TRANSITION_CIRCUIT_CAP
  ↓ native Homey symmetric circuit limit A/A/A confirmed
RESUME_SESSION
  ↓ Easee may reset charger-current target
SET_CURRENT desired A
  ↓ desired A + charging confirmed
RESTORE_CIRCUIT_CAP
  ↓ original circuit limit confirmed
STABLE
```

The transition captures the original dynamic circuit-current limit before changing it. Current commissioning value is 40 A.

The temporary circuit cap is symmetric, so it does not select a physical phase. It is only a transient safety ceiling during the Easee resume-current reset.

If execution fails while the temporary cap is active, leaving the lower circuit cap in place is fail-safe. Recovery can restore the captured original value after the session is paused.

## Homey-first write policy

Native Homey remains responsible for:

- pause charging
- resume charging
- dynamic charger current
- symmetric dynamic circuit-current cap
- symmetric circuit-current restore
- device/readback confirmation

Custom Easee Cloud is used only because Homey does not expose `set_phase_mode`.

Canonical cloud helper:

`src/homey/actuators/ev-power/easee-phase-cloud-v0.3.mjs`

It supports only:

- rotating Easee token refresh
- locked 1P/3P `set_phase_mode`

It contains no current control, circuit control, pause/resume logic or EMS policy.

## Easee credentials

No username/password/token is committed to GitHub.

One-time bootstrap:

`services/pi/commissioning/bootstrap_easee_homey_tokens.py`

The bootstrap:

1. prompts username/password locally on the Pi;
2. authenticates once against Easee;
3. stores only access token, rotating refresh token and expiry in private Homey Logic;
4. does not store username/password.

Homey token variables:

- `EM2_Easee_Access_Token`
- `EM2_Easee_Refresh_Token`
- `EM2_Easee_Access_Expires_At`

Easee access tokens expire; refresh tokens rotate and the newest refresh token must replace the previous one.

## LIVE gate

Do not promote phase switching into the sole EV Actuator until all are true:

- v0.4 transition tests PASS
- phase cloud token refresh tests PASS
- architecture gate PASS
- token bootstrap succeeds on Homey
- Homey actuator candidate performs requested/commanded/confirmed separation
- native circuit-cap and restore are verified in SHADOW/commissioning
- phase command is issued only while session pause is confirmed
- 1P/3P readback confirmation is mandatory
- timeout/failure pauses session fail-closed
- deadline charging remains 3P-capable and bounded by deadline max A
- no other automatic EV writer exists

## Current production state

Automatic phase-aware EV execution is LIVE through the single Homey actuator path.

Current observed production chain on 2026-09-26:

- Bridge policy revision `PI_DYNAMIC_PLANNER_BRIDGE_V1.5.3_PHASE_AUTHORITY`
- Adapter `EM2_EV_POWER_ADAPTER_V0.2`
- Gate `EM2_EV_ADAPTER_GATE_V0.3`
- Actuator `EM2_EV_ACTUATOR_V0.4.2_PHASE_WRITER`

The sole-writer invariant remains unchanged: Pi decides policy/power intent; Homey owns physical execution.


## Realtime P1 import cutback v1.4.1

Commissioning exposed a separate production-control weakness while PV changed quickly: the previous bridge reduced EV current by only 1 A per control cycle regardless of import magnitude. A live example reached approximately +3.0 kW net import before successive cycles reduced the charger target.

Bridge v1.4.1 keeps upward PV capture conservative at +1 A per cycle, but makes downward correction proportional:

`reductionA = ceil((gridImportW - 250 W deadband) / 690 W per 3P amp)`

If the resulting current would be below 6 A, opportunity charging goes directly to 0 A.

This change affects only the existing fixed-3P production current controller. It does not activate phase switching and does not alter the phase SHADOW contract.

A controlled physical validation attempt was limited by Easee/Equalizer itself: when charger target was raised to 12 A, Equalizer held offered current at 6 A while the house was still exporting. Equalizer safety was deliberately not bypassed.


## Confirmed phase readback candidate v1.4.2

Before phase switching can become LIVE, active EV load reconstruction must use the confirmed physical mode rather than assuming 3P.

Candidate bridge:

`src/homey/power-intent/pi-dynamic-planner-bridge-v1.4.4.pause-aware-phase-shadow.js`

The bridge reads Easee `phaseMode` from the Homey device/settings API and normalizes:

- `Locked to single phase` → 1P
- `Locked to three phase` → 3P
- `Auto` or unknown → unconfirmed

For active charging:

`actualEvW = currentA × 230 W × confirmedPhaseCount`

where confirmed phase count is 1 or 3.

If an active charger has no confirmed locked phase readback, only phase SHADOW fails closed with `PHASE_READBACK_UNCONFIRMED`; the proven fixed-3P production current controller remains unchanged.

This candidate must pass Pi regression tests before deployment into the existing Homey Bridge flow.


## Runtime connectivity ownership correction

A post-drive validation exposed that the Pi realtime envelope still gated opportunity charging on `plan.tesla.connectedNow`, which reflects connectivity at planner-build time. Homey live state simultaneously showed `plugged_in_paused`.

That coupling is removed in realtime envelope v0.4.

Policy ownership is now:

- Pi: whether realtime PV opportunity is allowed by strategy/deadline policy;
- Homey/Easee live `evcharger_charging_state`: whether the car is physically connected and execution is possible.

The Pi envelope now exposes `planConnectedAtBuild` only as observability and declares `liveConnectivityOwner = HOMEY_EASEE_CHARGE_STATE`.

This allows a Tesla that arrives after planner build to participate in realtime PV capture without waiting for a planner rebuild, while physical execution still fails closed when Homey does not observe a connected charger state.

Phase-mode readback is also observability and is therefore evaluated independently of realtime envelope eligibility in Bridge v1.4.3.


## Pause-aware physical EV reconstruction

Validation of Bridge v1.4.3 while the charger was physically paused exposed that the previous realtime controller command could remain non-zero even though Easee reported:

- `plugged_in_paused`
- target charger current 0 A
- offered current 0 A
- charger power 0 W

The phase SHADOW had therefore incorrectly reconstructed physical EV load from stale controller state.

Bridge v1.4.4 separates:

- `controllerStateA`: previous realtime command used only by the proven fixed-3P production loop;
- `actualProductionA`: physical add-back used by phase SHADOW.

For phase SHADOW:

- `plugged_in_charging` → physical add-back may use controller current;
- `plugged_in_paused` or `plugged_in` → physical add-back is 0 A.

This keeps the production controller unchanged while preventing fictitious EV load from inflating reconstructed PV opportunity during a paused session.


## v1.4.4 + actuator v0.3.0 no-write validation

Bridge v1.4.4 was deployed with the physical actuator disabled. Live validation while Easee was `plugged_in_paused` confirmed:

- charger target 0 A
- offered 0 A
- charger power 0 W
- confirmed phase readback remains locked 3P
- P1 export approximately 5.9 kW

The existing actuator flow was then replaced in-place by:

`EM v2 | 60 Actuator | EV Power v0.3.0 PHASE-CANDIDATE [NO-WRITE]`

The candidate topology contains only Start / Gate-change trigger / HomeyScript / note. It contains no Easee action cards and its source contains no physical device or Cloud write calls.

Published control evidence showed:

- actuator status `PHASE_CANDIDATE`
- phase candidate target: 7 A
- next action: represented by reason `PAUSED_RESUME_REQUIRES_SAFETY_CAP`
- physicalWritePerformed: false
- live Easee state: `plugged_in_paused`

The legacy production-current contract simultaneously still exposed 16 A / 11.04 kW because Bridge/Adapter/Gate production semantics are still fixed-3P while the new phase selector is shadow-only.

This is intentional evidence for the next gate: phase mode + A must be promoted into the authoritative Adapter/Gate contract before any phase-capable writer becomes LIVE. The actuator must not choose between two competing desired-current semantics.


## Phase-authority control contract

After the no-write actuator candidate exposed that the legacy production path could still report a fixed-3P target while phase SHADOW requested a different current, the chain is being promoted to one authoritative EV command.

Prepared contract:

- Bridge v1.5.3: `EM2_EV_PHASE_CONTROL_V0.1`
  - authoritative `OFF | 1P | 3P`
  - `phase_requested_A`
  - `phase_requested_W`
  - `target_W` derives from the same mode/current pair
  - deadline execution always projects to 3P
  - explicit `controlRevision` includes phase mode and current
- Adapter v0.2.0: `EM2_EV_POWER_ADAPTER_V0.2`
  - does not infer current from an assumed 3-phase watt target
  - validates exact mode/current/power mapping
  - emits `EM2_EV_PHASE_COMMAND_V0.1`
- Gate v0.3.0: `EM2_EV_ADAPTER_GATE_V0.3`
  - phase mode/current/power alignment is part of `finalStatus`
  - no separate observability-only phase authority remains
- Actuator v0.3.1 candidate:
  - consumes only Adapter v0.2 / Gate v0.3 command authority
  - remains hard no-write during validation

The legacy `phase_*_shadow` fields may remain temporarily in Power Intent for comparison, but they are no longer allowed to compete with the authoritative command.

### Cutover safety rule

The authoritative Bridge/Adapter/Gate contract may be promoted while actuator v0.3.1 remains no-write. Physical phase execution is a separate later gate.

This preserves the single-writer invariant and allows semantic validation of the complete phase-aware control chain before any automatic phase or charger-session action is enabled.


## Writer v0.4.0 prepared, not yet live

A stateful physical-writer candidate now exists at:

`src/homey/actuators/ev-power/ev-power-v0.4.0.phase-writer.js`

It is deliberately shipped with:

`PHASE_EXECUTION_ENABLED=false`

so repository validation cannot yet cause physical execution.

Writer design:

- one short transition step per HomeyScript invocation;
- persistent transition stage in `EM2_EV_Actuator_Status`;
- bounded self-retrigger between steps;
- overall transition timeout 90 s;
- phase confirmation timeout 30 s;
- 5 s deadtime after confirmed phase change;
- native Homey Easee action cards for:
  - Pause Charging
  - Resume Charging
  - Set dynamic circuit current
  - Set dynamic charger current
- Easee Cloud only for locked phase-mode command;
- rotating access/refresh-token update stays inside private Homey Logic;
- no password or username is stored in the writer;
- no direct `setCapabilityValue()` path exists.

Required transition remains:

`PAUSE -> phase command -> confirmed locked phase -> 5 s deadtime -> temporary symmetric circuit cap -> RESUME -> desired charger current -> charging confirmation -> restore original circuit cap -> STABLE`

The next gate is regression plus armed-disabled deployment. Physical cutover requires a separate explicit promotion of `PHASE_EXECUTION_ENABLED`.


## Live runtime corrections before 3P → 1P observation

Two commissioning findings were incorporated before observing the natural solar-decline transition.

### Homey action-card invocation

HomeyScript action execution now uses the current full Flow Card IDs, for example:

- `homey:device:<easee-id>:pauseCharging`
- `homey:device:<easee-id>:resumeCharging`
- `homey:device:<easee-id>:circuitCurrentControl`
- `homey:device:<easee-id>:setDynamicChargerCurrent`

The writer calls `Homey.flow.runFlowCardAction({id,args})`; it no longer supplies a separate legacy `uri`.

A live proof test lowered charger current to 7 A manually, triggered only the Bridge, and the LIVE actuator independently returned the charger target to 8 A.

### Physical EV-load reconstruction

Bridge v1.5.3 keeps P1 total net power authoritative, but the EV load already being consumed is now reconstructed from live Easee `measure_current.offered` together with confirmed 1P/3P mode. The previous controller command is only a fallback.

This prevents a stale controller target from inflating available PV after commissioning/manual intervention.

### Commissioning monitor

The external Pi cutover monitor is not part of runtime control. It is now low-rate/read-only after its initial trigger:

- one persisted actuator-status read every 5 s;
- no repeated device polling;
- no external fallback-trigger loop.

Normal runtime phase control remains entirely Bridge → Adapter → Gate → sole LIVE actuator.

### Natural 3P → 1P policy

With a 120 s minimum mode dwell:

- 3P → 1P when reconstructed available total power is below 3600 W and at least 1500 W;
- 3P → OFF below 1500 W;
- 1P → 3P at or above 4400 W;
- 1P → OFF below 1100 W.

The 3P → 1P physical transition is:

`pause → locked 1P command → confirmed 1P → 5 s deadtime → temporary symmetric circuit cap → resume → requested current → charging confirmation → restore original circuit cap`.

## Stale / transient Easee handling

Keep this deliberately simple.

### Energy authority

P1 total net grid power remains authoritative for available-energy decisions.

Easee telemetry is not used to decide how much PV is available.

### Connection authority

Easee connection state is used directly:

- `plugged_in`
- `plugged_in_paused`
- `plugged_in_charging`

mean connected.

There is no time-based disconnect grace or debounce timer.

Only clear active electrical evidence may override a contradictory non-connected state:

- `evcharger_charging = true`
- offered current > 1 A
- charger power > 250 W

This covers the narrow stale-state case where Easee reports a contradictory connection label while current is demonstrably flowing, without inventing a separate connectivity state machine.

### Transition readback

The former generic 90 s transition timeout is not a control-failure boundary.

- 90 s is observability only (`transitionSlow`);
- slow phase confirmation retries while the session remains safely paused;
- a failed transition may recover from a known-safe paused / zero-load / valid-circuit boundary;
- stale or slow Easee readback may delay a hardware transition but must not permanently deadlock the EV writer.

This keeps the rule set small:

`P1 decides power; Easee confirms hardware state; safe transitions retry instead of deadlocking.`

## v0.4.2 stale phase-readback correction

Live observation on 2026-09-26 exposed a long paused interval even though Pi continued to request positive EV power and Adapter/Gate remained executable/PASS. The v0.4.1 writer status showed:

- transition state `DEADTIME`;
- transition age >120 s;
- Easee session safely `plugged_in_paused`;
- requested/confirmed mode both eventually 3P;
- no transition failure.

The 5 s deadtime itself was not the cause. The long interval occurred before the writer obtained a usable phase confirmation.

Writer v0.4.2 keeps phase confirmation mandatory but changes the confirmation sources:

1. While charging, live per-phase current plus charger power may prove the already-active physical mode:
   - one active output phase -> 1P;
   - two or more active output phases -> 3P.
   This electrical proof prevents a stale Homey phase setting from creating an unnecessary same-phase pause.

2. During a real paused phase transition, Homey settings remain valid readback, but the writer may also query the official Easee Observations endpoint for observation id 38 (`PHASE MODE`). A matching cloud observation is latched for the remainder of that transition.

3. A successful phase-command HTTP response is still not treated as physical confirmation. Session pause, 5 s deadtime, temporary symmetric circuit cap, resume/current re-application, and circuit-cap restore remain unchanged.

4. Cloud phase observation is rate-bounded and queried only while safely paused in phase-confirmation stages.

Deployment uses the existing actuator Flow ID in place; no second writer is created. Guarded upgrade helper:

`services/pi/commissioning/upgrade_ev_phase_writer_v0_4_2.py`

Guarded production cutover completed successfully on 2026-09-26 from a stable 1P charging state. Post-deploy actuator status was `STABLE`, requested and confirmed mode were both `1P`, and confirmation source was `ELECTRICAL_TELEMETRY`. The existing Advanced Flow ID remained the sole EV writer. Earlier same-day v0.4.1 validation proved the full 3P→1P physical chain but also exposed the excessive paused transition duration that motivated v0.4.2. The next natural 1P↔3P event is the remaining live validation for the v0.4.2 latency improvement.


## v0.4.3 failed-transition circuit-cap recovery

Live validation on 2026-09-27 exposed a separate fail-closed recovery defect in
writer v0.4.2. The control chain itself was healthy:

- Pi realtime envelope: `allowed=true`, `PV_OPPORTUNITY`;
- P1 export: approximately 3.1-3.3 kW;
- Bridge authoritative phase control: `1P + 13 A`;
- Adapter: `EXECUTABLE`;
- Gate: `PASS`;
- Easee: `plugged_in_paused`, 0 A, 0 W.

The sole LIVE actuator rejected the positive command with
`CIRCUIT_LIMIT_BELOW_REQUEST` because Easee still reported a dynamic circuit
limit of 6 A.

Homey Insights established the preceding physical sequence:

- normal dynamic circuit limit was 20 A;
- during the interrupted transition it moved through 8 A to a temporary 6 A;
- Easee resume briefly reset charger target to 32 A, matching the already
  documented resume-reset behaviour;
- charging stopped again before `RESTORE_CIRCUIT_CAP` completed;
- the temporary 6 A circuit cap then remained in place.

The defect was in `safePausedRecovery`: a FAILED transition could be reset to
`STABLE` while clearing `originalCircuitA` before the original circuit limit
had been restored and confirmed. Once that value was lost, the writer correctly
refused a later 13 A request against the still-active 6 A circuit cap, but could
no longer restore the pre-transition baseline itself.

Writer v0.4.3 changes only this recovery boundary:

1. `originalCircuitA` is retained across FAILED state.
2. Recovery enters explicit `RECOVERING_CIRCUIT_CAP`.
3. The captured original circuit limit is written back while the session remains
   safely paused.
4. The writer returns to `STABLE` only after readback confirms that original
   limit.
5. A legacy/orphaned FAILED state with no captured original value remains
   fail-closed. It may resume only after an externally restored circuit limit is
   observed above the executable EV range (>16 A), proving that the observed
   value cannot itself be a temporary transition cap.
6. The writer never hardcodes or guesses a 20 A/40 A baseline.

Canonical sources:

- `src/homey/actuators/ev-power/ev-power-v0.4.3.phase-writer-live.js`
- `src/homey/actuators/ev-power/ev-phase-transition-v0.4.mjs`
- `services/pi/commissioning/upgrade_ev_phase_writer_v0_4_3.py`

The v0.4.3 upgrade helper supports both a normal quiescent STABLE upgrade and the
specific safely-paused orphaned-cap incident. In the latter case the helper
deploys the corrected writer but deliberately does not restore or guess a
baseline; operator recovery of the independently proven pre-transition limit is
a separate explicit action.

The guarded v0.4.3 upgrade was executed and validated on 2026-09-27. The orphaned
6 A cap was recovered to the independently proven 20 A baseline, and a full live
1P resume sequence subsequently restored the temporary transition cap back to
20 A. v0.4.3 is therefore the current production writer baseline for the next
change.


## v0.4.4 bounded transition runner

The next live 1P→3P opportunity on 2026-09-27 exposed a separate execution-model
problem. The phase policy itself behaved correctly: while charging 1P at about
3.7 kW, residual P1 export lifted reconstructed available power to roughly the
4.4 kW 3P entry threshold. The writer paused the charger as designed. However,
the state remained at `PAUSING` until an external/manual actuator trigger
occurred, even though Easee had already reached `plugged_in_paused / 0 A / 0 W`.

Further live observation showed the same pattern at later stages: the physical
write completed, but continuation depended on
`Homey.flow.triggerAdvancedFlow({id: FLOW_ID})` successfully starting the same
Advanced Flow again. While the writer waited for another invocation, realtime PV
continued changing, so a 3P request could already have fallen back to 1P before
the transition resumed. This turned a hardware transition that should take
seconds into a multi-minute paused interval.

Writer v0.4.4 removes inter-stage self-retrigger entirely. A required hardware
transition is one bounded actuator transaction inside one HomeyScript invocation:

`pause -> confirm paused -> set locked phase -> confirm phase -> 5 s deadtime
-> temporary symmetric circuit cap -> resume -> set charger current
-> confirm Easee accepted the opportunity -> restore original circuit cap -> STABLE`.

Safety and ownership remain unchanged:

- Bridge/Adapter/Gate still own the authoritative `OFF | 1P | 3P + A` command;
- P1 remains realtime energy authority;
- 1500/1100 W 1P and 4400/3600 W 3P hysteresis thresholds are unchanged;
- Easee Cloud remains phase-command/fallback phase-observation only;
- native Homey Easee cards remain pause/resume/current/circuit writers;
- the original circuit limit is captured before transition and restored on both
  success and failure;
- Tesla current/power is observability only and is never a success condition for opportunistic charging;
- a Tesla that remains at 0 W (for example because it is full or not requesting charge) is a healthy outcome as long as Easee has accepted the requested phase/current opportunity;
- a short RUNNING lock makes concurrent Gate-triggered invocations no-ops while
  one bounded transaction is active.

The writer deliberately re-reads the authoritative control contract while the
session is safely paused, before phase execution and again before resume. This
allows falling/rising PV to change the pending mode/current without waiting for
another Advanced Flow invocation. Up to three paused replans are allowed; an
unstable command beyond that fails closed, pauses the session and restores the
captured circuit baseline.

Canonical sources:

- `src/homey/actuators/ev-power/ev-power-v0.4.4.phase-writer-live.js`
- `services/pi/commissioning/upgrade_ev_phase_writer_v0_4_4.py`
- `tests/ev-phase-writer-v0.4.4-bounded.test.mjs`
- `tests/ev-phase-v044-upgrade-guard.test.mjs`

An initial guarded v0.4.4 deployment attempt on 2026-09-27 rolled back automatically because HomeyScript does not expose browser/node `setTimeout`; the bounded writer had used it for polling/deadtime. No v0.4.4 writer remained LIVE after rollback. The corrected source uses HomeyScript's native global `await wait(ms)` primitive, and deployment now rejects any v0.4.4 source containing `setTimeout(`.

A second guarded attempt correctly stopped before deployment because the original 10-second quiescence guard treated a normal same-phase PV current change as instability. For v0.4.4 source replacement, quiescence now means stable phase/confirmed-phase, STABLE transition state, unchanged normal circuit cap and unchanged charge-state class; `targetA` and `controlRevision` may advance if Easee remains physically coherent (`offeredA` follows its current charger target). This preserves protection against an in-flight phase transition without requiring the realtime PV current loop to freeze.

Production remains on v0.4.3 until the corrected guarded v0.4.4 upgrade is executed from that structural quiescent state and the next natural phase transition is observed.


### Opportunistic EV boundary: offer, not consumption

The EMS does not command the Tesla to consume energy. For opportunistic PV charging it only exposes an allowed charging opportunity through Easee: selected phase mode, permitted current and session enablement. Tesla remains free to draw zero, partial or full offered current.

Therefore Tesla behaviour must never create a control-path timeout or failure. In particular:

- no minimum Tesla power is required after resume;
- no timeout waits for Tesla current/power;
- a full Tesla may remain at 0 W without causing pause/retry/fail-closed;
- Easee command acceptance/readback remains the actuator success boundary;
- actual Tesla current, power and electrically observed phase remain observability for later analysis only.

This rule is architectural, not merely a timeout tuning choice.

### Easee auth recovery on phase command

A live 2026-09-27 1P→3P opportunity proved the opportunity-only contract but failed before the phase write with `EASEE_HTTP_401`. The writer now treats a 401 from the Easee phase-command/phase-observation REST boundary as an authentication recovery event: it performs exactly one forced refresh using the current Homey-stored refresh token, persists the returned access/refresh pair, and retries the original request exactly once. Other HTTP errors do not enter this retry path. A second 401 still fails closed. Tesla consumption remains unrelated to this auth handling.

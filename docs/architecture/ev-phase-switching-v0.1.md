# EV 1P/3P phase switching

Status: SHADOW contract validated end-to-end; physical 1P and 3P commissioning passed; LIVE actuator integration not yet promoted.

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

Physical 1P and 3P are proven, but automatic phase switching is **not yet LIVE**.

Production remains:

- Bridge production v1.4.1 FAST-IMPORT-CUTBACK; v1.4.4 PAUSE-AWARE-PHASE-SHADOW pending regression validation
- Adapter v0.1.11 PHASE-SHADOW
- Gate v0.2.12 PHASE-SHADOW
- Actuator v0.2.15 CONTROL-AUTHORITY

Phase promotion requires an explicit actuator version bump after the remaining LIVE-gate checks pass.


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

- Bridge v1.5.1: `EM2_EV_PHASE_CONTROL_V0.1`
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

Bridge v1.5.1 keeps P1 total net power authoritative, but the EV load already being consumed is now reconstructed from live Easee `measure_current.offered` together with confirmed 1P/3P mode. The previous controller command is only a fallback.

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

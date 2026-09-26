# EV 1P/3P phase switching

Status: design validated, SHADOW implementation in progress, not LIVE.

## Functional contract

The EMS decision is:

- `OFF`
- `1P + A`
- `3P + A`

The EMS does not select L1/L2/L3 during 1P operation. Physical phase selection and fuse protection remain the responsibility of Easee/Equalizer.

Total net P1 power is the authoritative energy-control feedback signal. Per-phase P1 values remain observability/safety context, not the EMS selector for a physical 1P phase.

## Ownership

```text
P1 / planner policy
        ↓
EV phase/current policy
        ↓
Power Intent
        ↓
EV Adapter
        ↓
EV Gate
        ↓
sole EV Actuator
        ↓
Easee phase mode + dynamic charger current
        ↓
Easee Equalizer local phase/fuse safety
        ↓
Tesla
```

No second physical writer may be introduced.

## Easee interface research

Validated public interfaces:

- Easee command endpoint:
  `POST /api/chargers/{serialNumber}/commands/set_phase_mode`
  - 1 = locked to 1 phase
  - 2 = auto
  - 3 = locked to 3 phase
- Dynamic charger current remains the runtime current-control interface.
- Easee warns against frequent writes through the generic charger `/settings` endpoint.
- The existing Homey Easee action-card surface exposes dynamic charger/circuit current but currently does not expose Set Phase Mode.
- The historical Homey Easee implementation already reads charger observation 38 as `phaseMode`, so phase state exists in the integration even though a Flow write card is absent.
- evcc and Home Assistant both model charger phase mode explicitly rather than treating phase selection as an EMS optimization dimension.

References:
- https://developer.easee.com/reference/charger_set_phase_mode
- https://developer.easee.com/docs/current-limits-and-control
- https://developer.easee.com/reference/charger_set_dynamic_charger_current
- https://github.com/evcc-io/evcc/blob/master/charger/easee.go
- https://github.com/nordicopen/easee_hass/blob/master/custom_components/easee/services.yaml
- https://community.homey.app/t/app-pro-easee-charger-small-smart-full-of-power/31647?page=21

## Phase selector policy

Initial thresholds:

- 1P start: total available PV >= 1500 W
- 1P stop: total available PV < 1100 W
- 3P enter: total available PV >= 4400 W
- 3P leave: total available PV < 3600 W
- minimum mode dwell: 120 s
- current range: 6..16 A

For a physically idle EV:

`availableTotalW = max(0, -P1_total_W)`

For an active EV session:

`availableTotalW = max(0, -P1_total_W + actual EV commanded power)`

Previous SHADOW recommendations are never added back as physical load.

Current sizing:

- 1P: `floor(availableTotalW / 230)`
- 3P: `floor(availableTotalW / 690)`
- clamp to 6..16 A

The Equalizer may further limit actual current for local fuse/load safety.

## Stateful transition contract

A mode transition is not a simple write. Candidate LIVE actuator sequence:

1. validate fresh upstream intent and fresh PASS gate;
2. request 0 A / pause;
3. confirm charging current/power is effectively zero;
4. issue Easee phase-mode command;
5. confirm the requested phase mode;
6. apply dead-time;
7. resume/start session;
8. apply requested dynamic charger current;
9. separately record requested / commanded / confirmed state;
10. timeout or incoherent state -> fail closed to 0 A.

A 1P→3P transition may require a new/resumed charging session before the EV adopts three phases. This is therefore implemented as an explicit state machine.

## LIVE gate

Do not promote until:

- phase-mode command path is accessible from the existing sole EV Actuator;
- the Homey/Easee integration path does not create a second writer;
- phase-mode readback/confirmation is available;
- OFF→1P, 1P→3P, 3P→1P, and transition timeout are tested in SHADOW/replay;
- physical validation confirms current and phase behavior at Easee/Tesla;
- existing deadline behavior remains 3P-capable and fail-closed;
- architecture gate and EV regression suite pass.

## Current implementation

Canonical selector:
`services/pi/planner/ev/ev_phase_selector_shadow_v0.2.mjs`

One-shot observer:
`services/pi/planner/ev/run_ev_phase_shadow_once.mjs`

The selector is SHADOW-only and performs no device/control writes.


## Contract staging 2026-09-26

The Pi realtime EV envelope now carries additive SHADOW phase policy:

`realtime.ev.phasePolicy = EMS_PI_EV_PHASE_POLICY_V0.1`

It declares allowed modes, thresholds, mode dwell, current bounds and `EASEE_EQUALIZER` as physical phase owner. The existing production bridge ignores these additive fields.

Prepared non-live Homey candidates:

- `src/homey/power-intent/pi-dynamic-planner-bridge-v1.4.0.phase-shadow.js`
- `src/homey/adapters/ev-power/ev-power-v0.1.11.phase-shadow.js`
- `src/homey/validation/ev-power-adapter-gate-v0.2.12.phase-shadow.js`

The candidate bridge computes phase mode from fresh Homey P1 only inside the bounded Pi phase policy. It publishes `phase_mode_shadow` and `phase_requested_A_shadow` while retaining the existing fixed-3P production current target. Adapter and Gate validate and expose the phase contract without any physical phase write. The phase Gate result is observability-only until the LIVE release gate is explicitly completed.


## Homey SHADOW deployment 2026-09-26

The additive phase contract has been deployed into the existing production control-chain flow IDs without adding a writer:

- Bridge ID `8bf53fdb-76f4-47db-8ccb-773ac515f06e` → `v1.4.0 PHASE-SHADOW`
- Adapter ID `953e9b18-3576-4557-b940-ed4a64eb2516` → `v0.1.11 PHASE-SHADOW`
- Gate ID `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` → `v0.2.12 PHASE-SHADOW`

Topology, triggers, Logic variable IDs and the sole physical EV Actuator were left unchanged. The phase path is observability-only and performs no Easee phase-mode write.

Immediate live validation after the Bridge trigger showed the existing fixed-3P production path still functioning: Easee charged at approximately 3x6 A / 4.31 kW while net P1 power was approximately -14 W. This is production-current validation only; it is not yet proof of a physical 1P phase transition.


## End-to-end SHADOW validation 2026-09-26

Live evidence after deploying the SHADOW contract through the existing Homey chain:

- Bridge phase shadow: `3P + 6 A`
- reconstructed available total power: `4336 W`
- reason: `HOLD`
- Intent: `phase_mode_shadow=3P`, `phase_requested_A_shadow=6`
- Adapter phase shadow: valid `3P + 6 A`
- Gate phase shadow: `PASS`, all phase-shadow checks true
- production Gate: `PASS`, requested current `6 A`

This is the expected hysteresis case: `4336 W` is below the `enter3p_W=4400` threshold but above `leave3p_W=3600`. Because SHADOW was already in 3P, it correctly remains in 3P rather than oscillating back to 1P.

The physical production path remained the existing fixed-3P path during this validation.

## Homey Easee phase-mode interface constraint

Inspection of the public Easee Homey app source shows that charger observation 38 is decoded into the device setting `phaseMode`, but that setting is defined as an informational label and no capability listener / writable phase-mode Flow card is exposed. Therefore programmatically changing the Homey setting is not a valid charger command path.

The official Easee charger API does expose a dedicated runtime command:

`POST /api/chargers/{serialNumber}/commands/set_phase_mode`

with `1=1P`, `2=Auto`, `3=3P`.

LIVE promotion therefore remains blocked until the sole EV Actuator has a validated command transport for that dedicated Easee command plus phase-mode readback. No per-phase circuit-current workaround is promoted as the canonical design while physical phase ownership remains assigned to Easee/Equalizer.


## Stateful actuator preparation 2026-09-26

Prepared pure transition logic:

`src/homey/actuators/ev-power/ev-phase-transition-v0.1.mjs`

The transition machine has no Homey/Easee side effects. It emits only the next requested actuator action.

Canonical transition:

```text
STABLE
  ↓ mode differs
ZEROING
  ↓ target 0 A + low power/current confirmed
PHASE_COMMAND
  ↓ dedicated Easee command accepted
CONFIRMING
  ↓ Homey readback phaseMode matches requested locked mode
DEADTIME
  ↓ 5 s
APPLY_CURRENT
  ↓ charger target matches requested A
STABLE
```

Fail-closed conditions include invalid request, Gate not PASS, stale control, phase-command error, phase-confirm timeout, transition timeout and loss of phase confirmation.

Prepared official command transport:

`src/homey/actuators/ev-power/easee-phase-command-transport-v0.1.mjs`

This transport contains no credentials and no token persistence. It only knows the official command endpoint and accepts an injected Bearer access token. It never logs or returns the supplied token.

Easee authentication remains a deployment concern. Official cloud authentication returns a one-hour Bearer access token plus a rotating refresh token. No username, password, access token or refresh token may be committed to this repository.

Current Homey readback on charger `ECHM6B9F` confirmed:

- `phaseMode = Auto`
- grid type `TN_3_PHASE`
- main fuse `25 A`
- circuit fuse `20 A`
- max charger current `16 A`

For LIVE commissioning, requested `1P` must confirm as `Locked to single phase`; requested `3P` must confirm as `Locked to three phase`. `Auto` is valid observed state but is not treated as confirmation of a requested locked phase mode.


## Commissioning finding: zero current is not a stable pause boundary

During physical commissioning preparation on 2026-09-26, Homey Insights showed a repeatable pattern after writing charger current 0 A:

- target current 0 A;
- approximately one minute later the charger target returned to 32 A;
- while the production actuator was enabled it subsequently re-applied the bounded 6 A target;
- with the production actuator temporarily disabled, the restored target was able to produce approximately 3x16 A / 11.3 kW.

This means a charger-current value of 0 A by itself is not accepted as the canonical safe hardware state for phase switching.

Native Easee/Homey `Pause Charging` was then applied. The charger remained `plugged_in_paused`, offered 0 A and measured 0 W beyond the prior reset interval.

The transition contract is therefore superseded by v0.2:

`src/homey/actuators/ev-power/ev-phase-transition-v0.2.mjs`

Canonical sequence:

```text
PAUSE_SESSION
  ↓ confirmed plugged_in_paused + <=1 A offered + <=250 W
SET_PHASE_MODE
  ↓ confirmed locked phase readback
DEADTIME
  ↓
SET_CURRENT desired A while paused
  ↓ target current confirmed
RESUME_SESSION
  ↓ charging observed
STABLE
```

Fail-closed now means `PAUSE_SESSION`, not merely setting dynamic current to 0 A.

The one-shot commissioning tool at `services/pi/commissioning/ev_phase_commission.py` requires the same paused-session precondition before issuing a phase command.


## Physical commissioning: 1P command accepted 2026-09-26

With the production EV actuator disabled and the charger confirmed `plugged_in_paused`, offered current 0 A and measured power 0 W, the guarded commissioning tool sent the official Easee phase command for locked single-phase mode.

Observed Homey readback sequence:

- initial `phaseMode = Auto`
- then `phaseMode = Locked to single phase`
- commissioning result: `PASS`
- charger remained paused at 0 A / 0 W after the phase-mode change

This is the first physical proof that the dedicated Easee command path and Homey phase-mode readback work together on charger `ECHM6B9F`.

The next commissioning step is to pre-set 6 A while paused, resume the session, and validate that physical charging uses exactly one phase before restoring locked 3P.

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

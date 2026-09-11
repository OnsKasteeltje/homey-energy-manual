# EV Device Health Fail-safe v0.2

Date: 2026-09-11

## Purpose

Prevent stale or unavailable Easee/Homey telemetry from being interpreted as a trustworthy `plugged_out` / disconnected EV state.

The control-plane rule is now:

- fresh and internally consistent Easee telemetry -> normal EV semantics and `CONTROL_AVAILABLE`;
- unavailable device, stale telemetry, or confirmed P1/Easee contradiction -> `EV_STATUS_UNKNOWN` + `CONTROL_UNAVAILABLE`;
- `CONTROL_UNAVAILABLE` can never pass the EV Adapter Gate for a positive charging command;
- the existing EV actuator remains the only physical writer and fail-closes to 0 A when its gate is not PASS;
- recovery requires fresh device health before the gate can return to PASS.

## Homey runtime components

### `EM v2 | 82 Safety | EV Device Health v0.2 LIVE-GATE`

- enabled;
- one targeted Easee device read per run;
- runs every 2 minutes and on `EM2_State` change;
- no physical writes;
- reuses Logic variable `EM2_EV_Telemetry_Health`;
- checks Homey device availability, newest timestamp across live Easee telemetry capabilities, and the existing P1 three-phase contradiction heuristic;
- stale threshold: 5 minutes;
- publishes `EV_STATUS_UNKNOWN / CONTROL_UNAVAILABLE` when unsafe;
- emits a Homey notification only on unsafe/recovery transitions.

### `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.4 + HEALTH`

The gate now also consumes `EM2_EV_Telemetry_Health`. PASS requires a fresh health sample with:

- `schema = EM2_EV_DEVICE_HEALTH_V0.2`;
- `status = OK`;
- `controlSafe = true`;
- `controlAvailability = CONTROL_AVAILABLE`.

Any STALE / UNAVAILABLE / MISMATCH health state makes the gate FAIL. The existing EV actuator then uses its existing fail-closed path; no second Easee writer was added.

### `EM v2 | 81 Observability | EV Control Status v0.3 + HEALTH`

`docs/data/ev-control-status.json` now publishes the health state next to Gate and Actuator evidence, including telemetry age, device availability, normalized EV status and control availability.

## Recovery validation

Live evidence immediately after deployment showed:

- health `OK / FRESH_TELEMETRY`;
- normalized EV state `PLUGGED_IN_PAUSED`;
- `CONTROL_AVAILABLE`;
- EV Gate PASS and revision coherent;
- EV target 0 W / requested 0 A;
- actuator fail-closed target 0 A with `previousA = 0` and no physical write required;
- live Easee readback: paused, 0 W, target current 0 A.

This validates the recovered-state end condition without intentionally disrupting the Easee app or starting a charging session.

## Safety note

When Homey cannot communicate with the Easee charger, the EMS cannot guarantee that a 0 A command has physically reached the charger. The fail-safe therefore reports control as unavailable rather than claiming the charger has stopped. Once telemetry/control recovers, the normal EV gate and the existing single physical actuator reassert the current policy, including 0 A when charging is not permitted.

## Remaining architectural cleanup

`EM2_State.tesla.chargeState` is still the raw Core representation and may contain the last Easee value during an outage. Control consumers must use `EM2_EV_Telemetry_Health` as the authoritative availability guard. A later Core schema revision can embed the normalized device-health fields directly into the canonical State without changing the safety behavior implemented here.

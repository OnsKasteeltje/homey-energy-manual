# EV Device Health v0.2 — observability-only update

Date: 2026-09-12

## Purpose

`EM2_EV_Telemetry_Health` remains a diagnostic signal for Easee/Homey telemetry quality, but as of 2026-09-12 it is **not a hard control veto** in the EV Adapter Gate.

This document supersedes the earlier 2026-09-11 interpretation in which `CONTROL_UNAVAILABLE` from the health observer automatically blocked every positive EV command.

## Why the control rule changed

Live validation showed that the health observer can report `STALE / EASEE_TELEMETRY_STALE` when capability values have simply remained unchanged for more than five minutes, even though:

- the Easee device is still reachable through Homey;
- the charger is still controllable;
- the canonical intent, EV adapter and EM2 state are coherent;
- electrical and translation checks pass.

Therefore the health observer was conflating **unchanged capability timestamps** with **loss of control availability**. Using that signal as a hard gate produced false-positive control vetoes.

## 2026-10-04 v0.4 downstream observability extension

The production observer is promoted to `EM2_EV_DEVICE_HEALTH_V0.4` without
changing its safety role. It remains observability-only and does not participate
in Gate PASS/FAIL.

Compared with v0.3, one additional targeted read is made for the Homey
`Equalizer` device. The observer now records:

- Easee `target_charger_current` as requested current;
- Easee `measure_current.offered` as offered current;
- Easee `target_circuit_current`;
- Easee measured charging power and L1/L2/L3 currents;
- Equalizer measured power and L1/L2/L3 currents, availability and telemetry age;
- existing P1/grid current context.

This evidence exists specifically to distinguish **requested** current from
**offered** and **physically measured** current. A lower offered current than the
requested current proves the reduction happened downstream of the EMS/Homey
target. Presence of fresh Equalizer evidence makes Equalizer/load balancing a
supported explanation, but not unique causal proof by itself.

The EV Control Pi Push remains unchanged: it still performs Logic reads only.
Because the Device Health Logic value now contains the downstream snapshot, the
existing health-variable trigger transports it to the Pi. Pi ingest persists a
normalized `downstream_json` projection so changes in downstream current/load
are not removed by semantic deduplication.

## Current Homey runtime components

### `EM v2 | 82 Safety | EV Device Health v0.2 LIVE-GATE`

The existing health observer remains enabled for diagnostics. It:

- performs a targeted Easee device read;
- runs periodically and on state changes;
- performs no physical writes;
- publishes `EM2_EV_Telemetry_Health`;
- reports fields such as status, reason, normalized EV status, control availability and telemetry age;
- may still classify stable capability timestamps as `STALE`.

Its current flow name contains the historical term `LIVE-GATE`; that name no longer describes its control impact and should be treated as legacy naming until cleaned up.

### `EM v2 | 80 Validation | EV Power Adapter Gate v0.2.5 OBSERVABILITY-ONLY HEALTH`

This is the active EV gate.

The gate still reads `EM2_EV_Telemetry_Health`, but only to publish diagnostic context. Health fields are emitted under `deviceHealth` with `observabilityOnly = true`.

Health is **not** part of the decisive PASS/FAIL checks.

Gate PASS is based on the independent control contract, including:

- expected intent/adapter/state schemas;
- exact source/state revision alignment;
- valid canonical Power Intent;
- safe read-only adapter semantics;
- valid EV state semantics;
- electrical/current mapping checks;
- valid command range;
- fail-closed translation semantics.

A health state such as `STALE`, `UNAVAILABLE` or `CONTROL_UNAVAILABLE` by itself therefore cannot force the v0.2.5 gate to FAIL.

### `EM v2 | 81 Observability | EV Control Status v0.3 + HEALTH`

`docs/data/ev-control-status.json` publishes the health state next to Gate and Actuator evidence.

The top-level contract is explicit:

- `observabilityOnly = true`;
- `controlImpact = NONE`.

Some nested warning text can still reflect the older hard-veto wording. Such wording is diagnostic legacy text and is **not authoritative for control behavior**. The gate status and active v0.2.5 implementation are authoritative.

## Live validation — 2026-09-12

A controlled Pi end-to-end EV test was performed after changing the gate to observability-only health.

During the successful positive command:

- Pi target: 4830 W / 7 A;
- health observer still reported `STALE / EASEE_TELEMETRY_STALE`;
- gate: `PASS`;
- gate health block: `observabilityOnly = true`;
- actuator: `WRITE_OK_POST_SESSION`;
- `physicalWritePerformed = true`;
- Easee: `Charging`;
- offered/target current: 7 A;
- measured charging power: approximately 4.9 kW.

The later return to Pi target 0 A physically paused the charger again.

Result: **the hard health veto was the blocker; removing health from decisive gate checks restored the intended Pi → Homey → Easee control path while retaining the other safety checks.**

## Safety boundary

This change does not make Easee health irrelevant. It changes how the signal is used.

- Health remains useful for observability, troubleshooting and warning.
- The EV gate continues to fail closed on incoherent intent/adapter/state revisions, invalid schema, invalid electrical mapping or invalid translation semantics.
- The EV actuator remains the single physical Easee writer.
- Invalid/stale canonical control input still fails closed to 0 A.

The current capability-timestamp heuristic must not be treated as a control interlock.

Writer v0.4.5 adds a separate, stronger operational signal at the physical command boundary: a terminal Easee Cloud authentication failure after the bounded single refresh/retry path. This is not inferred from stale telemetry; it is an explicit command/auth acknowledgement failure. The actuator already fails closed on that condition. The new signal therefore drives **warning only**, not an additional Gate veto or second safety authority.

Alert policy:

- a first HTTP 401 that is successfully recovered by the existing one-refresh/one-retry path is silent;
- terminal refresh 400/401/403, missing/invalid private token state, primary phase 403, or 401/403 after refresh retry produces an auth alert;
- the same active failure is deduplicated; if both push and Timeline delivery fail, alert delivery is retried no more often than every 15 minutes;
- Owner push is preferred, with Homey Timeline fallback;
- notification failure never changes actuator safety behavior;
- no access token, refresh token, Homey user ID or other secret material is stored in the alert.

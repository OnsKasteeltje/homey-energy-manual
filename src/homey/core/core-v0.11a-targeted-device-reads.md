# Core v0.11a — Targeted Device Reads

Status: **DEPLOYED / ACTIVE BASELINE**

Date: 2026-08-29

Baseline: `EM v2 | 00 Core Tick | v0.10.18 (EV semantic producer)`.

## Runtime status

Deployed Homey flow: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

The full Core + Publisher + EV + WW chain has been re-enabled manually and observed under natural runtime load. Compared with the earlier EMS period with repeated 20–40% system-CPU peaks, v0.11a currently keeps the integrated workload materially lower. Recent observations were predominantly low single digits with short peaks around 11–17%; a later window reached roughly 13–14% without returning to the former 20–40% pattern. Read-only Homey probes have also succeeded again after earlier rate limiting.

This is the active comparison baseline for v0.11b. Do not alter v0.11a while the consolidated Logic-input design is being prepared.

## Purpose

Remove the remaining broad `Homey.devices.getDevices()` collection scan from Core while preserving the current 5-minute cadence, Core policy, state schema, Logic single-reader behavior, fan-out suppression and all downstream contracts.

This is deliberately a one-variable-at-a-time load experiment. `Homey.logic.getVariables()` remains unchanged in v0.11a. Logic targeting is a separate v0.11b step.

**v0.10.18 preservation gate:** the producer-only `EM2_Control_EV` semantic output introduced in v0.10.18 MUST remain equivalent in behavior. v0.11a changes only the device read layer.

## Current structural cost

The pre-v0.11a Core pattern was effectively:

```js
const [devices, vars] = await Promise.all([
  Homey.devices.getDevices(),
  Homey.logic.getVariables()
]);
```

Core already contains stable IDs for the devices it consumes. Therefore enumerating the complete Homey device collection every Core tick was unnecessary for normal operation.

At a 5-minute cadence the broad device scan executed up to **12 times/hour**.

## Known Core device inventory

The current Core source identifies these devices by stable ID:

| Role | Stable ID | Required Core data |
|---|---|---|
| P1 meter | `7a696d77-15fb-4b68-9bce-f1e39bff5045` | grid power, phase power/current, capability timestamps |
| Easee charger | `65ee9fda-9535-44ab-8037-809587bc8f1c` | EV power/current/voltage/state/meter |
| Easee Equalizer | `7dd35f8f-1dca-42f5-9b41-9b69bd14c611` | power and phase currents |
| Boiler | `8238b270-21a2-4284-aa78-6b9b58d254ab` | power and on/off |
| Quatt | `1e5dcde5-c1cf-4c32-9141-33e00ce36de9` | electrical/thermal/COP/mode/thermostat/CV state |
| SolarEdge | `c52c1c1d-9080-4a3b-b2e0-acc1eed7bf20` | production power + timestamp |
| GoodWe 4200 | `9f55af14-a080-4129-8887-c81b95f649bb` | production power + timestamp |
| GoodWe 2000 | `cbb98288-1c44-4718-9a66-13709b9d0172` | production power + timestamp |
| Washer | `921c9604-b06e-43df-b903-2294a971c525` | AEG direct appliance status fields used by Core |
| Dryer | `dfce2ff9-3d90-4721-9865-2a7bcc6d7100` | AEG direct appliance status fields used by Core |

No discovery-by-name is required for these devices.

## Deployed v0.11a read strategy

The collection read is replaced by targeted reads only for the known IDs Core actually consumes. The deployed implementation obtains the ten known devices directly and retains `Homey.logic.getVariables()` for Logic data.

The existing `capObj`, `cap`, `capTs` and laundry-state helpers remain unchanged.

## Important load caveat

v0.11a removes one **broad collection enumeration** per Core tick, but replaces it with targeted requests for the devices Core actually uses. This reduces broad response volume, object traversal and pressure on the collection path, but it does **not** automatically mean fewer API request operations.

Acceptance is therefore based on observed throttling/resource behavior, not on an assumption that targeted reads are always cheaper in every Homey implementation.

If Homey exposes a supported bulk-ID or cached/event-driven mechanism with lower request count, that is preferable for a later revision.

## Fail-closed behavior

A missing/stale safety-relevant target device must never silently become a valid zero.

Rules:

- preserve existing freshness/skew validation;
- if a targeted P1 read fails, Core must fail closed for flex decisions;
- if a PV source read fails, derived house balance remains invalid/degraded according to existing rules;
- if Easee/Equalizer data cannot be read, EV availability/measurement must not be upgraded to a valid state;
- no physical write is introduced by this change;
- do not add retries inside the same Core run after `429 Too many requests`.

## No-change contract

v0.11a MUST NOT change:

- Core cadence: stays every 5 minutes;
- `Homey.logic.getVariables()` behavior;
- state/decision schemas;
- v0.10.18 `EM2_Control_EV` semantic producer behavior;
- Power Intent semantics;
- EV/WW control ownership;
- Publisher cadence;
- Planner state;
- semantic-write suppression;
- physical device-write behavior;
- external HTTP/GitHub behavior.

## Observed effect

Steady-state broad device collection scans:

- before: **12/hour**;
- after v0.11a: **0/hour**.

Observed integrated runtime after deployment is materially lighter than the earlier problematic EMS configuration. This does not prove that CPU load alone caused Homey API throttling, but it establishes v0.11a as the preferred active baseline.

## Soak acceptance

The current v0.11a baseline has passed the initial runtime/load gate:

- no broad `getDevices()` collection call remains in Core;
- v0.10.18 `EM2_Control_EV` producer is preserved;
- full Core + Publisher + EV + WW chain runs with much lower CPU than the former 20–40% period;
- read-only probes can succeed without immediate `Too many requests`;
- no physical-write behavior was intentionally changed by the Core revision.

Continue to treat rate limiting separately from CPU: a future 429 is not automatically a v0.11a failure unless it correlates with the new targeted-read pattern.

## Rollback

Restore v0.10.18 unchanged. Do not combine rollback with any Planner, Publisher, Power Intent, Gate or actuator change.

## Next step

Design and validate **v0.11b** to remove the remaining broad `Homey.logic.getVariables()` scan using a consolidated canonical Logic input rather than dozens of per-variable reads. Event-driven Core (`v0.12`) remains a later step after both broad-read eliminations are proven.
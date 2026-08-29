# Core v0.11a — Targeted Device Reads

Status: **IMPLEMENTATION-READY / NOT DEPLOYED**

Date: 2026-08-29

Baseline: active `EM v2 | 00 Core Tick | v0.10.17 (Planner Input low-load)`.

## Purpose

Remove the remaining broad `Homey.devices.getDevices()` collection scan from Core while preserving the current 5-minute cadence, Core policy, state schema, Logic single-reader behavior, fan-out suppression and all downstream contracts.

This is deliberately a one-variable-at-a-time load experiment. `Homey.logic.getVariables()` remains unchanged in v0.11a. Logic targeting is a separate v0.11b step.

## Current structural cost

The current Core pattern is effectively:

```js
const [devices, vars] = await Promise.all([
  Homey.devices.getDevices(),
  Homey.logic.getVariables()
]);
```

Core already contains stable IDs for the devices it consumes. Therefore enumerating the complete Homey device collection every Core tick is unnecessary for normal operation.

At a 5-minute cadence this broad device scan executes up to **12 times/hour**.

## Known Core device inventory

The current Core source already identifies these devices by stable ID:

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

## v0.11a read strategy

Replace the collection read with targeted reads only for the known IDs Core actually consumes.

Preferred shape:

```js
const getDevice = async id => Homey.devices.getDevice({ id });

const [
  p1, ev, eq, boiler, quatt,
  se, gw42, gw20, washer, dryer,
  vars
] = await Promise.all([
  getDevice(IDS.p1),
  getDevice(IDS.ev),
  getDevice(IDS.eq),
  getDevice(IDS.boiler),
  getDevice(IDS.quatt),
  getDevice(IDS.se),
  getDevice(IDS.gw42),
  getDevice(IDS.gw20),
  getDevice(IDS.washer),
  getDevice(IDS.dryer),
  Homey.logic.getVariables()
]);
```

Then construct an in-memory map so the rest of the current Core code can remain as close to byte-for-byte equivalent as practical:

```js
const devices = {
  [IDS.p1]: p1,
  [IDS.ev]: ev,
  [IDS.eq]: eq,
  [IDS.boiler]: boiler,
  [IDS.quatt]: quatt,
  [IDS.se]: se,
  [IDS.gw42]: gw42,
  [IDS.gw20]: gw20,
  [IDS.washer]: washer,
  [IDS.dryer]: dryer
};
```

The existing `capObj`, `cap`, `capTs` and laundry-state helpers can then remain unchanged.

## Important load caveat

v0.11a removes one **broad collection enumeration** per Core tick, but replaces it with targeted requests for the devices Core actually uses. This is expected to reduce response volume, object traversal and pressure on the broad Homey API path, but it does **not** automatically mean fewer HTTP/API request operations.

Therefore acceptance is based on observed throttling/resource behavior, not on an assumption that targeted reads are always cheaper in every Homey implementation.

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

## Capability parity gate

Before deployment, compare the targeted response for each device against what current `getDevices()` exposes for every capability Core reads. PASS requires parity for both `.value` and `.lastUpdated` where freshness logic depends on the timestamp.

Required checks include at minimum:

- P1 `measure_power`, phase power/current and `lastUpdated`;
- SolarEdge/GoodWe production capability and `lastUpdated`;
- Easee current/voltage/power/charging-state/meter capabilities;
- Equalizer phase currents;
- boiler power/onoff;
- Quatt thermal/COP/mode/thermostat/CV capabilities;
- washer/dryer direct appliance status fields used by `laundryState()`.

If any targeted device response omits capability metadata used today, **do not deploy** v0.11a until the adapter pattern is corrected.

## No-change contract

v0.11a MUST NOT change:

- Core cadence: stays every 5 minutes;
- `Homey.logic.getVariables()` behavior;
- state/decision schemas;
- Power Intent semantics;
- EV/WW control ownership;
- Publisher cadence;
- Planner state;
- semantic-write suppression;
- physical device-write behavior;
- external HTTP/GitHub behavior.

## Expected effect

Steady-state broad device collection scans:

- before: **12/hour**;
- after v0.11a: **0/hour**.

This should reduce broad-read pressure and data volume. CPU improvement may be small because current Insights show low HomeyScript CPU outside short pulses; the primary success criterion is lower Homey API/throttling pressure.

## Deployment / smoke gate

Do not deploy during an active throttling incident.

1. exact-ID read the active Core flow;
2. confirm baseline is v0.10.17 and `broken=false`;
3. validate targeted capability parity without repeated discovery loops;
4. apply only the device-read delta;
5. run one controlled Core smoke;
6. verify `enabled=true`, `broken=false`;
7. compare `EM2_State`, `EM2_Decision`, `EM2_Control_WW`, `EM2_Planner_Input` semantics with pre-change baseline;
8. verify no physical write was caused;
9. stop immediately on `429` / `Too many requests`.

## Soak acceptance

Observe natural Core runs before moving to v0.11b. PASS requires:

- no broad `getDevices()` collection call in the deployed Core source;
- no semantic regression in Core output;
- no new stale/missing-device false positives caused by targeted response shape;
- no new downstream fan-out;
- no 429 attributable to the new targeted-read fan-out;
- ideally a longer clean interval between Homey throttling events than the pre-change baseline.

## Rollback

Restore v0.10.17 unchanged. Do not combine rollback with any Planner, Publisher, Power Intent, Gate or actuator change.

## Next step

Only after v0.11a passes: design **v0.11b** to remove the remaining broad `Homey.logic.getVariables()` scan using stable Logic IDs/canonical inputs. Event-driven Core (`v0.12`) remains a later step after both broad-read eliminations are proven.
# Core v0.10.16 — safe semantic fan-out correction

Baseline: live/Homey Core v0.10.15 and `src/homey/core/core-v0.10.15.js`.

## Scope

This release is a mechanical safety correction only. All EMS policy, Tesla, Equalizer, Quatt, Quooker, laundry, hot-water, post-goal, publication-due, balance and SHADOW behaviour remain unchanged.

## Exact changes

1. Version markers:
   - header `v0.10.15` -> `v0.10.16`
   - `PUB_VERSION='EM2_CORE_STATE_V0.10.15'` -> `PUB_VERSION='EM2_CORE_STATE_V0.10.16'`

2. Semantic Logic suppression set:

Before:
```js
const SEMANTIC_JSON_VARS=new Set(['EM2_State','EM2_Decision','EM2_Shadow','EM2_WW_State','EM2_Control_WW','EM2_Public_State','EM2_Publisher_Status']);
```

After:
```js
const SEMANTIC_JSON_VARS=new Set(['EM2_State','EM2_Decision','EM2_Shadow','EM2_Control_WW','EM2_Publisher_Status']);
```

`EM2_WW_State` is deliberately excluded because its cadence persistence (`updatedAt` / `deltaMin`) is part of the hot-water integrator state and must not be suppressed as timestamp-only noise.

`EM2_Public_State` is deliberately excluded because public heartbeat freshness must remain independently writable even when the semantic energy state does not change.

## Invariants

- exactly one `Homey.devices.getDevices()` per Core tick;
- exactly one `Homey.logic.getVariables()` per Core tick;
- no physical device writes;
- SHADOW/read-only control remains intact;
- `EM2_Publish_Due = revisionPending || heartbeatDue || upgradeDue` remains unchanged;
- `EM2_Control_WW` remains semantic-suppressed and is the late semantic trigger contract for Power Intent;
- no policy thresholds or actuator decisions are changed.

## Validation gate

Deploy only as the exact v0.10.15 runtime plus the changes above. After deployment run one controlled Core smoke, verify Publisher v1.0.7 publishes the matching revision to `docs/data/energy-state-v2.json`, and verify no Homey rate-limit error occurs before starting a sustained load baseline.

# Core v0.11h — Homey readback and rollback baseline

**Status: PREP ONLY / NOT DEPLOYED**

Read-only Homey baseline captured on 2026-09-02 before any Core change.

## Current Homey Core flow

- Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Name: `EM v2 | 00 Core Tick | v0.11g PINNED SOURCE`
- Type: Advanced Flow
- Enabled: `true`
- Broken: `false`
- Triggerable: `true`
- Schedule trigger: every 5 minutes
- Manual start card: present
- Script action card: `homey:app:com.athom.homeyscript:runCode_v2`
- Script header: `v0.11g CANDIDATE — Planner v0.5 WW compatibility + existing Tesla headroom`
- `PUB_VERSION`: `EM2_CORE_STATE_V0.11g`
- Core control mode in source: `SHADOW`
- Core source explicitly states: `NO physical writes here.`

The live script contains the v0.11g thermostat verification semantics under investigation: `THERMOSTAT_VERIFY_MAX_MIN=20`, an import-safe gate using the 4 kW discretionary ceiling, and no measured-low-power requirement in `thermostatVerifyBaseEligible`.

## Source provenance

Repository baseline used for candidate generation:

- Commit: `bd4edecc219c035399a18671429c2cf24eaea1be`
- Path: `src/homey/core/core-v0.11g.live-homey.js`
- Git blob: `0bdd1fd7228cddcd2c5331df1dbbcfcaa3aab715`

The Homey readback visibly matches the expected v0.11g identity, header, constants and affected WW logic. This capture is the rollback configuration baseline. Deployment tooling must not rely on a live fragment edit.

## Stale note discovered

The flow contains a green note saying `Core remains disabled until explicitly re-enabled`, while the actual flow property is `enabled=true`. Treat the flow property as authoritative. Do not use that note as runtime state evidence.

## Rollback procedure

If v0.11h is later deployed and rollback is required:

1. Do not alter downstream WW adapter or actuator flows.
2. Restore the Core script action as one complete unit from immutable v0.11g source `bd4edecc...:src/homey/core/core-v0.11g.live-homey.js`.
3. Restore the flow name to `EM v2 | 00 Core Tick | v0.11g PINNED SOURCE`.
4. Preserve the existing Advanced Flow structure: 5-minute cron trigger, manual start card, same script action card, flow enabled.
5. Read back the complete Advanced Flow after write and confirm `enabled=true`, `broken=false`, the v0.11g header and `PUB_VERSION='EM2_CORE_STATE_V0.11g'`.
6. Perform observation-only post-rollback validation; do not induce loads.

## Deployment gate remaining

No Homey write has occurred. Before deployment, the exact v0.11h full-source candidate must be committed/pinned as an immutable deployment artifact derived from validated candidate blob `c88647e08b85631cd27bb109b35a58a569445dea`. Deployment must replace the Core source as one reviewed unit and requires explicit approval.
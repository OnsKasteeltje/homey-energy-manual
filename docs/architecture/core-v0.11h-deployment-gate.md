# Core v0.11h deployment gate

**Status: PREPARED / NOT DEPLOYED**

Date: 2026-09-02

## Validated candidate identity

- Runtime baseline commit: `bd4edecc219c035399a18671429c2cf24eaea1be`
- Runtime baseline blob: `0bdd1fd7228cddcd2c5331df1dbbcfcaa3aab715`
- Candidate generator: `src/homey/core/tools/materialize-core-v0.11h.sh`
- Candidate Git blob from green CI: `c88647e08b85631cd27bb109b35a58a569445dea`
- Green GitHub Actions run: `33673543895`
- WW regression matrix: 10/10 PASS
- Downstream WW schema remains `EM2_CONTROL_WW_V0.11`

The candidate remains generated-only by design. Do not reconstruct or hand-edit the deployment source in Homey. Materialize it from the immutable v0.11g baseline using the reviewed generator and verify the resulting Git blob equals the candidate blob above before deployment.

## Live Homey pre-deploy readback

Read-only Homey inspection on 2026-09-02 confirmed:

- Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Name: `EM v2 | 00 Core Tick | v0.11g PINNED SOURCE`
- `enabled=true`
- `broken=false`
- schedule: every 5 minutes
- manual start card present
- one HomeyScript action card
- live source identifies `PUB_VERSION='EM2_CORE_STATE_V0.11g'`

The green note inside the flow says the Core remains disabled; that note is stale and must not be used as runtime evidence. The actual flow property is authoritative.

## Deployment sequence

No Core write is authorized merely by this document.

When explicit deployment approval is given:

1. User manually disables the existing Core flow in Homey.
2. Confirm by read-only Homey readback that the exact flow ID above has `enabled=false` before changing code.
3. Materialize the v0.11h source from the immutable baseline and verify candidate blob `c88647e08b85631cd27bb109b35a58a569445dea`.
4. Replace only the HomeyScript source in the existing Core flow. Preserve flow ID, folder, 5-minute trigger, manual trigger and graph topology.
5. Keep the Core disabled during immediate post-write readback.
6. Read the flow back and verify: expected v0.11h identity, low-power thermostat gate present, no unexpected card/topology changes, `broken=false`.
7. Only after readback PASS may the user manually re-enable the Core.
8. Observe the next natural Core ticks. Do not induce artificial boiler/Tesla/Quatt loads.

## First observational acceptance

After re-enable:

- Core ticks normally on its 5-minute cadence.
- Publisher/state freshness remains normal.
- `EM2_Control_WW` remains schema-compatible.
- High-power boiler after run-lock with no opportunity and import >500 W resolves to `BOILER_OFF / WAIT_IMPORT` rather than `THERMOSTAT_VERIFY`.
- `THERMOSTAT_VERIFY` may start only with measured boiler power <100 W after confirmed heating.
- If boiler power rises to >=100 W during verification, control resolves to `BOILER_OFF / THERMOSTAT_VERIFY_ABORT`.
- No regression is accepted in catch-up, 19:00 hard stop, mode-off, planner, Tesla or post-goal paths.

## Rollback trigger

Rollback immediately if the flow becomes broken, Core/state freshness stops, downstream WW schema changes, unexpected control behavior appears, or the readback differs from the reviewed candidate.

Rollback target is the complete immutable v0.11g source from commit `bd4edecc219c035399a18671429c2cf24eaea1be`, preserving the same flow ID and graph. Keep Core disabled while restoring and read back before re-enabling.

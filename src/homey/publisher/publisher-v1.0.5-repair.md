# Publisher v1.0.5 repair candidate

Purpose: restore website publication without the retired/missing `PBTH Export` flow.

## Invariants

- Flow ID remains `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd`.
- Publisher remains disabled during deployment and smoke preparation.
- Existing `EM v2 - Publish ShadowData` HomeyScript is retained unchanged.
- Existing 90-second delay is retained to minimize behavioral change.
- No device read/write or actuator path is added.

## Flow delta

Before:

`Start -> PBTH Export (missing flow) -> 90 s delay -> Publish ShadowData`

After:

`Start -> 90 s delay -> Publish ShadowData`

The obsolete programmatic-trigger card is removed. Start connects directly to the existing delay card. This is intentionally the smallest repair possible; it does not redesign the publication script or website schema.

## Proposed Homey name

`EM v2 | 40 Data | Publisher v1.0.5 (PBTH decoupled)`

## Smoke acceptance

1. Homey accepts the updated flow with `enabled=false` and `broken=false`.
2. Temporarily enable manually for the smoke only.
3. One start reaches `Publish ShadowData` after the retained 90-second delay.
4. `docs/data/energy-state-v2.json` receives a newer generated/source timestamp or revision.
5. No Homey `Too many requests` occurs during the smoke.
6. Watchdog is not enabled until publisher smoke passes.

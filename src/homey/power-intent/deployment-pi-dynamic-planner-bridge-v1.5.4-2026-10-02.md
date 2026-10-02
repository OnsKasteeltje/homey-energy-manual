# PI Dynamic Planner Bridge v1.5.4 — phase/current deployment

Date: 2026-10-02

Status: **DEPLOYED / LIVE — natural PV acceptance open**

## Runtime

Homey Advanced Flow:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.4 PHASE-CURRENT [READY]`

Stable Flow ID:

`8bf53fdb-76f4-47db-8ccb-773ac515f06e`

HomeyScript card ID:

`44444444-eeee-4444-8444-444444444444`

Canonical source:

`src/homey/power-intent/pi-dynamic-planner-bridge-v1.5.4.phase-current.js`

Policy revision:

`PI_DYNAMIC_PLANNER_BRIDGE_V1.5.4_PHASE_CURRENT`

## Change

v1.5.4 removes duplicate realtime current ownership from v1.5.3.

The live opportunity path now has one controller:

```text
P1 + actual EV load
        |
        v
slow phase selector
OFF / 1P / 3P
        |
        v
phase-aware A regulator
6..16 A
```

The phase selector owns physical mode only. The current regulator owns requested current only. Compatibility fields `realtime.candidateA/candidateW` mirror the single controller result and are not a second control loop.

Current-only changes do not request a physical phase transition. The existing EV writer remains the sole physical writer.

## Production settings

- trailing available-power signal: 120 s time-weighted;
- minimum rolling coverage: 90 s;
- OFF→1P: 1500 W;
- OFF/1P→3P: 4400 W;
- 3P→1P: below 3600 W while at least 1500 W remains;
- 1P→OFF: below 1100 W;
- upward/re-entry dwell: 300 s;
- 1P mapping: 230 W/A;
- 3P mapping: 690 W/A;
- current range: 6..16 A, additionally bounded by the Pi realtime envelope;
- import deadband: 250 W;
- up-regulation: +1 A after 45 s continuous headroom;
- downward A-regulation: immediate proportional correction;
- applied deadline force remains a separate 3P path and runs last.

Unknown/new OFF state does not synthesize a 300 s re-entry delay. The dwell applies only after a known physical mode transition.

## Pre-cutover validation

The final Pi validation run on branch head `473a517d5` passed:

- controller tests: 24/24;
- bridge v1.5.4 tests: 16/16;
- existing phase regressions: 19/19;
- combined final regression: 59/59;
- Architecture Gate: PASS;
- Security Scan: PASS;
- Adapter/Gate/Writer files unchanged by the bridge change.

The controlled dry-run against live v1.5.3 reported:

```text
live hash : 01e5224883d8b41f1011531097fbed7d53b1b35a6d6b9c9c400f778b522ac775
cand hash : 7f18e276854a267bbeae52995696a1fe66526f5d93723425e00ebea6fccbc22c
result    : DIFF
mode      : DRY-RUN
write     : BLOCKED
```

## Cutover

Immediately before cutover:

- `readyForCutover=true`;
- planner owner `PI`;
- executor `HOMEY`;
- realtime EV `allowed=true`;
- realtime mode `PV_OPPORTUNITY`;
- deadline `active=false`.

The controlled deployer created a fresh pre-deploy backup and performed an exact read-back verification.

Pre-deploy backup:

`/home/jeroen/ems/backups/homey-flows/8bf53fdb-76f4-47db-8ccb-773ac515f06e.20261002T200506Z.predeploy.json`

Verified live hash after deployment:

`7f18e276854a267bbeae52995696a1fe66526f5d93723425e00ebea6fccbc22c`

The live flow remained `enabled=true`, `broken=false`, with five cards.

## Post-cutover chain validation

The first v1.5.4 control revision was coherent through the full chain:

```text
Power Intent
  policyRevision = PI_DYNAMIC_PLANNER_BRIDGE_V1.5.4_PHASE_CURRENT
  valid/status   = true / OK
  EV             = OFF / 0 A / 0 W / IDLE
  controller     = EM2_EV_PHASE_CURRENT_CONTROLLER_V0.1

Adapter
  valid/status   = true / ZERO_INTENT
  command        = OFF / 0 A / 0 W

Gate
  finalStatus    = PASS
  errors         = []

Actuator
  status         = STABLE
  reason         = OFF_ZERO_A_HOLD
  stage          = STABLE
  physical write = false
```

Control revisions aligned across Power Intent, Adapter, Gate and Actuator.

No unexpected charging or physical phase transition occurred during cutover.

## Rollback

The pre-deploy backup above is the canonical immediate rollback source for v1.5.3. The controlled Homey deployer must be used for rollback so that read-back verification remains mandatory.

## Remaining acceptance gate

Do not manufacture phase transitions solely for acceptance.

Validate on a natural PV period:

1. OFF→1P after sustained surplus;
2. A regulation inside 1P without a phase transaction;
3. 1P→3P after sustained higher surplus and upward dwell;
4. A regulation inside 3P without a phase transaction;
5. sustained 3P→1P and 1P→OFF behavior during falling/broken-cloud PV;
6. no regression in deadline-force behavior.

Until that natural validation is complete, the software is LIVE but the dynamic-PV acceptance item remains open.

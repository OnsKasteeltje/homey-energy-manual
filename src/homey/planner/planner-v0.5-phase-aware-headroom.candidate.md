# Planner v0.5 — phase-aware scheduling candidate

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Baseline: Planner `EM2_ENERGY_PLAN_24H_V0.4.9` with Tesla/WW flex-load coordination.

Topology input: `docs/data/ems-phase-topology.json` (`EM2_PHASE_TOPOLOGY_V0.1`).

## Objective

Extend the Planner with **phase-aware scheduling/orchestration** for the 3×25 A main connection, while explicitly **not** duplicating Easee Equalizer realtime load balancing or hardware protection.

The Planner may use validated topology to avoid unnecessarily unfavourable overlap between known flexible loads. It must not become a realtime phase controller and must not directly curtail Tesla current based on instantaneous P1 phase currents.

## Architecture alignment

This candidate follows the existing project invariants:

- Energy Core / EMS owns resource policy and scheduling priorities.
- Actuator adapters translate upstream intent but do not invent independent EMS policy.
- Easee Equalizer and other hardware-safety remain higher in the safety hierarchy and may further limit actual charging.
- Realtime device protection is not reimplemented in Planner.
- Planner remains SHADOW/read-only and forecast-only.

## Validated topology available now

- Main connection: **3 phases, 25 A per phase**.
- Boiler: **single-phase on L2**, nominal ~1.95 kW, observed ~1.9–2.05 kW, ~8.5 A, confidence HIGH.
- Tesla/Easee: **3-phase load on L1+L2+L3** with balanced charging expected for the currently validated topology.
- No phase assignment is invented for unknown loads.

## Scope of v0.5 candidate

v0.5 models only **planning preference / collision avoidance** for known flexible loads.

For the first implementation:

1. Use the validated static topology: boiler=L2, Tesla=3P balanced.
2. Treat simultaneous Tesla + boiler as less desirable than an equivalent schedule without overlap, because L2 carries both loads.
3. Prefer relocation of WW-SHOULD or Tesla opportunity slots when an equivalent feasible time exists.
4. Never silently drop WW-MUST or Tesla deadline obligations.
5. Do not compute or command a reduced Tesla current as a Planner response to phase loading.
6. Do not claim that Planner protects the 3×25 A fuse in realtime.
7. Do not model Victron battery phase effects yet. DESS remains external/primary battery optimizer.

## Scheduling policy

Existing v0.4.9 priority remains the starting point:

- Tesla deadline/MUST can outrank WW-SHOULD.
- WW-MUST/catch-up cannot silently be dropped.
- WW-SHOULD may be relocated before 19:00.

v0.5 adds a **phase-overlap preference**:

1. Detect candidate slots where Tesla and boiler would overlap.
2. Mark those slots as `PHASE_OVERLAP_L2_PREFERRED_AVOID` when an equivalent non-overlapping alternative exists.
3. Resolve in this order:
   - relocate WW-SHOULD before 19:00 if possible;
   - otherwise relocate non-MUST Tesla opportunity charging if possible;
   - preserve mandatory obligations when no equivalent alternative exists;
   - expose unresolved mandatory overlap explicitly instead of pretending it was electrically eliminated.
4. Realtime Easee Equalizer and existing Core/Gates remain authoritative for actual execution and electrical protection.

## What v0.5 explicitly does NOT do

- No realtime P1 phase-current control loop.
- No Planner-generated Tesla current curtailment.
- No synthetic 22 A per-phase control ceiling.
- No replacement of Easee Equalizer load balancing.
- No actuator write changes.
- No new per-phase polling.
- No claim that an overlap is unsafe solely because boiler and Tesla share L2.

## L2-specific implication

Because the boiler adds ~8.5 A on L2 while Tesla adds approximately the same charging current to L1/L2/L3, L2 carries the largest **known flexible-load increment** during simultaneous operation.

That makes simultaneous Tesla + boiler a valid scheduling preference signal, but **not** by itself a realtime safety verdict. Unknown household load and Equalizer behaviour remain outside Planner's direct control.

## Planner output additions

At plan level:

```json
"phaseAwareScheduling": {
  "enabled": true,
  "model": "KNOWN_FLEX_TOPOLOGY_OVERLAP_AVOIDANCE_V0.1",
  "topologySchema": "EM2_PHASE_TOPOLOGY_V0.1",
  "boilerPhase": "L2",
  "boilerCurrentA": 8.5,
  "teslaTopology": "3P_BALANCED",
  "realtimeProtectionOwner": "EASEE_EQUALIZER_AND_EXISTING_GATES",
  "currentCurtailmentByPlanner": false,
  "futureHouseLoadPerPhase": "NOT_MODELED"
}
```

Per slot, where relevant:

```json
"phaseScheduling": {
  "knownFlexibleOverlap": true,
  "sharedPhase": "L2",
  "preference": "AVOID_IF_EQUIVALENT_ALTERNATIVE_EXISTS",
  "resolvedBy": "WW_RELOCATED"
}
```

For a mandatory overlap that remains:

```json
"phaseScheduling": {
  "knownFlexibleOverlap": true,
  "sharedPhase": "L2",
  "preference": "MANDATORY_OVERLAP_VISIBLE",
  "resolvedBy": null,
  "realtimeProtectionOwner": "EASEE_EQUALIZER_AND_EXISTING_GATES"
}
```

## Metadata wording

Do **not** replace `gridHeadroom: NOT_MODELED_PHASE_AWARE` with a claim of phase-aware headroom in this iteration.

v0.5 is phase-aware **scheduling**, not phase-aware realtime headroom control. A truthful companion field is:

`phaseScheduling: KNOWN_FLEX_TOPOLOGY_OVERLAP_AVOIDANCE_V0.1`

The existing `gridHeadroom: NOT_MODELED_PHASE_AWARE` remains correct until a separate forecast-grade headroom model exists.

## No-change contract

v0.5 must not change:

- Planner SHADOW/read-only status;
- physical-write behavior (`false`);
- 96 × 15-minute horizon;
- timeline geometry contract;
- WW 19:00 hard deadline;
- daily WW obligation accounting;
- v0.4.9 Tesla/WW priority semantics except intentional relocation of non-MUST equivalents;
- Core/Gate realtime safety ownership;
- EV Adapter W→A contract;
- Easee Equalizer realtime load-balancing ownership;
- DESS battery-optimizer ownership;
- Publisher cadence.

## Open validation before Homey deployment

Before implementing/deploying v0.5 in Homey:

1. Confirm Tesla remains 3-phase/balanced in the supported operating modes used by the EMS.
2. Confirm boiler ~8.5 A remains stable across multiple heating cycles.
3. Synthetic-test a Tesla + WW-SHOULD overlap and verify WW is relocated when an equivalent slot exists.
4. Synthetic-test Tesla opportunity + WW-SHOULD and verify one non-MUST load can move without energy-accounting loss.
5. Synthetic-test Tesla deadline/MUST + WW-MUST and verify both obligations remain visible when overlap cannot be avoided.
6. Confirm Planner output never claims to have enforced the 25 A fuse limit.
7. Confirm website rendering can show overlap/preference metadata without altering the shared 96-slot timeline geometry.

## Deployment gate

Do not modify Homey until:

- synthetic scheduling tests pass;
- the v0.4.9 → v0.5 diff shows only phase-aware scheduling/observability changes;
- no realtime phase-control or Equalizer-duplication code exists;
- the website can render the new phase-scheduling status without altering timeline geometry.

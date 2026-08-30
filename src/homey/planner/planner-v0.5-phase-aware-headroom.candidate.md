# Planner v0.5 — phase-aware 3×25 A headroom candidate

Status: **PREPARED IN GITHUB / NOT DEPLOYED TO HOMEY**

Baseline: Planner `EM2_ENERGY_PLAN_24H_V0.4.9` with Tesla/WW flex-load coordination.

Topology input: `docs/data/ems-phase-topology.json` (`EM2_PHASE_TOPOLOGY_V0.1`).

## Objective

Extend the Planner from energy/price/PV-only coordination to **phase-aware electrical headroom** for the 3×25 A main connection, without turning the Planner into a realtime actuator safety layer.

The Planner remains a scheduling/orchestration layer. Realtime Core/Gate protections remain authoritative.

## Validated topology available now

- Main connection: **3 phases, 25 A per phase**.
- Boiler: **single-phase on L2**, nominal ~1.95 kW, observed ~1.9–2.05 kW, ~8.5 A, confidence HIGH.
- Tesla/Easee: **3-phase load on L1+L2+L3** with per-phase current capabilities available in Homey.
- No phase assignment is invented for other flexible/house loads.

## Scope of v0.5 candidate

v0.5 SHOULD model phase headroom only where topology is known with sufficient confidence.

For the first implementation:

1. Use current P1 phase currents (`grid.l1A`, `grid.l2A`, `grid.l3A`) as the realtime baseline supplied through Planner input.
2. Model Tesla as a balanced 3-phase load: requested current `A` adds approximately `+A` to L1, L2 and L3.
3. Model boiler as `+8.5 A` on **L2 only** when a WW slot is selected.
4. Keep unknown household loads inside the measured P1 baseline; do not invent future per-phase decomposition for them.
5. Do not model Victron battery phase effects yet. DESS remains external/primary battery optimizer.

## Safety reserve

Do not schedule up to the raw 25 A fuse limit. Introduce a configurable Planner reserve:

```js
const PHASE_LIMIT_A = 25;
const PHASE_RESERVE_A = 3;
const PHASE_PLANNING_LIMIT_A = PHASE_LIMIT_A - PHASE_RESERVE_A; // 22 A
```

Rationale: leave room for short-duration/unmodelled household load and keep Planner decisions conservative. This is a planning reserve, not a substitute for realtime hardware protection or Easee Equalizer behavior.

The reserve MUST remain explicit in plan metadata and must not be presented as a verified optimal value until runtime observations justify it.

## Baseline phase current

For every Planner run, obtain a phase-current baseline from the Core state in Planner input:

```js
const phaseBaseA = {
  L1: Number(state?.grid?.l1A),
  L2: Number(state?.grid?.l2A),
  L3: Number(state?.grid?.l3A)
};
```

A phase-aware decision is usable only if all three are finite and P1 is fresh. Otherwise the Planner MUST fall back to v0.4.9 behavior and report phase-aware quality as unavailable/degraded; it must not fabricate headroom.

Because the 24 h Planner does not yet have a per-phase forecast of unknown house load, v0.5 uses the current measured baseline as a conservative planning anchor and reports that limitation explicitly.

## Slot electrical model

For a candidate slot, derive incremental flexible load currents:

### Boiler

```js
const boilerPhaseA = selectedWW ? {L1:0, L2:8.5, L3:0} : {L1:0, L2:0, L3:0};
```

### Tesla

For a proposed balanced 3-phase Tesla current `teslaA`:

```js
const teslaPhaseA = {L1:teslaA, L2:teslaA, L3:teslaA};
```

### Combined projected phase current

```js
const projectedPhaseA = {
  L1: phaseBaseA.L1 + teslaPhaseA.L1 + boilerPhaseA.L1,
  L2: phaseBaseA.L2 + teslaPhaseA.L2 + boilerPhaseA.L2,
  L3: phaseBaseA.L3 + teslaPhaseA.L3 + boilerPhaseA.L3
};
```

For planning safety, compare the **absolute import-side loading** conservatively. If signed P1 currents are used and export can be negative, normalize semantics before applying the limit; do not treat export on one phase as guaranteed capacity for a future flexible import unless the current baseline sign convention is verified.

## Headroom computation

```js
const phaseHeadroomA = {
  L1: PHASE_PLANNING_LIMIT_A - projectedBaseA.L1,
  L2: PHASE_PLANNING_LIMIT_A - projectedBaseA.L2,
  L3: PHASE_PLANNING_LIMIT_A - projectedBaseA.L3
};
const limitingPhase = Object.entries(phaseHeadroomA)
  .sort((a,b)=>a[1]-b[1])[0][0];
const minHeadroomA = Math.min(...Object.values(phaseHeadroomA));
```

For Tesla current selection, the maximum phase-aware current is the minimum remaining headroom across all three phases after any selected boiler load is applied:

```js
const teslaMaxPhaseAwareA = Math.max(0, Math.floor(Math.min(
  PHASE_PLANNING_LIMIT_A - projectedBaseA.L1,
  PHASE_PLANNING_LIMIT_A - projectedBaseA.L2,
  PHASE_PLANNING_LIMIT_A - projectedBaseA.L3
)));
```

Clamp this further by existing EV min/max electrical limits. Do not change the EV Power Adapter contract in this Planner iteration.

## Coordination policy

Existing v0.4.9 priority remains the starting point:

- Tesla deadline/MUST can outrank WW-SHOULD.
- WW-MUST/catch-up cannot silently be dropped.
- WW-SHOULD may be relocated before 19:00.

v0.5 adds an electrical feasibility filter:

1. For each candidate WW/Tesla combination, compute projected phase loading.
2. If all phases remain within `PHASE_PLANNING_LIMIT_A`, keep the candidate.
3. If not, try in this order:
   - reduce Tesla current if the slot is still useful and above the EV minimum current;
   - relocate WW-SHOULD to another eligible slot before 19:00;
   - relocate non-MUST Tesla opportunity charging;
   - preserve WW-MUST / Tesla deadline obligations and mark any remaining conflict explicitly as `PHASE_HEADROOM_UNRESOLVED_MUST_CONFLICT` rather than pretending it is feasible.
4. Realtime Core/Gates retain final authority and may still block execution.

## L2-specific implication

Because the boiler adds ~8.5 A on L2 while Tesla adds approximately the same requested current to all three phases, **L2 is expected to be the limiting phase whenever boiler and Tesla overlap**, unless the measured baseline on another phase is already higher.

This is now a measured topology fact, not an assumption.

## Planner output additions

At plan level:

```json
"phaseAwareHeadroom": {
  "enabled": true,
  "model": "P1_CURRENT_BASELINE_PLUS_KNOWN_FLEX_TOPOLOGY_V0.1",
  "mainFuseA": 25,
  "planningReserveA": 3,
  "planningLimitA": 22,
  "topologySchema": "EM2_PHASE_TOPOLOGY_V0.1",
  "boilerPhase": "L2",
  "boilerCurrentA": 8.5,
  "teslaTopology": "3P_BALANCED",
  "unknownHouseLoadForecast": "NOT_MODELED_PER_PHASE",
  "batteryPhaseEffects": "NOT_MODELED"
}
```

Per slot add, when phase data is usable:

```json
"phaseHeadroom": {
  "quality": "CURRENT_BASELINE_ONLY",
  "baseA": {"L1": 0, "L2": 0, "L3": 0},
  "projectedA": {"L1": 0, "L2": 0, "L3": 0},
  "headroomA": {"L1": 0, "L2": 0, "L3": 0},
  "limitingPhase": "L2",
  "minHeadroomA": 0,
  "teslaMaxPhaseAwareA": 0,
  "feasible": true
}
```

If unavailable:

```json
"phaseHeadroom": {
  "quality": "UNAVAILABLE_P1_PHASE_CURRENT",
  "feasible": null
}
```

## Required metadata correction

Replace the current Planner statement:

`gridHeadroom: NOT_MODELED_PHASE_AWARE`

with a truthful quality string only after implementation, e.g.:

`gridHeadroom: PHASE_AWARE_CURRENT_BASELINE_V0.1`

Do not claim forecast-grade per-phase headroom because unknown future household phase load is not yet forecast.

## No-change contract

v0.5 must not change:

- Planner SHADOW/read-only status;
- physical-write behavior (`false`);
- 96 × 15-minute horizon;
- timeline geometry contract;
- WW 19:00 hard deadline;
- daily WW obligation accounting;
- v0.4.9 Tesla/WW priority semantics except where electrical feasibility forces relocation/current reduction;
- Core/Gate realtime safety ownership;
- EV Adapter W→A contract;
- DESS battery-optimizer ownership;
- Publisher cadence.

## Open validation before Homey deployment

Before implementing/deploying v0.5 in Homey, verify:

1. P1 current sign convention for L1/L2/L3 under import and export.
2. Tesla balanced 3-phase current behavior at several requested currents, preferably 6 A and 10 A.
3. Whether the Planner should use 3 A reserve or another value; 3 A is the initial conservative candidate only.
4. Confirm that boiler ~8.5 A remains stable across multiple heating cycles.
5. Smoke-test a synthetic overlap where L2 becomes limiting and WW-SHOULD is relocated rather than violating the phase limit.
6. Smoke-test Tesla deadline/MUST + WW-MUST conflict and verify the Planner reports an unresolved electrical conflict rather than hiding it.

## Deployment gate

Do not modify Homey until:

- the phase-current sign convention is verified;
- synthetic tests pass;
- the v0.4.9 → v0.5 diff shows only phase-aware planning/observability changes;
- the website can render the new phase-headroom status without altering the shared 96-slot timeline geometry.

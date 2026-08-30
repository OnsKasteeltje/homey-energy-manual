# Smoke plan — Planner v0.5 phase-aware headroom

Status: **GITHUB PREP / NO HOMEY CHANGE**

## Goal

Validate that phase-aware planning improves electrical feasibility without changing Planner ownership, WW obligations, Tesla deadline semantics, or the shared 96-slot horizon.

## Preconditions

- Topology file `docs/data/ems-phase-topology.json` available and schema-compatible.
- Boiler validated on L2 at ~8.5 A.
- Tesla treated as balanced 3-phase only after runtime verification.
- P1 L1/L2/L3 current sign convention verified.
- Planner remains SHADOW/read-only.

## Acceptance scenarios

| Scenario | Input condition | Expected result |
|---|---|---|
| P1 phase data missing/stale | one or more phase currents unavailable | fallback to v0.4.9 behavior; phaseHeadroom quality unavailable; no invented values |
| Boiler only | WW slot selected | projected L2 rises by ~8.5 A; L1/L3 unchanged by boiler model |
| Tesla only | Tesla current A | projected L1/L2/L3 each rise by A |
| Tesla + boiler | simultaneous slot | L2 includes Tesla A + boiler 8.5 A; limiting phase computed from all three phases |
| L2 limit, WW-SHOULD | overlap exceeds planning limit | relocate WW-SHOULD before 19:00 if alternative exists |
| L2 limit, Tesla opportunity | overlap exceeds planning limit | reduce/relocate non-MUST Tesla before violating phase limit |
| Tesla deadline + WW-SHOULD | phase conflict | preserve Tesla deadline priority and relocate WW-SHOULD when possible |
| Tesla MUST + WW MUST | no feasible combination | keep obligations visible and mark `PHASE_HEADROOM_UNRESOLVED_MUST_CONFLICT`; never silently drop either |
| Reserve boundary | projected current exactly 22 A with 3 A reserve | feasible |
| Reserve exceeded | projected current >22 A | infeasible for discretionary scheduling |
| Website output | plan contains phase fields | display status/details without changing 96-slot geometry |

## Regression checks

- 96 slots remain present.
- Tesla/WW action slot boundaries unchanged unless v0.5 intentionally relocates for electrical feasibility.
- Existing `flexLoadCoordination` counters remain meaningful.
- WW allocated kWh is preserved after relocation.
- `unallocatedKWh` is not hidden or falsified.
- Planner stays `physicalWritePerformed=false`.
- Core/Gate remain final realtime safety owners.
- Battery planning does not become a competing DESS optimizer.

## Evidence required for PASS

A v0.5 smoke is PASS only when the published Planner snapshot shows:

1. explicit phase model metadata;
2. per-slot projected/headroom values for usable phase inputs;
3. at least one deterministic synthetic case where L2 is limiting because of the boiler;
4. correct relocation/current reduction behavior;
5. no regression in v0.4.9 WW/Tesla obligation accounting;
6. no claim of full future per-phase forecast quality.

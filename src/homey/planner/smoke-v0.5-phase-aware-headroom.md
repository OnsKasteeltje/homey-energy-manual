# Smoke plan — Planner v0.5 phase-aware scheduling

Status: **GITHUB PREP / NO HOMEY CHANGE**

## Goal

Validate that phase-aware scheduling reduces unnecessary overlap between known flexible loads without duplicating Easee Equalizer realtime load balancing, changing Planner ownership, or altering WW/Tesla obligations.

## Preconditions

- Topology file `docs/data/ems-phase-topology.json` available and schema-compatible.
- Boiler validated on L2 at ~8.5 A.
- Tesla treated as balanced 3-phase only after runtime verification.
- Planner remains SHADOW/read-only.
- Easee Equalizer remains the realtime load-balancing / hardware-protection owner.

## Acceptance scenarios

| Scenario | Input condition | Expected result |
|---|---|---|
| Topology unavailable | boiler/Tesla topology missing or not validated | fallback to v0.4.9 scheduling; no invented phase preference |
| Boiler only | WW slot selected, no Tesla | no special phase conflict; normal v0.4.9 behavior |
| Tesla only | Tesla slot selected, no boiler | no special phase conflict; normal v0.4.9 behavior |
| Tesla + boiler overlap | both selected same slot | mark known flexible overlap on L2 |
| L2 overlap, WW-SHOULD | equivalent WW slot exists before 19:00 | relocate WW-SHOULD; preserve allocated WW energy |
| L2 overlap, Tesla opportunity | equivalent Tesla opportunity slot exists | relocate non-MUST Tesla opportunity rather than current-curtailing it |
| Tesla deadline + WW-SHOULD | overlap exists | preserve Tesla deadline priority and relocate WW-SHOULD when possible |
| Tesla MUST + WW MUST | no equivalent non-overlap slot | keep both obligations visible; mark mandatory overlap; do not claim fuse protection |
| No equivalent alternative | overlap unavoidable but not proven unsafe | keep schedule and expose preference/conflict metadata; actual protection remains Equalizer/Core/Gates |
| Website output | plan contains phase-scheduling fields | display status/details without changing 96-slot geometry |

## Explicit negative tests

The v0.5 implementation FAILS if any of these occur:

- Planner reduces Tesla current because of instantaneous P1 phase current.
- Planner introduces a synthetic 22 A per-phase control ceiling.
- Planner claims to protect the 3×25 A main fuse in realtime.
- Planner duplicates Easee Equalizer load balancing.
- New per-phase polling is added solely for realtime Planner control.
- A MUST obligation is silently dropped to remove overlap.

## Regression checks

- 96 slots remain present.
- Tesla/WW action slot boundaries change only when v0.5 intentionally relocates a non-MUST equivalent.
- Existing `flexLoadCoordination` counters remain meaningful.
- WW allocated kWh is preserved after relocation.
- `unallocatedKWh` is not hidden or falsified.
- Planner stays `physicalWritePerformed=false`.
- Core/Gate remain final EMS runtime safety owners.
- Easee Equalizer remains realtime EV load-balancing / hardware protection owner.
- Battery planning does not become a competing DESS optimizer.
- `gridHeadroom` remains `NOT_MODELED_PHASE_AWARE` in this iteration.

## Evidence required for PASS

A v0.5 smoke is PASS only when the published Planner snapshot shows:

1. explicit phase-scheduling metadata based on known topology;
2. at least one deterministic synthetic case where Tesla+boiler overlap on L2 is identified;
3. WW-SHOULD relocation when an equivalent non-overlap slot exists;
4. no Tesla current-curtailment logic in Planner;
5. mandatory overlap preserved and made visible when no equivalent alternative exists;
6. no regression in v0.4.9 WW/Tesla obligation accounting;
7. no claim of realtime phase-headroom protection or Equalizer replacement.

# Planner v0.5.0 SHADOW deployment — 2026-08-31

Status: **DEPLOYED TO EXISTING HOMEY PLANNER FLOW — SHADOW ONLY**

Flow: `EM v2 | 45 Planner | 24h Energy Plan v0.5.0 SHADOW LOW-LOAD`
Flow ID: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`
Previous runtime: `v0.4.9 SHADOW LOW-LOAD`

## Deployment method

A single targeted update of the existing Advanced Flow was performed. No flow enumeration, device read, flow start, capability write or additional Homey validation probe was performed as part of the deployment step.

The trigger topology was preserved exactly:

- every 15 minutes;
- 45-second delay;
- manual start card retained;
- one HomeyScript action;
- flow remains enabled.

The update response reports the flow as `broken: false`.

## Runtime change

Only the Planner HomeyScript and displayed version/note were changed. v0.5.0 adds:

- WW remaining-energy budget;
- marginal-grid-import ranking;
- non-contiguous PV-first WW slots;
- receding-horizon deferral of optional grid fallback;
- two-slot / 30-minute deadline safety reserve;
- minimal fallback when 19:00 feasibility becomes tight;
- explicit per-slot `targets.wwTargetW` SHADOW output;
- partial last-slot energy accounting in Planner observability.

Tesla, battery scenario, forecast method, price input contract, Planner cadence and physical control ownership remain unchanged.

## Homey-load contract

The candidate retains exactly one targeted Planner-input Logic read and one Planner-snapshot Logic write per scheduled run. It adds no device reads, broad Logic enumeration, new triggers or physical writes.

## Safety

- `controlMode = SHADOW`
- `physicalWritePerformed = false`
- no boiler writes
- no Easee writes
- no Victron writes
- existing physical writers unchanged
- phase-aware headroom is still explicitly not claimed

## Validation gate

No manual execution was triggered after deployment in order to avoid unnecessary Homey load. Validation should use the next naturally scheduled Planner publication and GitHub publication path. Compare the first v0.5.0 snapshot with the preceding v0.4.9 snapshot and confirm version, WW allocation policy, `wwDeferredGridEnergyKWh`, deadline-safety fields and `targets.wwTargetW` while preserving all SHADOW/no-write invariants.

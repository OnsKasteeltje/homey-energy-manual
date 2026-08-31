# Contract Price Adapter — PBTH Event Refresh Preparation

Status: **DO NOT DEPLOY / FROZEN PREPARATION ONLY**

> **DEPLOYMENT BLOCKED BY PROJECT DECISION (2026-08-31).**
> Do not provision state, do not patch Homey, and do not enable an event-refresh branch from this material unless the PBTH investigation first demonstrates a real timing gap that the existing 15-minute v0.10 refresh cannot adequately cover and a new explicit deployment decision is made.

## Why frozen

The current evidence does not establish that Homey needs an additional PBTH event-refresh path. The live v0.10 adapter already refreshes `prices_json(next_hours)` every 15 minutes. During the controlled 2026-08-31 probe, a fresh adapter -> Planner -> Publisher run still returned a shrinking current-day price horizon, while PBTH next-day fields were null. That points to PBTH/upstream availability rather than a stale website/publisher path.

Therefore this work is retained only as prepared contingency design. **Prepared does not mean approved or deployable.**

## Explicit prohibitions

Until this freeze is lifted by a new evidence-based project decision:

- DO NOT run `contract-price-event-refresh-v0.11-provision-state.homeyscript.js`;
- DO NOT create `EM2_ContractPrice_EventRefresh_State`;
- DO NOT read the production Advanced Flow for the purpose of this patch;
- DO NOT run/apply `build-contract-price-event-refresh-v0.11-patch.mjs` against Homey;
- DO NOT add or enable PBTH `new_prices` event nodes;
- DO NOT alter the existing 15-minute v0.10 fallback for this purpose;
- DO NOT treat any file in this preparation set as a deployment instruction.

## Current live baseline — unchanged

- Flow: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Schedule: every 15 minutes + manual start
- DYNAMIC action: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`, `period=next_hours`
- Canonical DYNAMIC context includes validated `priceSeries: prices`
- No event-refresh branch is approved for deployment.

## Retained contingency artefacts

The following are retained for possible future reconsideration, but are **NOT DEPLOYABLE** under the current project decision:

```text
contract-price-event-refresh-v0.11-provision-state.homeyscript.js
contract-price-event-refresh-v0.11-eligibility.homeyscript.js
contract-price-event-refresh-v0.11-post-fetch.homeyscript.js
build-contract-price-event-refresh-v0.11-patch.mjs
```

PBTH upstream source established `new_prices` with `period=next_hours`; this is retained as technical reference only.

## Conditions required before reconsideration

This freeze may only be reconsidered after evidence establishes all of the following:

1. PBTH has actually received/holds materially newer future prices;
2. the existing v0.10 15-minute refresh demonstrably fails to make those prices available to the canonical context/Planner within an acceptable interval;
3. the failure is not primarily PBTH/provider publication timing;
4. an event-driven refresh provides material benefit over the existing low-load schedule;
5. Homey load/rate-limit risk is acceptable;
6. a new explicit decision authorizes deployment.

If these conditions are not met, the event-refresh preparation should remain frozen or be removed as unnecessary complexity.

## If freeze is ever lifted

Only then may the previously prepared low-load design be reconsidered: DYNAMIC + horizon <12h + cooldown gate, maximum one PBTH call per admitted event, semantic comparison using `priceSeries`, no canonical republish on unchanged/degraded results, and the existing 15-minute route retained as fallback.

That topology is documentation of a contingency, **not a current implementation plan**.

## Project rule

For this and future HEMS changes: prepare and validate as much as possible outside Homey. A Homey call must be necessary for runtime-only information or the final authorized mutation; use the lightest available call and avoid broad enumeration/full-flow reads unless mutation safety strictly requires them.

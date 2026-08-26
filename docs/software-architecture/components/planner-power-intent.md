---
component: planner-power-intent
title: 24h Energy Planner and Power Intent
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-26
sources:
  - Homey Advanced Flow: EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | Actuator Commands v0.2 SHADOW
---

# 24h Energy Planner and Power Intent

## Purpose

This layer translates current EMS state and contract context into two distinct outputs: a 24-hour SHADOW plan for Tesla, hot water and a future Victron battery, and revision-aligned Power Intent that projects current Core policy into actuator-neutral targets such as `EV_target_W`. The layer is advisory/translation-only and performs no physical writes.

## Architecture boundary

`Core / Contract Context -> 24h Planner (advice)`

`Core Decision + WW Control + Public State -> Power Intent -> device-specific adapters -> future physical writers`

The Planner is not a runtime actuator controller. Power Intent is not the policy owner; it projects existing Core decisions into neutral numeric or binary targets.

## 24h Energy Planner v0.2 SHADOW

The planner runs every 15 minutes with a 45-second delay and can also be started manually. Its current fixed SHADOW battery scenario is Victron MultiPlus-II 48/5000/70-50 with 3 × Pylontech US5000, 14.4 kWh nominal capacity, assumed 20–90% SOC band, 3.3 kW AC charge/discharge limit, 95% charge and discharge efficiency, 90.25% round-trip efficiency and a 10.08 kWh usable simulation window. These are simulation assumptions, not commissioning values.

For Tesla, the planner does not invent charging power or throughput. With an active deadline it uses the existing deadline/latest-start as a hard planning window and ranks price slots inside that window. For hot water it uses the modeled approximately 1.9 kW boiler load and allocates remaining fallback energy over inexpensive 15-minute slots before 19:00. Battery planning remains theoretical and calculates charge/discharge candidates and economic pairs from price spreads and assumed efficiency. `theoreticalUpperBoundEuro` must never be presented as realized savings while actual SOC, detailed base load and true 15-minute PV forecast remain unavailable.

## Power Intent v0.2 SHADOW

Power Intent is triggered by changes to `EM2_Public_State` and is idempotent per source revision. Public State, Core State, Decision and WW Control revisions must align. On mismatch the output is invalid with `REVISION_MISMATCH` and the EV target fails closed to 0 W.

For `TESLA_CHARGE_DEADLINE`, `target_W = remaining_kWh / hours_to_deadline * 1000` when both remaining energy and a valid future deadline exist. For export opportunity with at least 800 W flex budget, the target equals `flexExportBudget_W`; where no export budget is available but price is negative/cheap, it uses `discretionaryImportBudget_W`. Otherwise the target is 0 W. Power Intent deliberately does not convert watts to amperes; electrical clamping belongs in the device adapter.

Hot water is still projected as binary intent (`BOILER_ON`, `BOILER_OFF`, `HOLD`); numeric `WW_target_W` is not yet produced.

## EV Power Adapter v0.1 SHADOW

The live SHADOW adapter accepts `EM2_POWER_INTENT_V0.2`, reads no devices directly and performs no physical Easee write. The electrical topology is fixed to three phases, 230 V per phase, 6 A minimum executable current and a configured safe maximum hard-limited to 16 A, with no automatic 1↔3 phase switching.

`theoretical_A = EV_target_W / (3 × 230)` and `requested_A = floor(theoretical_A)`. The result is clamped to the safe maximum; values below 6 A become 0 A. The adapter never rounds upward to minimum charging power and therefore cannot exceed the upstream power budget. It validates revision/schema alignment, freshness, numeric targets/current constraints and charger availability, failing closed to 0 A on stale or untrusted control input.

The output keeps `requested_A`, `commanded_A` and `confirmed_A` distinct. In SHADOW, `commanded_A` remains null. A future LIVE cut-over may only use Easee dynamic/volatile current control; persistent charger settings with flash-wear risk are not permitted as an EMS runtime writer.

## Generic Actuator Commands v0.2 SHADOW

The generic adapter accepts both transition schemas `EM2_POWER_INTENT_V0.1` and `V0.2`, emits `EM2_ACTUATOR_COMMANDS_V0.2`, records `inputSchema` and deduplicates on source revision plus input schema. EV W→A conversion is delegated to the EV Power Adapter; hot water remains binary and battery remains SHADOW/NOT_INTEGRATED.

## Single-writer and safety boundary

Core owns policy/arbitration; Power Intent owns neutral intent; adapters own deterministic translation, feasibility, quantization/clamping and freshness/capability guards; writer lifecycle owns commanded/confirmed tracking, idempotency, dedupe, run lease, retries and write throttling. Only one explicit physical writer may be active per actuator, and activation requires controlled atomic cut-over from the existing production writer.

SHADOW performs no device writes or adapter network calls, adapters contain no policy arbitration, revision alignment precedes numeric targets, invalid/stale control input fails closed, adapters never increase upstream power budgets, and frequent Easee control must use dynamic/volatile runtime control.

## Current status

| Item | Status |
|---|---|
| 24h Planner v0.2 | ACTIVE SHADOW |
| Power Intent v0.2 | ACTIVE SHADOW |
| EV Power Adapter v0.1 | ACTIVE SHADOW, hardened 3×230V/floor/fail-closed |
| Actuator Commands v0.2 | ACTIVE SHADOW, Power Intent v0.1/v0.2 compatible |
| EV physical writer via new adapter chain | NOT ACTIVE |
| Victron physical writer | NOT ACTIVE |
| WW physical writer via new adapter chain | NOT ACTIVE |

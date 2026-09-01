# Raspberry Pi EMS migration preparation

Status: **PREPARED / NOT DEPLOYED / NO PHYSICAL WRITES**  
Last sync: 2026-09-01  
GitHub sync anchor observed during preparation: `ef50e0d4981380f65f1c82bc9a4a5106a151fbde`

## Purpose

This directory is the migration boundary for moving suitable HEMS runtime responsibilities from Homey to the Raspberry Pi 5 without changing the current physical-control ownership prematurely.

The migration is code-first: the current GitHub sources under `src/homey/` remain authoritative for logic and schemas until a component has been explicitly ported, replay-tested, shadow-validated and cut over. The Pi must not reimplement a second independent planner, price model or actuator policy.

## Current architecture to preserve

The Pi migration must preserve these invariants:

- P1 remains authoritative for net import/export.
- One consistent state/revision is used downstream.
- Planner and price/context logic remain deterministic and replayable.
- Exactly one automatic writer may own each physical actuator.
- Easee Equalizer remains the independent hard EV load-balancing layer.
- Quatt remains `OBSERVE_ONLY` unless a separately validated control policy is introduced.
- Victron Dynamic ESS remains the primary future battery optimizer; the HEMS orchestrates household flexibility and must not become a competing realtime battery optimizer.
- New Pi control starts read-only/shadow. Physical ownership is transferred only by an explicit atomic cutover with rollback.

## Runtime baseline versus newer GitHub preparation

The last Homey ↔ GitHub runtime reconciliation remains `src/homey/runtime-sync-baseline-2026-08-30.md`. It records the active critical Homey runtime, including Core v0.11a, Power Intent v0.2.4, Planner v0.4.7, WW and EV adapter/gate/actuator chains.

Since that reconciliation, GitHub has gained important **shadow/read-only** price-source work that the Pi preparation must include from day one:

- `src/homey/context/price-source-normalizer-v0.1.mjs`
- `src/homey/context/price-source-selector-v0.1.mjs`
- `src/homey/context/price-source-e2e-shadow-v0.1.mjs`
- `docs/snippets/pbth-energyzero-selector-shadow-v0.1.js`
- `docs/snippets/pbth-energyzero-evening-validation-v0.1.js`

The selector is deliberately deterministic and contains no Homey calls, writes or network access. The E2E runner is explicitly Node/Pi-compatible and combines captured PBTH data with live EnergyZero REST data. This makes the price-source chain a strong first native-Pi candidate while it remains `SHADOW_READ_ONLY`.

The live A/B validation on 2026-09-01 established an exact semantic match for 109/109 overlapping PBTH and EnergyZero NL DAP15 slots. That validates the current PBTH `importPrice` mapping against EnergyZero `MARKET_EX_VAT` for that run, but it does **not** authorize production source switching. Horizon/readiness behaviour must still be validated, including the prepared evening probe.

## Migration sequence

### Phase P0 — repository sync and replay boundary — CURRENT

Run all work outside the physical control loop. Reuse current GitHub source files, schemas and captured fixtures. No Pi-to-device writes and no disabling of Homey flows.

Required outcomes:

1. A Pi runtime can consume recorded/captured state without Homey broad polling.
2. Deterministic modules run under Node on ARM64 unchanged or with a thin environment adapter only.
3. Outputs can be compared against the current Homey/GitHub shadow publications by schema, revision, timestamps and decision reason.
4. Price-source normalizer/selector/E2E logic is executable on the Pi in shadow mode.

### Phase P1 — Pi shadow services

Move compute-heavy/read-only responsibilities first:

- price-source acquisition/normalization/selection;
- 24h Planner replay/shadow calculation;
- evidence/history processing;
- diagnostics and validation.

Homey remains authoritative for live inputs that have not yet received a dedicated event/bridge interface. The Pi must consume compact state/events rather than reproduce `getDevices()` / `getVariables()` collection polling.

### Phase P2 — Power Intent shadow parity

Run Pi-produced Planner output and Power Intent beside the Homey chain. Require agreement on schema, intended watts, MUST/SHOULD/MAY priority, reason codes, freshness and revision provenance. Differences are evidence to investigate, not a reason to silently prefer one side.

### Phase P3 — adapter ownership transfer, one actuator at a time

Only after shadow parity and a targeted smoke test may ownership move. Transfer must be atomic:

1. establish Pi writer with physical writes disabled;
2. verify end-to-end command, guard and rollback path;
3. disable the old automatic writer;
4. enable exactly one new writer;
5. smoke-test and record PASS/FAIL;
6. rollback immediately on failure.

Do not migrate WW and EV writers in the same cutover batch.

### Phase P4 — Victron integration

After Victron hardware commissioning, expose measurement/status to the HEMS and hand battery optimization to Victron/DESS. Planner may publish household-flex forecasts/reservations such as future load requirements, but must not duplicate DESS arbitrage.

## Current component disposition

See `src/pi/runtime-migration-manifest-v0.1.json` for the machine-readable migration inventory. The key rule is that `native_pi_shadow_candidate` does not mean `production_on_pi`.

Current recommended first executable chain on the Pi:

`EnergyZero REST / captured PBTH -> price normalizer -> shadow selector -> Planner shadow input -> Planner replay -> comparison/evidence`

This path has no actuator dependency and therefore gives useful Pi validation without increasing Homey throttling risk.

## Runtime packaging decision intentionally still open

No prior project decision establishes Docker versus native Node/systemd as the canonical Pi packaging model. This sync therefore does **not** invent one. The runtime modules are prepared to remain ordinary Node-compatible source; packaging should be decided once the Pi is available and after checking operational needs such as restart behaviour, logs, secrets, updates and resource overhead.

Until that decision is made, do not add a production service that automatically starts physical writers at boot.

## Definition of Done before first Pi cutover

- Pi checkout is pinned to a known Git commit.
- Node/ARM64 smoke tests pass for all migrated deterministic modules.
- Homey and Pi clock/timezone handling agrees on `Europe/Amsterdam` and DST boundaries.
- Price horizon and next-day availability behaviour has shadow evidence.
- Planner output matches the accepted Homey/GitHub reference for replay fixtures.
- No duplicate actuator ownership exists.
- Kill switch and rollback are tested before physical writes.
- Observability records input revision, output revision/schema, decision reason and writer ownership.
- GitHub runtime baseline is updated in the same change cycle as any real cutover.

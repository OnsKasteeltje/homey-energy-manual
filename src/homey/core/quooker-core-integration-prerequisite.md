# Quooker — Core integration decision

Status: **REMOVED FROM HOMEY EMS CRITICAL PATH**

Date: 2026-08-30

## Project decision

Quooker detection is no longer a prerequisite for Core v0.11b and is removed from the Homey EMS critical input chain.

The Quooker is not controlled by the EMS. Detection was used primarily to classify approximately 1.5–1.7 kW of household consumption as Quooker heating for diagnostics and website enrichment. That classification benefit does not justify a permanent Homey producer with periodic device reads, freshness keepalives, Logic writes, aggregator wake-ups, parity work and additional rate-limit exposure.

For EMS control and safety, the P1 measurement already contains the Quooker load as normal household consumption. EV, warm-water, Power Intent, Gate and future Victron/DESS decisions therefore remain electrically correct without a dedicated Quooker classification signal.

## Homey architecture

The Homey critical path becomes:

`P1 / devices -> Core -> Power Intent / controls`

There is no required Quooker producer, no required `EM_Quooker_Commit` trigger and no Quooker freshness gate in Core v0.11b.

Consequences:

- Quooker Detector v0.3/v0.4 is not required for normal EMS operation;
- `EM_Quooker_Commit` is not part of the Core v0.11b input contract;
- the ten legacy `EM_Quooker_*` variables are not required inputs for v0.11b;
- the Snapshot Aggregator must not refresh a Quooker source group;
- Quooker parity is removed from the v0.11b acceptance gate;
- Quooker can no longer block Core v0.11b cut-over.

Legacy Quooker variables may remain temporarily for compatibility/history, but they must not be maintained merely to satisfy Core. Cleanup is a separate controlled migration after confirming that no remaining consumer depends on them.

## Optional future enrichment on Raspberry Pi

Quooker classification may later be implemented outside the Homey critical EMS runtime, preferably on the Raspberry Pi used for the future EMS runtime/website enrichment layer.

Possible inputs include native Quooker `onoff` / `energy_power` data or a lightweight fingerprint based on P1/device telemetry. Such enrichment is informational only and must not become a mandatory freshness dependency for Core or a competing real-time control loop.

## Acceptance effect

The previous v0.4 semantic-commit validation, 120-second keepalive validation and aggregator commit-trigger integration are cancelled as Core v0.11b prerequisites.

Core v0.11b may proceed once the remaining genuinely required inputs satisfy parity, freshness and load criteria.

# Price Source Cut-over Plan v0.1

_Status: PREPARED / GITHUB-ONLY / NOT DEPLOYED / NO HOMEY CHANGE_

## Objective

Replace the single-source PBTH production input for DYNAMIC quarter-hour pricing with a validated source-selection layer while preserving the existing downstream contract:

```text
selected normalized MARKET_EX_VAT series
  -> Contract Price Adapter
  -> EM2_ContractPrice_Context
  -> Planner / Power Intent
```

No planner, actuator or device behavior is changed by this cut-over package.

## Preconditions

Required before deployment approval:

- EnergyZero normal-day semantics validated;
- PBTH vs EnergyZero A/B exact on at least two live evenings;
- next local day completeness validated;
- deterministic selector with required horizon start/end guards;
- explicit PBTH semantic-promotion policy;
- unit tests green after latest hardening;
- DST 92/100-slot behavior covered;
- exact production planning horizon defined.

## Target production policy

```text
PRIMARY   ENERGYZERO_PUBLIC_REST
SECONDARY PBTH_INTERAPP_DAP_PRICES
CHECK     ENTSO-E (future independent validation lineage)
```

Only a source that passes schema, semantics, freshness, cadence and required-horizon coverage is eligible.

PBTH is eligible as `MARKET_EX_VAT` only after explicit semantic confirmation by the PBTH market-basis policy. No global assumption is permitted.

## Production boundary

The cut-over must occur only at the price-source boundary upstream of Contract Price Adapter v0.10 (or its successor).

Current:

```text
PBTH prices_json(next_hours)
  -> TEMP_PBTH_JSON_BUFFER
  -> Contract Price Adapter
```

Target:

```text
EnergyZero ----\
                -> Normalizer -> Selector -> selected MARKET_EX_VAT series
PBTH ----------/
                                      |
                                      v
                           Contract Price Adapter
```

The Contract Price Adapter remains responsible for supplier markup, tax/VAT treatment and import/export contract rules.

## Deployment stages

### Stage 0 — current state

- PBTH production unchanged.
- EnergyZero/selector read-only SHADOW.
- `productionSwitchAllowed=false`.

### Stage 1 — parallel production-shadow feed

- Run selector on production cadence.
- Publish selected source and diagnostics to a separate shadow context only.
- Do not feed Planner yet.
- Compare selected market series against current PBTH-driven adapter input.

Exit criterion: no unexplained semantic/timestamp/horizon mismatch over representative days.

### Stage 2 — adapter input cut-over

- Contract Price Adapter reads the selected normalized source series instead of the PBTH-specific buffer.
- No Planner code change.
- EnergyZero is preferred when eligible.
- PBTH is fallback when eligible and semantically confirmed.
- If neither source is eligible, publish price context as unavailable/diagnostic; never synthesize zero prices.

Exit criterion: context schema/horizon and planner output remain consistent with expected replay/shadow behavior.

### Stage 3 — cleanup

Only after stable operation:

- mark direct PBTH-specific production ingestion path SUPERSEDED;
- retain PBTH Inter-App source as SECONDARY;
- remove obsolete temporary buffers only after confirming no consumers remain.

## Rollback

Rollback must be one configuration/code-boundary reversal:

```text
selected source input -> OFF
legacy PBTH input     -> ON
```

Rollback must not require changing Planner, Power Intent, actuator writers or device flows.

Triggers for immediate rollback:

- malformed normalized series;
- missing current-quarter coverage;
- unexpected slot gaps/duplicates;
- selector oscillation caused by implementation error;
- Contract Price Context schema regression;
- Planner receives null/incorrect horizon unexpectedly;
- any downstream behavioral change not explained by price differences.

## Observability required at cut-over

For every selector publication log/publish:

- generated/retrieved timestamp;
- required horizon start/end;
- each source eligibility + reasons;
- source horizon start/end;
- selected source;
- price basis;
- slot count;
- PBTH semantic-validation status when PBTH is admitted;
- no-eligible-source condition.

The selected series provenance must be retained downstream so a Planner decision can be traced back to the exact source and source revision.

## Safety invariants

- no Homey device write from source adapters/selectors;
- no implicit EUR 0 for missing price;
- no source switch unless semantic basis is explicit;
- Planner remains source-agnostic;
- one production price context publisher only;
- physical actuator writers remain unchanged;
- rollback path prepared before deployment.

## Current release state

**NOT DEPLOYED.** This document is a production-preparation artifact only. Explicit deployment approval is still required after the remaining test/DST gates are closed.

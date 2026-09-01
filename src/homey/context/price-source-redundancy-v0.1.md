# Price Source Redundancy evaluation v0.1

_Status: GITHUB-ONLY ANALYSIS / NO HOMEY CHANGE / NOT DEPLOYED_

## Goal

Remove single-source dependence on PBTH for DYNAMIC quarter-hour pricing while preserving the existing `EM2_ContractPrice_Context` consumer contract.

Current production path remains:

`PBTH prices_json(next_hours) -> TEMP_PBTH_JSON_BUFFER -> Contract Price Adapter v0.10 -> EM2_ContractPrice_Context -> Planner`

The 2026-08-31 incident demonstrated that PBTH can have a truncated horizon even when next-day market prices are already published. The existing PBTH Inter-App API is a cleaner interface, but it reads the same PBTH internal price store and therefore does not create true source redundancy.

## Candidate independent sources

### 1. EnergyZero Public API — preferred independent candidate

EnergyZero documents a Public API `GetPrices` operation that returns definitive energy prices for the day before, the requested day, and the day after when available. EnergyZero also publicly states that electricity prices are quarter-hour based from 2026 onward and that next-day electricity prices are normally published around 15:00.

Why it is attractive:
- independent of the PBTH Homey app;
- native market-price use case;
- suitable for a lightweight server/Pi HTTP adapter;
- can provide day-ahead data independently from Homey runtime state;
- aligns with the future Pi-based EMS runtime.

Open validation points before production use:
- exact unauthenticated/authenticated access requirements for `GetPrices` in the intended machine-to-machine use case;
- exact response schema and timestamp semantics;
- whether returned electricity values are raw market prices or include VAT / commercial components;
- DST behavior and expected 92/96/100 quarter-hour slot counts;
- operational rate limits / SLA.

### 2. ENTSO-E Transparency Platform — strong canonical fallback candidate

ENTSO-E is a canonical European market-data source for bidding-zone day-ahead prices. It is independent from PBTH and suitable as an authoritative cross-check or fallback after normalization.

Advantages:
- independent upstream lineage;
- bidding-zone native (`10YNL----------L` for NL);
- suitable for timestamped quarter-hour market price series;
- strong provenance for source-health comparison.

Trade-offs:
- XML/API-token integration is somewhat heavier than a simple JSON endpoint;
- normalization, timezone and DST handling must be explicit;
- should be wrapped behind the same source adapter contract as every other source.

### 3. Nord Pool Market Data API — technically strong, economically rejected for this project

Nord Pool publishes official Day-Ahead prices in 15-minute resolution after the SDAC 15-minute transition and exposes them via its Market Data API.

However, current commercial API pricing is far beyond what is justified for a residential HEMS. This source is therefore **not selected as a production dependency**. It remains useful as a reference when validating market semantics.

## Target architecture

```text
                 +--------------------+
                 | EnergyZero source  |  preferred independent source
                 +---------+----------+
                           |
                 +---------v----------+
                 | Price Source       |
PBTH ----------->| Normalizer /       |----------> EM2_ContractPrice_Context
                 | Selector           |                |
ENTSO-E -------->|                    |                v
                 +---------+----------+             Planner
                           |
                           +--> source health / diagnostics
```

The Planner must never call PBTH, EnergyZero or ENTSO-E directly.

The source layer produces one normalized contract. Downstream consumers remain source-agnostic.

## Candidate normalized source contract

```json
{
  "schemaVersion": "price-source-v0.1",
  "source": "ENERGYZERO",
  "biddingZone": "10YNL----------L",
  "currency": "EUR",
  "resolutionMinutes": 15,
  "generatedAt": "2026-09-01T13:05:00Z",
  "retrievedAt": "2026-09-01T13:05:04Z",
  "priceBasis": "MARKET_EX_VAT",
  "slots": [
    {
      "start": "2026-09-01T13:00:00+02:00",
      "end": "2026-09-01T13:15:00+02:00",
      "marketPriceEurPerKwh": 0.05731,
      "importPriceEurPerKwh": null,
      "exportPriceEurPerKwh": null,
      "isForecast": false
    }
  ],
  "health": {
    "valid": true,
    "complete": true,
    "stale": false,
    "horizonEnd": "2026-09-02T00:00:00+02:00"
  }
}
```

`priceBasis` is mandatory. A value from one source may **never** silently be treated as equal to another source unless market-price/all-in semantics are proven equivalent.

## Source-selection policy candidate

Do not implement automatic failover until A/B validation proves semantic equivalence.

Initial SHADOW policy:

1. PBTH remains production publisher.
2. EnergyZero is fetched independently and normalized in SHADOW.
3. ENTSO-E is optional CHECK source for disagreement diagnosis.
4. Compare overlapping slots by timestamp, not array position.
5. Report source disagreement; do not silently switch source.

Future production policy after validation:

```text
PRIMARY   = independent market source (candidate: EnergyZero)
SECONDARY = PBTH
CHECK     = ENTSO-E
```

Failover is allowed only if:
- source schema validates;
- expected NL bidding zone is confirmed;
- resolution is 15 minutes;
- timestamps are monotonic and gap-free for the required horizon;
- values are finite;
- `priceBasis` matches the configured Contract Price transformation;
- data is fresh enough for the Planner horizon.

## Contract Price Adapter responsibility

The source adapter should publish **raw normalized market-price facts**. Contract-specific economics remain in the existing Contract Price Adapter.

Target separation:

```text
Price source
  -> normalized market price
  -> Contract Price Adapter
       + supplier markup
       + energy tax where applicable
       + VAT where applicable
       + import/export contract rules
  -> effective marginal import/export price
  -> Planner / Power Intent
```

This avoids coupling Planner logic to a supplier, public API or Homey app.

## Required validation pack — outside Homey

### V1 — schema and semantics

- capture one full Netherlands quarter-hour day from EnergyZero;
- verify 96 slots on a normal day;
- verify timestamps and `Europe/Amsterdam` conversion;
- identify raw market-price vs VAT/all-in basis from source documentation and sample values;
- document retrieval/publication time for next-day prices.

### V2 — PBTH A/B comparison

For every overlapping quarter-hour:

```text
timestamp
pbth_import_price
energyzero_market_price
normalized_pbth_market_price (if derivable)
delta
```

Acceptance criteria:
- timestamp alignment 100%;
- no unexplained 15-minute offset;
- after correcting known contract components, numerical differences must be explainable and stable;
- missing slots are explicit `null`/missing, never zero.

### V3 — horizon behavior

Observe at least one next-day publication event.

Capture:
- time EnergyZero first exposes tomorrow;
- time PBTH first exposes tomorrow;
- horizon length from both sources;
- whether either source briefly publishes a partial/incomplete next day.

This is the critical test for the 2026-08-31 failure mode.

### V4 — malformed/degraded source tests

Unit-test the normalizer against:
- truncated current day;
- missing tomorrow;
- one missing quarter-hour;
- duplicate timestamp;
- wrong resolution;
- wrong currency;
- NaN/non-numeric price;
- stale payload;
- DST 92/100-slot day.

Expected result: reject/degrade source; never synthesize €0/kWh.

## Current decision

**Prepare EnergyZero as the first independent SHADOW source. Keep PBTH production unchanged. Do not touch Homey yet.**

Nord Pool is rejected as a practical dependency because of commercial API cost. ENTSO-E remains the preferred independent validation/fallback lineage if EnergyZero semantics or access prove unsuitable.

## Next implementation step

Build a small deterministic source normalizer and fixture-based A/B test in GitHub/Pi-compatible JavaScript. No Homey calls are required for this step. Only after the source schema and numerical equivalence are proven should a runtime fetch path be connected to the Contract Price Adapter.

## External references checked 2026-09-01

- EnergyZero Public API documentation: `GetPrices` returns the requested day plus adjacent day data when available.
- EnergyZero current-prices page: quarter-hour electricity pricing in 2026; next-day publication around 15:00.
- Nord Pool documentation: official Market Data API prices use 15-minute intervals after SDAC 15-minute go-live.
- Nord Pool current market-data pricing: commercial API pricing is materially disproportionate for this residential HEMS use case.

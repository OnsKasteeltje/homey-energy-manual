# Price Source Redundancy evaluation v0.1

_Status: GITHUB-ONLY ANALYSIS / NO HOMEY CHANGE / NOT DEPLOYED_

## Goal

Remove single-source dependence on PBTH for DYNAMIC quarter-hour pricing while preserving the existing `EM2_ContractPrice_Context` consumer contract.

Current production path remains:

`PBTH prices_json(next_hours) -> TEMP_PBTH_JSON_BUFFER -> Contract Price Adapter v0.10 -> EM2_ContractPrice_Context -> Planner`

The 2026-08-31 incident demonstrated that PBTH can have a truncated horizon even when next-day market prices are already published. The existing PBTH Inter-App API is a cleaner interface, but it reads the same PBTH internal price store and therefore does not create true source redundancy.

## Candidate independent sources

### 1. EnergyZero Public API — validated independent candidate

Current endpoint validated live on 2026-09-01:

`https://public.api.energyzero.nl/public/v1/prices`

Electricity request parameters:
- `energyType=ENERGY_TYPE_ELECTRICITY`
- `interval=INTERVAL_QUARTER`
- `date=DD-MM-YYYY`

Observed response streams:
- `base` = market price excluding VAT
- `base_with_vat` = market price including VAT
- `all_in` = all-in excluding VAT
- `all_in_with_vat` = all-in including VAT

The API returned 288 quarter-hour rows per stream in the live capture: three complete 96-slot local days around the requested date. Consumers must therefore filter by explicit `Europe/Amsterdam` local calendar date and must not assume the response contains only the requested day.

Why it is attractive:
- independent of the PBTH Homey app;
- native quarter-hour market-price use case;
- suitable for a lightweight server/Pi HTTP adapter;
- can provide day-ahead data independently from Homey runtime state;
- aligns with the future Pi-based EMS runtime.

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

However, commercial API pricing is far beyond what is justified for a residential HEMS. This source is therefore **not selected as a production dependency**. It remains useful as a reference when validating market semantics.

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
  "source": "ENERGYZERO_PUBLIC_REST",
  "biddingZone": "10YNL----------L",
  "currency": "EUR",
  "resolutionMinutes": 15,
  "generatedAt": null,
  "retrievedAt": "2026-09-01T13:05:04Z",
  "priceBasis": "MARKET_EX_VAT",
  "slots": [
    {
      "start": "2026-09-01T13:00:00Z",
      "end": "2026-09-01T13:15:00Z",
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
    "horizonEnd": "2026-09-01T22:00:00Z"
  }
}
```

`priceBasis` is mandatory. A value from one source may **never** silently be treated as equal to another source unless market-price/all-in semantics are proven equivalent.

## Live A/B validation — 2026-09-01

A read-only HomeyScript compared PBTH Inter-App DAP15 data directly against all four EnergyZero streams by exact timestamp.

PBTH capture:
- device `NL_Netherlands`
- bidding zone `10YNL----------L`
- 15-minute interval
- 109 slots
- 109 confirmed / 0 forecast
- first slot `2026-09-01T18:45:00Z`
- last slot `2026-09-02T21:45:00Z`

EnergyZero response:
- 288 rows in each of the four streams
- full overlap with all 109 PBTH timestamps

Result for EnergyZero `base` (`MARKET_EX_VAT`):

```text
overlapSlots = 109
meanDelta    = 0
meanAbsDelta = 0
rmsDelta     = 0
stddevDelta  = 0
minDelta     = 0
maxDelta     = 0
```

Therefore, for the tested PBTH configuration and dataset:

`PBTH importPrice == EnergyZero base == MARKET_EX_VAT`

for every one of the 109 overlapping quarter-hours.

Other EnergyZero streams did not match PBTH:
- `base_with_vat`: mean delta about `-0.0360 EUR/kWh`
- `all_in`: constant delta `-0.09161 EUR/kWh`
- `all_in_with_vat`: mean delta about `-0.14685 EUR/kWh`

### Validation conclusion

**A/B VALIDATED — 109/109 exact timestamp and price matches for PBTH importPrice versus EnergyZero `base`.**

This is sufficient to promote EnergyZero from “candidate semantics unknown” to **validated independent SHADOW market-price source**.

It is not yet sufficient to enable automatic production failover. Remaining validation gates are:
- repeat on at least one additional normal day;
- observe next-day publication transition and compare source horizons;
- validate degraded/truncated PBTH behavior while EnergyZero remains complete;
- validate DST 92/100-slot dates;
- implement deterministic source-health and selector logic outside production.

## Source-selection policy

Current production policy remains unchanged:

1. PBTH remains production publisher.
2. EnergyZero is independent SHADOW source.
3. Compare source health and overlapping `MARKET_EX_VAT` slots.
4. Do not silently switch production source.

Target policy after remaining validation:

```text
PRIMARY   = ENERGYZERO_PUBLIC_REST / base / MARKET_EX_VAT
SECONDARY = PBTH_INTERAPP_DAP_PRICES / MARKET_EX_VAT
CHECK     = ENTSO-E
```

A selector may consider a source eligible only when:
- schema validates;
- bidding zone is `10YNL----------L`;
- currency is EUR;
- resolution is exactly 15 minutes;
- timestamps are monotonic and gap-free for the required horizon;
- values are finite;
- `priceBasis` is explicitly `MARKET_EX_VAT`;
- data is fresh enough for the Planner horizon;
- missing data is represented as missing, never as `0`.

Automatic production failover remains disabled until the shadow selector and horizon-publication tests pass.

## Contract Price Adapter responsibility

The source adapter should publish **raw normalized market-price facts**. Contract-specific economics remain in the existing Contract Price Adapter.

Target separation:

```text
Price source
  -> normalized MARKET_EX_VAT price
  -> Contract Price Adapter
       + supplier markup
       + energy tax where applicable
       + VAT where applicable
       + import/export contract rules
  -> effective marginal import/export price
  -> Planner / Power Intent
```

This avoids coupling Planner logic to a supplier, public API or Homey app.

## Required validation pack — status

### V1 — schema and semantics

**PASS for normal-day EnergyZero capture.**

Validated:
- current public REST endpoint;
- quarter-hour schema;
- numeric-string price parsing;
- local-date filtering;
- normal 96-slot local day;
- tomorrow available in the same live response;
- `base` semantics established by live PBTH A/B.

Still open:
- DST 92/100-slot exact-day behavior;
- operational rate limits / long-term availability.

### V2 — PBTH A/B comparison

**PASS — 109/109 exact.**

No timestamp offset and no numerical difference for PBTH `importPrice` versus EnergyZero `base`.

### V3 — horizon behavior

**PARTIAL PASS.**

At the 2026-09-01 test time both sources exposed next-day data. EnergyZero exposed a wider 288-slot response; PBTH exposed 109 future/current slots through the end of the next local day.

Still required: observe the actual next-day publication transition and a degraded/truncated source case.

### V4 — malformed/degraded source tests

**IN PROGRESS.**

Normalizer tests cover malformed price values, wrong slot duration, gap/duplicate cases and deterministic normalization. Remaining: exact DST expected-slot logic, stale payload policy and selector-level degraded-source tests.

## Current decision

**EnergyZero is now validated as an independent SHADOW source for the same `MARKET_EX_VAT` quarter-hour series used by PBTH in the tested configuration. Keep PBTH production unchanged. Build and validate the source selector outside Homey before any cut-over.**

Nord Pool remains rejected as a practical dependency because of commercial API cost. ENTSO-E remains the preferred independent validation/check lineage.

## Next implementation step

Implement a deterministic `Price Source Selector v0.1` in GitHub/Pi-compatible JavaScript. It must rank source eligibility from normalized health/horizon metadata, produce a SHADOW decision record, and never perform a production switch or device write.

# Price Source Redundancy evaluation v0.1

_Status: SHADOW VALIDATED / GITHUB-ONLY / NO HOMEY CHANGE / NOT DEPLOYED_

## Goal

Remove single-source dependence on PBTH for DYNAMIC quarter-hour pricing while preserving the existing `EM2_ContractPrice_Context` consumer contract.

Current production path remains:

`PBTH prices_json(next_hours) -> TEMP_PBTH_JSON_BUFFER -> Contract Price Adapter v0.10 -> EM2_ContractPrice_Context -> Planner`

The 2026-08-31 incident demonstrated that PBTH can have a truncated horizon even when next-day market prices are already published. The PBTH Inter-App API is a cleaner interface, but it reads the same PBTH internal price store and therefore does not create true source redundancy.

## Target policy

```text
PRIMARY   = ENERGYZERO_PUBLIC_REST / base / MARKET_EX_VAT
SECONDARY = PBTH_INTERAPP_DAP_PRICES / MARKET_EX_VAT
CHECK     = ENTSO-E
```

The Planner must never call PBTH, EnergyZero or ENTSO-E directly. The source layer publishes one normalized market-price contract. Contract-specific economics remain in the Contract Price Adapter.

## EnergyZero semantics

Validated endpoint:

`https://public.api.energyzero.nl/public/v1/prices`

Electricity request parameters:
- `energyType=ENERGY_TYPE_ELECTRICITY`
- `interval=INTERVAL_QUARTER`
- `date=DD-MM-YYYY`

Observed streams:
- `base` = `MARKET_EX_VAT`
- `base_with_vat` = market including VAT
- `all_in` = all-in excluding VAT
- `all_in_with_vat` = all-in including VAT

The API returns a broad window (observed 288 rows per stream), so consumers must filter/validate by explicit `Europe/Amsterdam` timestamps and may not assume the response contains only the requested day.

## Live A/B validation — 2026-09-01

Read-only HomeyScript comparison of PBTH DAP15 versus EnergyZero by exact timestamp:

```text
PBTH overlap      = 109 slots
EnergyZero stream = base / MARKET_EX_VAT
exact matches     = 109/109
mean delta        = 0
max delta         = 0
```

For the tested PBTH configuration:

`PBTH importPrice == EnergyZero base == MARKET_EX_VAT`

Other EnergyZero streams did not match PBTH and are not eligible as raw market-price input.

## Live selector validation — 2026-09-01

The live read-only selector probe returned:

```text
status                = OK
selectedSource        = ENERGYZERO_PUBLIC_REST
PBTH eligible         = true
EnergyZero eligible   = true
A/B overlap           = 109
A/B exact             = 109
productionSwitchAllowed = false
```

Both sources had sufficient next-day horizon. This validated the deterministic primary/secondary policy in SHADOW.

## Evening validation — 2026-09-02

A dedicated read-only evening validation was run at `2026-09-02T18:47:27.852Z` for local tomorrow `2026-09-03`.

Result:

```text
verdict                   = PASS
finding                   = BOTH_SOURCES_TOMORROW_READY
selectorWouldChoose       = ENERGYZERO_PUBLIC_REST
productionSwitchAllowed   = false
```

EnergyZero:
- 288 total returned rows;
- tomorrow exactly 96 quarter-hours;
- first tomorrow slot `2026-09-02T22:00:00Z`;
- last tomorrow slot `2026-09-03T21:45:00Z`;
- complete next local day = true.

PBTH:
- 109 total slots;
- 109 confirmed / 0 forecast;
- tomorrow exactly 96 quarter-hours;
- identical first/last tomorrow timestamps;
- complete next local day = true.

A/B:

```text
overlapSlots     = 109
exactMatchSlots  = 109
maxAbsDelta      = 2.7755575615628914e-17
exact            = true
```

The non-zero machine epsilon is floating-point representation only and is economically/numerically zero for this purpose.

### Evening validation conclusion

**PASS — second independent normal-day validation. EnergyZero and PBTH both delivered the complete next local day and all 109 overlapping quarter-hours matched within machine precision.**

This promotes the source architecture to **SHADOW VALIDATED**. It does not itself prove a live PBTH-lag incident, but the selector remains designed to reject a source whose required start/end coverage is insufficient.

## Selector hardening after validation

`Price Source Selector v0.1` now evaluates both ends of the required horizon:

- `requiredHorizonStart`: reject `HORIZON_START_TOO_LATE` when the source does not cover the required start/current interval;
- `requiredHorizonEnd`: reject `HORIZON_TOO_SHORT` when future coverage is insufficient;
- source schema, NL bidding zone, EUR, 15-minute resolution, explicit `MARKET_EX_VAT`, freshness, finite prices and gap-free cadence remain mandatory.

The selector remains pure deterministic SHADOW logic with `productionSwitchAllowed=false`.

## PBTH semantic promotion policy

The generic PBTH normalizer remains conservative and does **not** globally claim `MARKET_EX_VAT` semantics.

`pbth-market-basis-policy-v0.1.mjs` now owns the explicit promotion. It may map PBTH `importPriceEurPerKwh` to normalized `marketPriceEurPerKwh` only when:

- reference source is explicitly `MARKET_EX_VAT`;
- bidding zone, currency and 15-minute resolution match;
- at least one timestamp overlaps;
- every overlapping finite PBTH/reference price matches within a strict tolerance;
- otherwise it fails closed and PBTH is not admitted as a normalized market-price source.

This removes the previous hardcoded semantic promotion from the E2E runner.

## Validation pack status

### V1 — schema and semantics

**PASS for normal-day EnergyZero behavior.**

Validated:
- public REST endpoint;
- quarter-hour schema;
- numeric-string prices;
- normal 96-slot local day;
- multi-day response behavior;
- `base = MARKET_EX_VAT` by PBTH A/B.

Open:
- explicit DST 92/100-slot day tests;
- operational long-term/rate-limit observation.

### V2 — PBTH A/B

**PASS twice on separate live evenings.**

2026-09-01: 109/109 exact.

2026-09-02: 109/109 exact within machine precision (`maxAbsDelta ~2.78e-17`).

### V3 — horizon behavior

**PASS for normal evening next-day readiness.**

On 2026-09-02 both sources exposed a complete 96-slot next local day. The selector now validates required start and end coverage explicitly.

Still desirable but not a blocker for further preparation: capture a naturally degraded/truncated PBTH case while EnergyZero remains complete.

### V4 — malformed/degraded logic

**PASS for current selector logic tests, subject to rerun after the latest hardening commit.**

Coverage includes bad basis, stale retrieval, gap/duplicate, insufficient future horizon, no eligible source, and required-horizon-start rejection. DST exact-day slot-count tests remain open.

## Current decision

**SHADOW VALIDATED.**

EnergyZero is the preferred independent raw market-price source. PBTH is the secondary source only after explicit same-run semantic validation/promotion. Production remains unchanged until a controlled cut-over package is reviewed.

## Production preparation gates

Before cut-over:

1. Re-run unit tests after selector/policy hardening.
2. Add direct tests for PBTH semantic promotion success/fail-closed behavior.
3. Add DST 92/100 expected-day tests to the EnergyZero normalization/coverage logic.
4. Define planner-relevant `requiredHorizonStart` and `requiredHorizonEnd` from the actual planning window rather than a generic rolling 24 hours.
5. Produce a cut-over/rollback plan that changes only the price-source input to the existing Contract Price Adapter.
6. Keep all Homey production flows unchanged until explicit deployment approval.

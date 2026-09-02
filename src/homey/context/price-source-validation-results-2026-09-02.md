# Price source validation results — 2026-09-02

_Status: GITHUB-ONLY / SHADOW / NO HOMEY CHANGE / NOT DEPLOYED_

## Live evening validation

`EM2_PRICE_SOURCE_EVENING_VALIDATION_V0.1` returned PASS at `2026-09-02T18:47:27.852Z`.

- EnergyZero tomorrow 2026-09-03: 96/96 slots, complete.
- PBTH tomorrow 2026-09-03: 96/96 slots, complete.
- PBTH total: 109 confirmed / 0 forecast.
- A/B overlap: 109 slots.
- A/B exact match: 109/109.
- maxAbsDelta: `2.7755575615628914e-17` (machine precision only).
- selector would choose: `ENERGYZERO_PUBLIC_REST`.
- productionSwitchAllowed: false.

## Selector hardening tests

Executed locally against the repository logic after adding `requiredHorizonStart` validation.

```text
price-source-selector-v0.1: 7/7 PASS
```

Coverage includes:
- EnergyZero primary preference;
- PBTH fallback on insufficient end horizon;
- rejection when source begins after required horizon start;
- bad price basis;
- stale retrieval;
- slot gap/duplicate;
- no eligible source.

## PBTH market-basis policy tests

Added `pbth-market-basis-policy-v0.1.test.mjs` and executed locally.

```text
6 tests / 6 PASS
```

Coverage includes:
- exact semantic promotion to `MARKET_EX_VAT`;
- machine-level epsilon within tolerance;
- fail-closed on semantic mismatch;
- fail-closed on no timestamp overlap;
- fail-closed on wrong reference basis;
- fail-closed on bidding-zone mismatch.

## DST helper tests

Added `price-source-dst-v0.1.mjs` plus tests and executed locally.

```text
4 tests / 4 PASS
```

Validated expected Europe/Amsterdam quarter-hour counts:
- normal day: 96 slots;
- spring DST transition 2026-03-29: 92 slots;
- autumn DST transition 2026-10-25: 100 slots;
- wrong slot count on a DST day fails closed.

## Remaining production gate

The DST helper is validated but still needs to be wired into the EnergyZero normalizer / day-completeness decision so `health.complete` is based on the exact expected slot count for the requested local date rather than accepting any of 92/96/100 generically.

After that integration, rerun normalizer + selector + policy tests and review the cut-over plan before any Homey production change.

# PBTH Inter-App API evaluation v0.1

_Status: GITHUB-ONLY ANALYSIS / NO HOMEY CHANGE / NO RUNTIME PROMOTION_

## Context

Current production DYNAMIC price ingestion in `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD` uses the PBTH flow action `prices_json(next_hours)` and passes the returned JSON through `TEMP_PBTH_JSON_BUFFER` before publishing normalized `EM2_ContractPrice_Context`.

The incident on 2026-08-31 showed that PBTH itself can have only the remainder of the current day available while tomorrow market prices are already published. `meter_price_next_day_*` was `null`, so the missing horizon was upstream of the Contract Price Adapter and Planner.

PBTH upstream now exposes a Homey Inter-App API endpoint `GET /dap-prices` plus realtime event `dap-prices-updated`.

## Upstream API contract

PBTH `api.js` documents:

```js
const phApi = this.homey.api.getApiApp('com.gruijter.powerhour');
const data  = await phApi.get('/dap-prices');

phApi.on('realtime', ({ name, data }) => { ... });
// event name: dap-prices-updated
```

The endpoint delegates to `homey.app.getDapPricesPayload()`.

PBTH `getDapPricesPayload()` returns:

```text
{
  generatedAt,
  prices: [
    {
      deviceId,
      deviceName,
      driverType,
      biddingZone,
      currency,
      priceInterval,
      slots: [
        { time, importPrice, exportPrice, isForecast }
      ]
    }
  ]
}
```

For each `dap`, `dap15` and `dapg` device it exposes all stored slots from the start of the current period onward. The payload therefore preserves timestamps, explicit 15-minute interval information, import/export values and forecast provenance.

## Comparison with current v0.10 path

### Current flow-card path

`PBTH prices_json(next_hours)` -> `TEMP_PBTH_JSON_BUFFER` -> publisher

Advantages:
- already deployed and smoke-validated;
- simple numeric array;
- no custom Homey app required;
- current Context consumers already work with it.

Limitations:
- timestamps are lost;
- device identity / bidding zone are implicit;
- export price and `isForecast` metadata are lost;
- temporary Logic buffer is required;
- semantic alignment assumes slot 0 equals current 15-minute period;
- event refresh needs an additional PBTH Flow trigger branch;
- diagnosing upstream PBTH state is harder because the payload carries little provenance.

### Inter-App API path

`PBTH GET /dap-prices` -> select expected device/bidding zone -> normalize directly -> Context

Advantages:
- timestamped slots, removing positional ambiguity;
- explicit `deviceId`, `driverType`, `biddingZone`, `priceInterval` and currency;
- import and export prices available in the same payload;
- explicit forecast marker per slot;
- no temporary Logic JSON buffer is architecturally required;
- realtime `dap-prices-updated` event is a native update signal;
- deterministic validation is possible before publication: expected device, zone `10YNL----------L`, `dap15`, `priceInterval=15`, strictly increasing timestamps, no gaps, finite prices;
- better observability and future Pi migration compatibility because the normalized source contract is richer.

Limitations / important non-solution:
- the API reads `device.prices`, i.e. the same PBTH internal stored series used elsewhere. It does **not** bypass PBTH's provider/fetch machinery.
- therefore it would **not have fixed the 2026-08-31 missing-tomorrow incident** if PBTH's stored series itself lacked tomorrow prices.
- it requires an executable consumer with access to Homey's Inter-App API; an Advanced Flow HomeyScript must first be proven capable of `homey.api.getApiApp(...)`. Do not assume this without a targeted compatibility test.
- coupling moves from PBTH Flow-card API to PBTH Inter-App API. Both remain dependencies on PBTH.

## Architecture conclusion

The Inter-App API is a **better data interface**, but not an upstream price-source redundancy mechanism.

Recommended architecture:

1. Keep the current v0.10 flow-card path as production baseline until a shadow implementation is validated.
2. Do not deploy the previously prepared `<12h` event-refresh as a fix for missing PBTH prices; it cannot create absent upstream data.
3. Prepare an Inter-App API adapter in SHADOW only.
4. Compare API payload against `prices_json(next_hours)` over multiple refreshes using timestamps and overlapping price values.
5. Only promote if the API path is demonstrably lower-load and at least equally reliable.
6. Retain a separate upstream-health guard: when market prices are expected after ~13:00 but PBTH horizon still ends near midnight, mark source health degraded rather than attempting repeated Planner refreshes.

## Candidate normalized mapping

For the expected PBTH device:

- `biddingZone === '10YNL----------L'`
- `driverType === 'dap15'`
- `priceInterval === 15`
- select slots with finite `importPrice`
- require monotonic 15-minute timestamps
- preserve timestamps in a future context field such as `priceSlots`
- preserve current additive `priceSeries` for backward compatibility during migration

Candidate additive structure:

```json
{
  "source": "PBTH_INTERAPP_DAP_PRICES",
  "priceSeries": [0.1924, 0.1984],
  "priceSlots": [
    {"time":"...","importPrice":0.1924,"exportPrice":null,"isForecast":false}
  ],
  "sourceMeta": {
    "deviceId":"...",
    "driverType":"dap15",
    "biddingZone":"10YNL----------L",
    "priceInterval":15,
    "generatedAt":"..."
  }
}
```

No existing consumer should depend on `priceSlots` until shadow validation is complete.

## Validation plan — outside Homey first

- Source-level contract review: **PASS**.
- Confirm endpoint returns same PBTH internal `device.prices`: **PASS**.
- Confirm it cannot repair missing upstream tomorrow prices: **PASS**.
- Define deterministic normalizer and schema guards in GitHub: **NEXT**.
- Unit-test normalizer against synthetic complete, truncated, gapped and malformed payloads: **NEXT**.
- Prepare one minimal Homey compatibility probe for `getApiApp('/dap-prices')`: **PENDING; do not run until GitHub pack is complete**.
- SHADOW A/B against current `prices_json(next_hours)`: **PENDING**.

## Decision

**Do not replace v0.10 yet.**

Proceed with a GitHub-only SHADOW candidate because the Inter-App API provides a materially cleaner and more observable price interface. Treat the 2026-08-31 incident separately as PBTH provider/fetch health; changing consumer interface alone would not solve it.

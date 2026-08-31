# PBTH `next_hours` / Planner price-horizon root-cause analysis — 2026-08-31

Status: **GITHUB-ONLY ANALYSIS / NO HOMEY CHANGE**

## Question

Why does the Planner show a 96-slot 24h energy axis while only the remaining evening price slots are populated, even though this appeared to work the previous day?

## Upstream PBTH code evidence

The upstream `gruijter/com.gruijter.powerhour` implementation establishes the following:

1. `prices_json(period=next_hours)` returns `device.state.pricesNextHours` directly.
2. `pricesNextHours` is built from **all stored price objects at or after the current period**, not from "today only":

```js
const pricesNextHours = this.prices
  .filter((hourInfo) => hourInfo.time >= periods.periodStart)
  .map((hourInfo) => hourInfo.muPrice);
```

3. `this.prices` is the merged stored price set. When tomorrow market prices are fetched, they are merged into this set. If PBTH forecast pricing is enabled, forecast values can also be appended after the last market price.
4. After a successful market-price fetch, PBTH compares old and new data for `this_day`, `tomorrow`, and `next_hours`.
5. For `next_hours`, PBTH selects the full interval from the current period to the end of available stored prices. If the selected length grows or values change materially, it fires the native `new_prices` trigger for `period=next_hours`.

Therefore the hypothesis that PBTH `next_hours` is intrinsically limited to the remainder of the current calendar day is **rejected by upstream code**.

## What the current Planner snapshot proves

The published Planner snapshot on 2026-08-31 showed:

- energy axis: 96 slots / 24h;
- dynamic price slots: only 19-20 slots;
- price quality: `GOOD`;
- price freshness: `fresh=true`;
- price usability: `usable=true`.

This means the Planner is behaving as designed: it keeps the 24h physical planning axis and marks future price slots unknown when the normalized price context contains fewer prices.

## Root-cause boundary

The visible problem is therefore upstream of Planner scheduling logic:

```text
PBTH available stored prices
        -> Contract Price Adapter
        -> normalized priceSeries
        -> Planner 96-slot axis
```

At the observed evening snapshot, either:

A. PBTH had not yet fetched/merged tomorrow prices, so `pricesNextHours` genuinely ended at midnight; or

B. PBTH had already extended its state, but the Contract Price Adapter had not yet consumed that newer state.

The Planner itself is not the cause of the truncated price horizon.

## Implication for the prepared event-refresh branch

The prepared event-refresh design remains technically valid and is now better justified:

- PBTH already emits `new_prices(period=next_hours)` when its future series extends or changes;
- on that event, the Context layer can perform exactly one `prices_json(next_hours)` call;
- semantic comparison prevents unnecessary downstream fan-out;
- Planner remains a read-only consumer and never polls PBTH directly.

However, this event branch is an **latency/recovery improvement**, not proof that PBTH itself had tomorrow prices at the moment of the screenshot.

## Important fallback observation

The deployed v0.10 Contract Price Adapter already runs every 15 minutes and, on DYNAMIC, performs one `prices_json(next_hours)` request. Therefore, once PBTH has extended `pricesNextHours`, the existing scheduled path should normally propagate the longer series within at most one adapter cycle even without the event branch.

This gives a clean post-deployment diagnostic distinction:

- PBTH event + extended response -> event branch removes up-to-15-minute latency;
- no PBTH extension -> no Context change is possible, correctly;
- PBTH extended but scheduled adapter still does not publish within one cycle -> investigate Adapter execution/publication, not Planner.

## Decision

1. Do **not** change Planner horizon construction.
2. Do **not** fabricate prices beyond the accepted PBTH horizon.
3. Keep the 96-slot energy axis and explicit unknown trailing price zone.
4. Retain the prepared Context-side PBTH `new_prices(next_hours)` event-refresh architecture.
5. Before any additional functional change, validate only the smallest remaining runtime fact: after PBTH receives tomorrow prices, does `prices_json(next_hours)` extend across midnight as upstream code says it should?
6. No broad Homey discovery is justified for this validation.

## Confidence

**High** on the software root-cause boundary and PBTH `next_hours` semantics, because both follow directly from upstream source code.

**Not yet runtime-proven** whether tomorrow prices were already present in the user's PBTH device at the exact time of the observed screenshot.

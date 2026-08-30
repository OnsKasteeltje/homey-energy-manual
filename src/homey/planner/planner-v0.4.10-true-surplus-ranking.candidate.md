# Planner v0.4.10 SHADOW candidate — true-surplus WW ranking

## Problem

Current `rankWW()` caps PV value at `BOILER_W` before ranking:

```js
const ac=Math.min(BOILER_W,Math.max(0,a.pvSurplusBeforeFlexW||0));
const zc=Math.min(BOILER_W,Math.max(0,z.pvSurplusBeforeFlexW||0));
```

As soon as two candidate slots both have >= 1900 W forecast surplus, they become equal on the first ranking dimension. Under DYNAMIC, price then wins the tie. This can pull WW earlier into cheap/negative-price slots even when later slots have materially more true forecast PV surplus.

That conflicts with the intended policy: **true PV surplus first; price only after PV quality is exhausted/equal**.

## Proposed ranking

Replace only `rankWW()` with the following SHADOW candidate logic:

```js
const rankWW=c=>[...c].sort((a,z)=>{
  const as=Math.max(0,Number(a.pvSurplusBeforeFlexW)||0);
  const zs=Math.max(0,Number(z.pvSurplusBeforeFlexW)||0);
  const af=as>=BOILER_W;
  const zf=zs>=BOILER_W;

  // 1. Full-PV slots always beat partial/no-PV slots.
  if(af!==zf)return af?-1:1;

  // 2. Within the same PV class, prefer the larger *true* forecast surplus.
  //    Do not cap at BOILER_W before ranking; extra surplus is useful margin
  //    against forecast error and concurrent household load.
  if(zs!==as)return zs-as;

  // 3. Only then use price for DYNAMIC contracts.
  if(contract==='DYNAMIC'){
    const ap=finite(a.price_eur_kwh)?Number(a.price_eur_kwh):999;
    const zp=finite(z.price_eur_kwh)?Number(z.price_eur_kwh):999;
    if(ap!==zp)return ap-zp;
  }

  // 4. Stable deterministic final tie-breaker.
  return Date.parse(a.start)-Date.parse(z.start);
});
```

`reserveWW()` remains unchanged. The selected slot still publishes actual boiler PV coverage as `min(BOILER_W, pvSurplusBeforeFlexW)` and grid remainder as `BOILER_W - pvCoverageW`. Only the candidate order changes.

## Architecture / safety

- SHADOW only.
- No physical writes.
- No new Homey reads.
- No change to WW energy requirement, deadline, day-boundary behavior, modeled boiler power or fallback duration.
- No change to Core, Power Intent, adapters, gates or actuators.
- No competing runtime optimizer is introduced.
- Keeps the single Planner owner for WW slot selection.

## A/B acceptance criteria

Run the same deterministic 96-slot input through current ranking and candidate ranking.

PASS requires:

1. Exactly the same required WW energy and number of allocated slots.
2. Every selected slot remains before the WW deadline.
3. Candidate never selects a lower-PV slot while an otherwise eligible higher true-surplus slot remains unselected, except where both true surpluses are exactly equal.
4. For equal true-surplus slots under DYNAMIC, lower price still wins.
5. Sum of selected `pvCoverageW` is >= current ranking for the same input.
6. Sum of selected `gridRequiredW` is <= current ranking for the same input.
7. No change outside Planner SHADOW output.

## Expected effect on the 2026-08-31 forecast

The currently visible WW block is concentrated around the cheap/negative-price period even though the energy-balance forecast shows stronger PV surplus later in the afternoon. With this ranking, later higher-surplus slots should move ahead of earlier lower-surplus slots. Price remains relevant only after true PV surplus is equal.

## Promotion gate

Do not deploy to Homey yet. First perform an offline A/B replay against the current published Planner snapshot and report selected WW slots, total PV-covered kWh, grid-required kWh and price cost for both algorithms.
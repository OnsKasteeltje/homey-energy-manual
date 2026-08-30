# Planner v0.4.10 SHADOW candidate — true-surplus WW ranking

## Root cause confirmed against active v0.4.9

The active Homey Planner is `24h Energy Plan v0.4.9 SHADOW LOW-LOAD`.

Its WW policy is two-stage:

1. `rankWWFullSurplus()` selects only slots with `pvSurplusBeforeFlexW >= BOILER_W`.
2. If WW energy remains, `rankWWGrid()` ranks all remaining slots.

For DYNAMIC + usable price context, `rankWWGrid()` currently sorts **price first** and only then PV surplus:

```js
const rankWWGrid=c=>[...c].sort((a,z)=>{
  if(contract==='DYNAMIC'&&priceUsable&&finite(a.price_eur_kwh)&&finite(z.price_eur_kwh)){
    const d=Number(a.price_eur_kwh)-Number(z.price_eur_kwh);
    if(Math.abs(d)>1e-9)return d;
  }
  const sd=(z.pvSurplusBeforeFlexW||0)-(a.pvSurplusBeforeFlexW||0);
  return sd||Date.parse(a.start)-Date.parse(z.start);
});
```

That is the actual reason the 2026-08-31 DYNAMIC forecast concentrated WW around the negative-price window even though materially larger partial PV surplus existed later. In that snapshot there were **no full-PV boiler slots**: the strongest forecast surplus was about 1.49 kW, below the 1.9 kW modeled boiler load. Therefore the entire 7.6 kWh obligation fell into `rankWWGrid()`, where price became the primary dimension.

This conflicts with the intended policy interpretation: **use true PV surplus first; use dynamic price to optimize the unavoidable grid remainder, not to displace materially better PV self-consumption.**

## Proposed v0.4.10 ranking

Keep the full-PV stage unchanged. Refine only the remaining-grid stage:

- partial-PV slots (`0 < surplus < BOILER_W`): true PV surplus descending, then price, then time;
- zero-PV slots: price first, then time;
- FIXED contract behavior remains effectively unchanged because price is not a ranking dimension there.

Candidate:

```js
const rankWWGrid=c=>[...c].sort((a,z)=>{
  const as=Math.max(0,Number(a.pvSurplusBeforeFlexW)||0);
  const zs=Math.max(0,Number(z.pvSurplusBeforeFlexW)||0);
  const ap=as>0;
  const zp=zs>0;

  // 1. Any partial-PV opportunity beats a zero-PV grid slot.
  if(ap!==zp)return ap?-1:1;

  // 2. Within partial-PV slots, maximize true self-consumption first.
  if(ap&&zp&&zs!==as)return zs-as;

  // 3. Dynamic price optimizes only after PV quality is equal/exhausted.
  if(contract==='DYNAMIC'&&priceUsable&&finite(a.price_eur_kwh)&&finite(z.price_eur_kwh)){
    const d=Number(a.price_eur_kwh)-Number(z.price_eur_kwh);
    if(Math.abs(d)>1e-9)return d;
  }

  return Date.parse(a.start)-Date.parse(z.start);
});
```

`reserveWW()` and all WW obligation/deadline semantics remain unchanged.

## Offline A/B replay — captured 2026-08-31 DYNAMIC forecast

Source snapshot generated around 2026-08-30 22:00 local, Planner schema `EM2_ENERGY_PLAN_24H_V0.4.9`.

Requirement: 240 min × 1.9 kW = **7.6 kWh**, i.e. 16 quarter-hour slots before 19:00.

### Current v0.4.9 selection

Selected slot indices:

`52,53,54,55,56,57,58,59,60,61,62,63,64,65,67,68`

This selection follows the cheap/negative-price window and has mean true forecast PV surplus about **444.5 W**.

Calculated energy split:

- PV-covered: **1.7780 kWh**
- grid-required: **5.8220 kWh**
- grid-energy price contribution over these slots: about **-€0.0088**

### v0.4.10 candidate selection

Selected slot indices:

`55,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74`

Mean true forecast PV surplus rises to about **781.2 W**.

Calculated energy split:

- PV-covered: **3.1248 kWh**
- grid-required: **4.4753 kWh**
- grid-energy price contribution over these slots: about **-€0.0013**

### Delta

- PV self-consumption: **+1.3468 kWh**
- grid energy: **-1.3468 kWh**
- direct dynamic-price advantage given up: about **€0.0074** (less than one cent for this captured forecast)
- 7 slots move from the early cheap-price block to higher-surplus later slots; 9 slots remain common.

This is a strong A/B PASS for the intended policy: substantially more forecast PV is consumed for a negligible direct price trade-off.

## Architecture / safety

- SHADOW only.
- No physical writes.
- No new Homey reads.
- No change to WW energy requirement, hard 19:00 deadline, day-boundary behavior, modeled boiler power or fallback duration.
- No change to Core, Power Intent, adapters, gates or actuators.
- No competing runtime optimizer.
- Single Planner owner for WW slot selection remains intact.

## Promotion criteria

PASS requires:

1. same WW required energy and allocated slot count;
2. all selected slots remain before the hard WW deadline;
3. PV-covered kWh is not lower;
4. grid-required kWh is not higher;
5. equal-PV DYNAMIC ties still prefer lower price;
6. zero-PV remainder still prefers cheapest usable grid slots;
7. no change outside Planner SHADOW output.

## Promotion gate

The captured DYNAMIC A/B replay passes the energy criteria. Before Homey promotion, update the exact v0.4.9 source as a v0.4.10 SHADOW candidate and run one deterministic repository replay/syntax test. Do not change any actuator or LIVE control path.
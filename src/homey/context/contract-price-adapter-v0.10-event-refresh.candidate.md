# EM v2 | 30 Context | Contract Price Adapter v0.10 EVENT REFRESH CANDIDATE

Status: **READY FOR CONTROLLED HOMEY DEPLOYMENT / NOT YET DEPLOYED**

Base runtime: `Contract Price Adapter v0.9 DYNAMIC LOW-LOAD`

## Objective

Extend the existing low-load DYNAMIC price adapter with an event-driven PBTH refresh only while the currently published dynamic-price horizon is below 12 hours.

The Planner does **not** call PBTH. The Context/Contract Price Adapter owns the refresh.

## Exact PBTH cards

For the configured PBTH **Day-Ahead 15m E Prices** device:

- WHEN card: **`New prices received for period`**
- ACTION card already used by v0.9: **`prices_json(next_hours)`**

The PBTH event is only an opportunity to refresh. It does not by itself imply that the usable horizon changed.

## Runtime topology

```text
existing scheduled 15-minute v0.9 path -------------------------+
                                                                  |
PBTH: New prices received for period                              |
        |                                                         |
        v                                                         |
read published Contract Price Context                             |
        |                                                         |
        +-- contract != DYNAMIC -----------------> STOP            |
        |                                                         |
        +-- horizonHours >= 12 ------------------> STOP            |
        |                                                         |
        +-- cooldown active ---------------------> STOP            |
        |                                                         |
        v                                                         |
PBTH prices_json(next_hours) exactly once                          |
        |                                                         |
        v                                                         |
TEMP_PBTH_JSON_BUFFER                                              |
        |                                                         |
        v                                                         |
normalize + validate contiguous 15-minute price series             |
        |                                                         |
        +-- degraded (<4 slots) --> retain prior context            |
        |                           record failed attempt            |
        |                                                         |
        +-- unchanged -----------> retain prior context             |
        |                           start 60-minute cooldown         |
        |                                                         |
        +-- changed/extended ----> publish context ----------------+
                                    clear cooldown
                                    normal semantic downstream chain
                                    -> Planner
```

## Admission rule

An event-driven PBTH action is admitted only when all are true:

```text
contractType == DYNAMIC
AND current horizonHours < 12
AND no-change cooldown is not active
```

If any condition fails, the event path performs **zero** `prices_json(next_hours)` calls.

## Semantic-change rule

A returned price series is useful only if at least one of these holds:

1. valid contiguous slot count increases;
2. effective price horizon extends;
3. one or more prices in the overlapping horizon changes materially.

An identical result must not republish the canonical context and must not fan out to Planner.

## Cooldown

When an admitted event refresh yields no semantic improvement:

- record the attempt timestamp;
- suppress further event-driven attempts for 60 minutes;
- allow at most one unsuccessful extra refresh per hour;
- never loop or immediately retry;
- keep the normal 15-minute scheduled v0.9 path intact.

A successful horizon extension or semantic price change clears the cooldown.

## Required event-state variable

Use one text Logic variable:

`EM2_ContractPrice_EventRefresh_State`

Recommended JSON payload:

```json
{
  "lastAttemptAt": null,
  "cooldownUntil": null,
  "lastResult": "NEVER",
  "lastReason": null
}
```

Allowed result values:

- `NEVER`
- `SKIPPED_FIXED`
- `SKIPPED_HORIZON_OK`
- `SKIPPED_COOLDOWN`
- `DEGRADED`
- `UNCHANGED`
- `UPDATED`

## Targeted Logic IDs inherited from v0.9

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EM2_Contract_Type`: `211e5846-aada-4607-8d52-01b2ef578866`
- `TEMP_PBTH_JSON_BUFFER`: `29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b`
- `EM2_ContractPrice_Context`: `93e41221-6b4d-4f5f-83dc-997c9620f758`
- `EM2_ContractPrice_Source`: `3e5a182d-2479-479a-bb58-42a27f4a4e23`
- `EM2_ContractPrice_Quality`: `abedc6f4-cfee-4496-9b3c-418f1f3ad2bc`
- `EM2_ContractPrice_Horizon`: `587ea957-f9e9-44c7-b975-3bed53bd9ab8`
- `EM2_ContractPrice_UpdatedAt`: `77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb`

The event-state variable ID must be captured after it is provisioned once in Homey; do not rediscover variables broadly.

## HomeyScript: event eligibility gate

This script is intended to run **before** the PBTH action card on the event branch. It returns `true` only if exactly one PBTH refresh may be attempted.

```js
// Contract Price Adapter v0.10 — EVENT ELIGIBILITY GATE
// Targeted reads only. No PBTH call here. No device writes.

const IDS={
  canonical:'8d346495-f183-4072-86d0-c4bc9da94e2e',
  context:'93e41221-6b4d-4f5f-83dc-997c9620f758',
  eventState:'__CAPTURE_ONCE_AFTER_PROVISIONING__'
};

const COOLDOWN_MS=60*60*1000;
const read=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};

const nowMs=Date.now();
const nowIso=new Date(nowMs).toISOString();
const canonical=await read(IDS.canonical);
const contract=String(canonical?.value||'FIXED').toUpperCase();
const stateVar=await read(IDS.eventState);
const eventState=parse(stateVar?.value)||{lastAttemptAt:null,cooldownUntil:null,lastResult:'NEVER',lastReason:null};

async function stop(result,reason){
  await write(IDS.eventState,JSON.stringify({...eventState,lastResult:result,lastReason:reason}));
  return false;
}

if(contract!=='DYNAMIC') return await stop('SKIPPED_FIXED','CONTRACT_NOT_DYNAMIC');

const contextVar=await read(IDS.context);
const context=parse(contextVar?.value)||{};
const horizonHours=Number(context.horizonHours);
if(Number.isFinite(horizonHours)&&horizonHours>=12)
  return await stop('SKIPPED_HORIZON_OK','HORIZON_GTE_12H');

const cooldownUntilMs=Date.parse(String(eventState.cooldownUntil||''));
if(Number.isFinite(cooldownUntilMs)&&nowMs<cooldownUntilMs)
  return await stop('SKIPPED_COOLDOWN','NO_CHANGE_COOLDOWN');

await write(IDS.eventState,JSON.stringify({
  ...eventState,
  lastAttemptAt:nowIso,
  lastResult:'ATTEMPT_ADMITTED',
  lastReason:'HORIZON_LT_12H'
}));
return true;
```

## HomeyScript: post-fetch semantic processor

Run this immediately after PBTH `prices_json(next_hours)` has written its token into `TEMP_PBTH_JSON_BUFFER`.

```js
// Contract Price Adapter v0.10 — EVENT POST-FETCH PROCESSOR
// Targeted Logic reads/writes only. Context-only. No actuator/device writes.

const IDS={
  mirror:'211e5846-aada-4607-8d52-01b2ef578866',
  buffer:'29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',
  context:'93e41221-6b4d-4f5f-83dc-997c9620f758',
  source:'3e5a182d-2479-479a-bb58-42a27f4a4e23',
  quality:'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',
  horizon:'587ea957-f9e9-44c7-b975-3bed53bd9ab8',
  updatedAt:'77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb',
  eventState:'__CAPTURE_ONCE_AFTER_PROVISIONING__'
};

const STEP_MS=15*60000,COOLDOWN_MS=60*60*1000,EPS=1e-9;
const read=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};

const nowMs=Date.now(),nowIso=new Date(nowMs).toISOString();
const stateVar=await read(IDS.eventState);
const eventState=parse(stateVar?.value)||{};
const oldVar=await read(IDS.context);
const oldCtx=parse(oldVar?.value)||{};
const oldPrices=Array.isArray(oldCtx.priceSeries)?oldCtx.priceSeries.map(Number).filter(Number.isFinite):[];

const buffer=await read(IDS.buffer);
const raw=parse(buffer?.value);
const source=Array.isArray(raw)?raw:[];
const prices=[];
for(const v of source){
  const n=Number(v);
  if(!Number.isFinite(n)||n<=-2||n>=5) break;
  prices.push(n);
}

if(prices.length<4){
  await write(IDS.eventState,JSON.stringify({
    ...eventState,
    cooldownUntil:new Date(nowMs+COOLDOWN_MS).toISOString(),
    lastResult:'DEGRADED',
    lastReason:'LT_4_CONTIGUOUS_SLOTS'
  }));
  return false;
}

const oldSlots=Number(oldCtx.slots)||oldPrices.length||0;
const oldHorizon=Number(oldCtx.horizonHours)||oldSlots*0.25;
const newSlots=prices.length,newHorizon=newSlots*0.25;
const overlap=Math.min(oldPrices.length,prices.length);
let priceChanged=false;
for(let i=0;i<overlap;i++){
  if(Math.abs(Number(oldPrices[i])-prices[i])>EPS){priceChanged=true;break;}
}
const changed=newSlots>oldSlots||newHorizon>oldHorizon+EPS||priceChanged;

if(!changed){
  await write(IDS.eventState,JSON.stringify({
    ...eventState,
    cooldownUntil:new Date(nowMs+COOLDOWN_MS).toISOString(),
    lastResult:'UNCHANGED',
    lastReason:'NO_SEMANTIC_PRICE_CHANGE'
  }));
  return false;
}

const horizon=newHorizon>=12?'FULL':newHorizon>=6?'INTRADAY':'DIAGNOSTIC';
const ctx={
  ...oldCtx,
  schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.4',
  contractType:'DYNAMIC',
  source:'PBTH_PRICES_JSON_TARGETED_EVENT',
  quality:'GOOD',
  updatedAt:nowIso,
  importPriceNow:prices[0],
  negativeNow:prices[0]<0,
  horizon,
  horizonHours:newHorizon,
  slotMinutes:15,
  slots:newSlots,
  priceSeries:prices,
  guards:{
    ...(oldCtx.guards||{}),
    targetedLogicReads:true,
    broadLogicEnumeration:false,
    broadDeviceEnumeration:false,
    pbthActionCardOnly:true,
    noActuatorWrites:true,
    eventDrivenShortHorizonRefresh:true,
    eventRefreshThresholdHours:12,
    noChangeCooldownMinutes:60
  }
};

await write(IDS.mirror,'DYNAMIC');
await write(IDS.context,JSON.stringify(ctx));
await write(IDS.source,ctx.source);
await write(IDS.quality,'GOOD');
await write(IDS.horizon,horizon);
await write(IDS.updatedAt,nowIso);
await write(IDS.eventState,JSON.stringify({
  ...eventState,
  cooldownUntil:null,
  lastResult:'UPDATED',
  lastReason:'SEMANTIC_PRICE_CHANGE'
}));
return true;
```

## Important compatibility note

The current v0.9 published context shown in the repository does not include `priceSeries`. For robust semantic value comparison, v0.10 should add `priceSeries: prices` to the canonical context on both the regular scheduled path and the event path. This is a context-schema extension only; existing consumers may ignore the extra field.

Until the scheduled v0.9/v0.10 path publishes `priceSeries`, the event processor still detects a useful horizon extension by slot/horizon growth, but exact overlapping price-value comparison is not fully available from the context alone.

## Controlled deployment sequence

1. Provision `EM2_ContractPrice_EventRefresh_State` once and record its Logic ID.
2. Add `priceSeries: prices` to the scheduled adapter output while keeping the existing 15-minute schedule unchanged.
3. Add the PBTH **New prices received for period** event branch disabled/SHADOW.
4. Event branch: eligibility script -> only on `true` -> PBTH `prices_json(next_hours)` -> write token to existing buffer -> post-fetch semantic processor.
5. Validate `horizon >=12h` produces zero PBTH action calls.
6. Validate `<12h` produces one and only one PBTH action call per admitted event.
7. Validate unchanged result starts 60-minute cooldown and produces no Planner fan-out.
8. Validate changed/extended result updates price context once and permits normal Planner recalculation.
9. Keep the scheduled 15-minute route as rollback/fallback throughout validation.

## Load-budget invariant

- no `Homey.logic.getVariables()`;
- no `Homey.devices.getDevices()`;
- no device/actuator writes;
- one PBTH action maximum per admitted event;
- zero PBTH action calls when horizon is already >=12h;
- maximum one unsuccessful extra attempt per 60 minutes;
- no direct Planner -> PBTH dependency;
- stop deployment/testing immediately on Homey HTTP 429.

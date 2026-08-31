# EM v2 | 30 Context | Contract Price Adapter v0.10 EVENT REFRESH CANDIDATE

Status: **GITHUB IMPLEMENTATION READY / EVENT BRANCH NOT YET DEPLOYED**

Live runtime baseline (verified 2026-08-31): `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`, flow ID `69648157-892b-49d2-bc4d-e61a1a4d78ab`.

The live scheduled/manual v0.10 path already publishes `priceSeries: prices`; that additive extension has been validated through Adapter -> Planner -> Publisher. The only remaining functional delta is the PBTH event-refresh branch.

## Objective

Extend the existing low-load FIXED+DYNAMIC price adapter with an event-driven PBTH refresh only while the currently published dynamic-price horizon is below 12 hours. Planner never calls PBTH directly.

## PBTH trigger contract — resolved outside Homey

Upstream PBTH source `gruijter/com.gruijter.powerhour`, `.homeycompose/flow/triggers/new_prices.json`, defines:

- base trigger card ID: `new_prices`
- title: `New prices received`
- formatted title: `New prices received for [[period]]`
- device filter: `driver_id=dap|dap15|dapg`
- period values: `this_day`, `tomorrow`, `next_hours`
- tokens: `prices` and `provider`

For our configured Day-Ahead 15m E Prices device `d28cdd44-ab8c-4f4c-8ea7-279f444ecd81`, the intended event branch uses `period=next_hours`. The expected device-scoped Homey card form is `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:new_prices`; verify that exact runtime representation once at deployment, but do not perform further broad card discovery.

The existing action remains `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`, `period=next_hours`.

Important PBTH behavior: `New prices received` is only an opportunity signal, not proof that the horizon improved. PBTH forum evidence confirms that a new-prices event can also occur around midnight as the next calendar period starts. Therefore the semantic comparison and cooldown remain mandatory; never fan out merely because the trigger fired.

## Runtime topology

```text
existing scheduled 15-minute live v0.10 path --------------------+
                                                                  |
PBTH new_prices(period=next_hours)                                |
        |                                                         |
        v                                                         |
EVENT ELIGIBILITY GATE                                            |
        +-- contract != DYNAMIC -----------------> STOP            |
        +-- horizonHours >= 12 ------------------> STOP            |
        +-- cooldown active ---------------------> STOP            |
        |                                                         |
        v                                                         |
PBTH prices_json(next_hours) exactly once                          |
        |                                                         |
        v                                                         |
TEMP_PBTH_JSON_BUFFER                                              |
        |                                                         |
        v                                                         |
EVENT POST-FETCH PROCESSOR                                        |
        +-- degraded/unchanged --> retain prior context; 60m cd    |
        +-- changed/extended ----> publish context; clear cd ------+
                                    normal semantic downstream chain
                                    -> Planner
```

## Admission and semantic rules

Admit only when:

```text
contractType == DYNAMIC
AND current horizonHours < 12
AND no-change cooldown is not active
```

A returned series is semantically useful when slot count/horizon increases or an overlapping price changes materially. Identical/degraded data must not republish canonical context and must not fan out to Planner.

## Required event-state variable

Text Logic variable: `EM2_ContractPrice_EventRefresh_State`

Initial value:

```json
{"schema":"EM2_PRICE_EVENT_REFRESH_STATE_V0.1","lastAttemptAt":null,"cooldownUntil":null,"lastResult":"NEVER","lastReason":null}
```

Allowed results: `NEVER`, `ATTEMPT_ADMITTED`, `SKIPPED_FIXED`, `SKIPPED_HORIZON_OK`, `SKIPPED_COOLDOWN`, `DEGRADED`, `UNCHANGED`, `UPDATED`.

The exact Logic ID is the only remaining unavoidable state identifier to provision/capture in Homey. Capture it by exact-name targeted lookup only; never enumerate Logic variables broadly.

## Stable IDs

```text
EMS_ContractType                  8d346495-f183-4072-86d0-c4bc9da94e2e
EM2_Contract_Type                 211e5846-aada-4607-8d52-01b2ef578866
TEMP_PBTH_JSON_BUFFER             29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b
EM2_ContractPrice_Context         93e41221-6b4d-4f5f-83dc-997c9620f758
EM2_ContractPrice_Source          3e5a182d-2479-479a-bb58-42a27f4a4e23
EM2_ContractPrice_Quality         abedc6f4-cfee-4496-9b3c-418f1f3ad2bc
EM2_ContractPrice_Horizon         587ea957-f9e9-44c7-b975-3bed53bd9ab8
EM2_ContractPrice_UpdatedAt       77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb
```

## Eligibility HomeyScript

```js
const IDS={canonical:'8d346495-f183-4072-86d0-c4bc9da94e2e',context:'93e41221-6b4d-4f5f-83dc-997c9620f758',eventState:'__CAPTURE_ONCE_AFTER_PROVISIONING__'};
const read=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};
const nowMs=Date.now(),nowIso=new Date(nowMs).toISOString();
const canonical=await read(IDS.canonical);
const contract=String(canonical?.value||'FIXED').toUpperCase();
const stateVar=await read(IDS.eventState);
const state=parse(stateVar?.value)||{schema:'EM2_PRICE_EVENT_REFRESH_STATE_V0.1',lastAttemptAt:null,cooldownUntil:null,lastResult:'NEVER',lastReason:null};
async function stop(result,reason){await write(IDS.eventState,JSON.stringify({...state,lastResult:result,lastReason:reason}));return false;}
if(contract!=='DYNAMIC') return await stop('SKIPPED_FIXED','CONTRACT_NOT_DYNAMIC');
const ctx=parse((await read(IDS.context))?.value)||{};
const h=Number(ctx.horizonHours);
if(Number.isFinite(h)&&h>=12) return await stop('SKIPPED_HORIZON_OK','HORIZON_GTE_12H');
const cd=Date.parse(String(state.cooldownUntil||''));
if(Number.isFinite(cd)&&nowMs<cd) return await stop('SKIPPED_COOLDOWN','NO_CHANGE_COOLDOWN');
await write(IDS.eventState,JSON.stringify({...state,lastAttemptAt:nowIso,lastResult:'ATTEMPT_ADMITTED',lastReason:'HORIZON_LT_12H'}));
return true;
```

## Post-fetch HomeyScript

```js
const IDS={mirror:'211e5846-aada-4607-8d52-01b2ef578866',buffer:'29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',context:'93e41221-6b4d-4f5f-83dc-997c9620f758',source:'3e5a182d-2479-479a-bb58-42a27f4a4e23',quality:'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',horizon:'587ea957-f9e9-44c7-b975-3bed53bd9ab8',updatedAt:'77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb',eventState:'__CAPTURE_ONCE_AFTER_PROVISIONING__'};
const COOLDOWN_MS=3600000,EPS=1e-9;
const read=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};
const nowMs=Date.now(),nowIso=new Date(nowMs).toISOString();
const state=parse((await read(IDS.eventState))?.value)||{};
const oldCtx=parse((await read(IDS.context))?.value)||{};
const oldPrices=Array.isArray(oldCtx.priceSeries)?oldCtx.priceSeries.map(Number).filter(Number.isFinite):[];
const raw=parse((await read(IDS.buffer))?.value); const prices=[];
for(const v of Array.isArray(raw)?raw:[]){const n=Number(v);if(!Number.isFinite(n)||n<=-2||n>=5)break;prices.push(n);}
if(prices.length<4){await write(IDS.eventState,JSON.stringify({...state,cooldownUntil:new Date(nowMs+COOLDOWN_MS).toISOString(),lastResult:'DEGRADED',lastReason:'LT_4_CONTIGUOUS_SLOTS'}));return false;}
const oldSlots=Number(oldCtx.slots)||oldPrices.length||0,oldH=Number(oldCtx.horizonHours)||oldSlots*.25,newSlots=prices.length,newH=newSlots*.25;
let priceChanged=false;for(let i=0;i<Math.min(oldPrices.length,prices.length);i++){if(Math.abs(oldPrices[i]-prices[i])>EPS){priceChanged=true;break;}}
const changed=newSlots>oldSlots||newH>oldH+EPS||priceChanged;
if(!changed){await write(IDS.eventState,JSON.stringify({...state,cooldownUntil:new Date(nowMs+COOLDOWN_MS).toISOString(),lastResult:'UNCHANGED',lastReason:'NO_SEMANTIC_PRICE_CHANGE'}));return false;}
const horizon=newH>=12?'FULL':newH>=6?'INTRADAY':'DIAGNOSTIC';
const ctx={...oldCtx,schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.4',contractType:'DYNAMIC',source:'PBTH_PRICES_JSON_TARGETED_EVENT',quality:'GOOD',updatedAt:nowIso,importPriceNow:prices[0],negativeNow:prices[0]<0,horizon,horizonHours:newH,slotMinutes:15,slots:newSlots,priceSeries:prices,guards:{...(oldCtx.guards||{}),targetedLogicReads:true,broadLogicEnumeration:false,broadDeviceEnumeration:false,pbthActionCardOnly:true,noActuatorWrites:true,eventDrivenShortHorizonRefresh:true,eventRefreshThresholdHours:12,noChangeCooldownMinutes:60}};
await write(IDS.mirror,'DYNAMIC');await write(IDS.context,JSON.stringify(ctx));await write(IDS.source,ctx.source);await write(IDS.quality,'GOOD');await write(IDS.horizon,horizon);await write(IDS.updatedAt,nowIso);await write(IDS.eventState,JSON.stringify({...state,cooldownUntil:null,lastResult:'UPDATED',lastReason:'SEMANTIC_PRICE_CHANGE'}));return true;
```

## Controlled deployment sequence

1. Provision/capture only `EM2_ContractPrice_EventRefresh_State`.
2. Substitute the captured ID in both scripts and commit it to GitHub.
3. Verify the device-scoped `new_prices` runtime card representation once, only if required by the mutation API.
4. Read production flow once; make one atomic patch adding only the event branch.
5. Keep scheduled v0.10 route and validated `priceSeries` unchanged.
6. Validate zero calls when FIXED / horizon>=12h / cooldown; max one call otherwise; semantic update fans out once.
7. Stop immediately on 429; no same-round retry.

## Load-budget invariant

No `getVariables()`, no `getDevices()`, no repeated card discovery, no actuator/device writes, maximum one PBTH action per admitted event, scheduled 15-minute fallback retained.

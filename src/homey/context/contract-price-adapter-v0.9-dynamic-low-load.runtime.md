# EM v2 | 30 Context | Contract Price Adapter v0.9 DYNAMIC LOW-LOAD

- Homey flow ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Type: Advanced Flow
- Runtime state at promotion: `enabled=true`, `broken=false`, `triggerable=true`
- Trigger: every 15 minutes + manual start
- Supersedes for DYNAMIC operation: `Contract Price Adapter v0.8` (kept off as rollback baseline)
- Safety: context-only; no actuator writes

## Promotion evidence

The v0.9 probe was validated end-to-end through Core and Planner v0.4.8. The published Planner snapshot reported `quality=GOOD`, `fresh=true`, `usable=true`, and selected warm-water grid slots with `warmWaterReason=GRID_CHEAPEST_USABLE`.

## Low-load architecture

1. PBTH action card `prices_json(next_hours)` reads the dynamic import-price horizon.
2. The returned price token is stored in `TEMP_PBTH_JSON_BUFFER`.
3. A HomeyScript uses targeted `Homey.logic.getVariable({id})` / `updateVariable({id,...})` calls only.
4. No `Homey.logic.getVariables()` and no `Homey.devices.getDevices()` are used.
5. No device or actuator write is performed.

## Runtime cards

- Schedule trigger: `homey:manager:cron:every_nth`, `n=15`, `type=minute`.
- Manual start retained for controlled validation.
- PBTH action: `homey:device:d28cdd44-ab8c-4f4c-8ea7-279f444ecd81:prices_json`, period `next_hours`.
- Buffer variable: `TEMP_PBTH_JSON_BUFFER` (`29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b`).

## Targeted Logic variable IDs

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EM2_Contract_Type`: `211e5846-aada-4607-8d52-01b2ef578866`
- `EM2_ContractPrice_Context`: `93e41221-6b4d-4f5f-83dc-997c9620f758`
- `EM2_ContractPrice_Source`: `3e5a182d-2479-479a-bb58-42a27f4a4e23`
- `EM2_ContractPrice_Quality`: `abedc6f4-cfee-4496-9b3c-418f1f3ad2bc`
- `EM2_ContractPrice_Horizon`: `587ea957-f9e9-44c7-b975-3bed53bd9ab8`
- `EM2_ContractPrice_UpdatedAt`: `77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb`

## Runtime HomeyScript

```js
// Contract Price Adapter v0.9 DYNAMIC LOW-LOAD
// Scheduled every 15 minutes + manual start. No getVariables(), no getDevices(), no actuator writes.
const IDS={canonical:'8d346495-f183-4072-86d0-c4bc9da94e2e',mirror:'211e5846-aada-4607-8d52-01b2ef578866',buffer:'29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',context:'93e41221-6b4d-4f5f-83dc-997c9620f758',source:'3e5a182d-2479-479a-bb58-42a27f4a4e23',quality:'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',horizon:'587ea957-f9e9-44c7-b975-3bed53bd9ab8',updatedAt:'77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb'};
const STEP_MS=15*60000,read=async id=>Homey.logic.getVariable({id}),write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const canonical=await read(IDS.canonical),contract=String(canonical?.value||'FIXED').toUpperCase();
if(contract!=='DYNAMIC'){await write(IDS.mirror,'FIXED');return true;}
const buffer=await read(IDS.buffer);let arr=null;try{arr=JSON.parse(String(buffer?.value??'[]'));}catch{}const raw=Array.isArray(arr)?arr:[],prices=[];
for(const v of raw){const n=Number(v);if(!Number.isFinite(n)||n<=-2||n>=5)break;prices.push(n);}
const quality=prices.length>=4?'GOOD':'DEGRADED',horizonHours=prices.length*STEP_MS/3600000,horizon=horizonHours>=12?'FULL':horizonHours>=6?'INTRADAY':'DIAGNOSTIC',now=new Date().toISOString();
const ctx={schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.4',contractType:'DYNAMIC',source:'PBTH_PRICES_JSON_TARGETED',quality,updatedAt:now,importPriceNow:prices.length?prices[0]:null,exportPriceNow:null,selfUseGainNow:null,negativeNow:prices.length?prices[0]<0:false,horizon,horizonHours,slotMinutes:15,slots:prices.length,guards:{canonicalContractSource:'EMS_ContractType',targetedLogicReads:true,broadLogicEnumeration:false,broadDeviceEnumeration:false,pbthActionCardOnly:true,noActuatorWrites:true,productionScheduleMinutes:15,dynamicOnly:true}};
await write(IDS.mirror,'DYNAMIC');await write(IDS.context,JSON.stringify(ctx));await write(IDS.source,ctx.source);await write(IDS.quality,quality);await write(IDS.horizon,horizon);await write(IDS.updatedAt,now);return true;
```

## Scope note

This v0.9 runtime is intentionally DYNAMIC-only. If `EMS_ContractType` is not `DYNAMIC`, it does not invoke a broad fallback implementation; it only mirrors `FIXED` and exits. A future FIXED low-load path should be implemented separately with targeted configuration-variable reads rather than reintroducing the broad v0.8 enumerations.

## Proposed v0.10 — short-horizon event refresh

Design decision, not yet deployed.

Goal: refresh tomorrow's dynamic prices promptly when PBTH receives them, without increasing normal polling or creating repeated Homey load when no new prices are available.

### Trigger policy

- Keep the existing 15-minute scheduled refresh as the normal path.
- Only arm the additional PBTH event-driven refresh while `horizonHours < 12`.
- Use PBTH's native "new prices received" event as the preferred extra trigger.
- The event path may request `prices_json(next_hours)` once and run the same targeted normalization as the scheduled path.

### Semantic-change gate

After an event-driven refresh, compare the newly returned price series with the currently published context before propagating downstream.

A refresh is considered useful when at least one of these changes:
- the number of valid 15-minute slots increases;
- the effective horizon extends;
- one or more price values in the overlapping horizon changes materially.

Only a useful semantic change may update the canonical price context in a way that triggers a Planner recalculation. An identical result must not create downstream fan-out.

### Retry ceiling / cooldown

If the PBTH event produces no new price information:

- record the attempt timestamp;
- suppress further extra event-driven horizon refreshes for 60 minutes;
- allow at most one unsuccessful extra horizon refresh per hour;
- do not loop, retry immediately, or switch to broad polling;
- the regular 15-minute scheduled path remains unchanged.

A successful horizon extension or price-series change clears the no-change cooldown state.

### Load-budget invariant

The v0.10 event path must remain context-only and low-load:

- no `Homey.logic.getVariables()`;
- no `Homey.devices.getDevices()`;
- no actuator/device writes;
- targeted Logic reads/writes only;
- one PBTH `prices_json(next_hours)` call per admitted event refresh;
- no downstream Planner wake-up unless the normalized price context changes semantically;
- no more than one unsuccessful extra refresh per hour while the horizon remains below 12 hours.

This implements an event-driven refresh with an hourly retry ceiling and preserves the existing Homey API/load-budget architecture.
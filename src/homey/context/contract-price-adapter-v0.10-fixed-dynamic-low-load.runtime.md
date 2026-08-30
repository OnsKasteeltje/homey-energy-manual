# EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD

_Status: deployed to Homey and smoke-started successfully on 2026-08-30. Full two-direction FIXED ↔ DYNAMIC selector validation remains pending._

## Runtime state

- Homey flow ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Name: `EM v2 | 30 Context | Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`
- After deployment: `enabled=true`, `broken=false`, `triggerable=true`
- Manual flow start after deployment: successful
- Website command at validation time: `contractType=FIXED`, `hotWaterSource=BOILER`
- No physical device or actuator writes were introduced or executed by this adapter.

The smoke run was deliberately performed without changing the user's contract selector. Because the website command was FIXED, the intended exercised path was the FIXED branch. This does not substitute for a later explicit two-direction FIXED -> DYNAMIC -> FIXED selector test.

## Purpose

Close the v0.9 DYNAMIC -> FIXED stale-context gap while preserving the low-load architecture. `EMS_ContractType` remains authoritative. FIXED bypasses PBTH and publishes a fresh targeted FIXED context; DYNAMIC refreshes PBTH once and publishes the targeted DYNAMIC context.

## Flow topology

- Existing production flow ID retained: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Trigger: every 15 minutes + manual start.
- Targeted HomeyScript condition reads only `EMS_ContractType`.
- TRUE/DYNAMIC -> PBTH `prices_json(next_hours)` -> `TEMP_PBTH_JSON_BUFFER` -> common publisher.
- FALSE/FIXED/invalid -> common publisher directly; PBTH is not called.
- No `Homey.logic.getVariables()`; no `Homey.devices.getDevices()`; no actuator/device writes.

## Resolved FIXED Logic IDs

- `EM2_Fixed_Import_Normal`: `c64dce4d-32b0-476a-8559-d294e18b281a`
- `EM2_Fixed_Import_Offpeak`: `aba83710-b95a-428c-ab8f-e3f760bf82cc`
- `EM2_Fixed_Export`: `fce32aed-4e6d-44c4-ade8-c8f383eeb02e`
- `EM2_Fixed_Offpeak_Active`: `39c7aef4-ebeb-4c93-a564-d3e66b4fc0fa`
- `EM2_Contract_EndDate`: `8bd1bcaa-aaa1-47ca-9171-b10dfcd0946f`

## Branch condition

```js
const canonical=await Homey.logic.getVariable({id:'8d346495-f183-4072-86d0-c4bc9da94e2e'});
return String(canonical?.value||'FIXED').toUpperCase()==='DYNAMIC';
```

## Common targeted publisher

```js
// Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD
const IDS={canonical:'8d346495-f183-4072-86d0-c4bc9da94e2e',mirror:'211e5846-aada-4607-8d52-01b2ef578866',buffer:'29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',context:'93e41221-6b4d-4f5f-83dc-997c9620f758',source:'3e5a182d-2479-479a-bb58-42a27f4a4e23',quality:'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',horizon:'587ea957-f9e9-44c7-b975-3bed53bd9ab8',updatedAt:'77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb',fixedNormal:'c64dce4d-32b0-476a-8559-d294e18b281a',fixedOffpeak:'aba83710-b95a-428c-ab8f-e3f760bf82cc',fixedExport:'fce32aed-4e6d-44c4-ade8-c8f383eeb02e',fixedOffpeakActive:'39c7aef4-ebeb-4c93-a564-d3e66b4fc0fa',contractEndDate:'8bd1bcaa-aaa1-47ca-9171-b10dfcd0946f'};
const STEP_MS=15*60000,ECON=0.02,read=async id=>Homey.logic.getVariable({id}),write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}}),num=v=>Number.isFinite(Number(v))?Number(v):null,bool=v=>v===true||String(v).toLowerCase()==='true';
async function publish(ctx){await write(IDS.mirror,ctx.contractType);await write(IDS.context,JSON.stringify(ctx));await write(IDS.source,ctx.source);await write(IDS.quality,ctx.quality);await write(IDS.horizon,ctx.horizon);await write(IDS.updatedAt,ctx.updatedAt);}
let contract=String((await read(IDS.canonical))?.value||'FIXED').toUpperCase();if(!['FIXED','DYNAMIC'].includes(contract)){contract='FIXED';await write(IDS.canonical,'FIXED');}
if(contract==='FIXED'){
 const [normalV,offpeakV,exportV,offV,endV]=await Promise.all([read(IDS.fixedNormal),read(IDS.fixedOffpeak),read(IDS.fixedExport),read(IDS.fixedOffpeakActive),read(IDS.contractEndDate)]),normal=num(normalV?.value),offpeak=num(offpeakV?.value),exp=num(exportV?.value),off=bool(offV?.value),valid=[normal,offpeak,exp].every(v=>v!==null&&v>=0),imp=valid?(off?offpeak:normal):null,cheapNow=valid&&off&&(normal-offpeak)>=ECON,expensiveNow=valid&&!off&&(normal-offpeak)>=ECON,ts=new Date().toISOString();
 const ctx={schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.4',contractType:'FIXED',contractEndDate:String(endV?.value||''),source:'FIXED_CONFIG_TARGETED',quality:valid?'GOOD':'DEGRADED',updatedAt:ts,importPriceNow:imp,exportPriceNow:valid?exp:null,selfUseGainNow:valid?imp-exp:null,negativeNow:false,cheapNow,expensiveNow,cheapNext4h:cheapNow,expensiveNext4h:expensiveNow,statistics:{minNext4h:valid?Math.min(normal,offpeak):null,maxNext4h:valid?Math.max(normal,offpeak):null,avgNext4h:imp,p25AvailableHorizon:valid?Math.min(normal,offpeak):null,p75AvailableHorizon:valid?Math.max(normal,offpeak):null,economicThreshold:ECON},horizon:'STATIC',horizonHours:168,slotMinutes:60,slots:168,guards:{canonicalContractSource:'EMS_ContractType',targetedLogicReads:true,broadLogicEnumeration:false,broadDeviceEnumeration:false,fixedDoesNotDependOnPBTH:true,noActuatorWrites:true,productionScheduleMinutes:15}};
 await publish(ctx);return true;
}
const buffer=await read(IDS.buffer);let arr=null;try{arr=JSON.parse(String(buffer?.value??'[]'));}catch{}const raw=Array.isArray(arr)?arr:[],prices=[];for(const v of raw){const n=Number(v);if(!Number.isFinite(n)||n<=-2||n>=5)break;prices.push(n);}const quality=prices.length>=4?'GOOD':'DEGRADED',horizonHours=prices.length*STEP_MS/3600000,horizon=horizonHours>=12?'FULL':horizonHours>=6?'INTRADAY':'DIAGNOSTIC',ts=new Date().toISOString();
const ctx={schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.4',contractType:'DYNAMIC',source:'PBTH_PRICES_JSON_TARGETED',quality,updatedAt:ts,importPriceNow:prices.length?prices[0]:null,exportPriceNow:null,selfUseGainNow:null,negativeNow:prices.length?prices[0]<0:false,horizon,horizonHours,slotMinutes:15,slots:prices.length,guards:{canonicalContractSource:'EMS_ContractType',targetedLogicReads:true,broadLogicEnumeration:false,broadDeviceEnumeration:false,pbthActionCardOnly:true,noActuatorWrites:true,productionScheduleMinutes:15,dynamicOnly:true}};
await publish(ctx);return true;
```

## Safety / compatibility

The context schema remains `EM2_UNIFORM_PRICE_CONTEXT_V0.4` to avoid an unnecessary downstream schema change. Core v0.11b consumes `EM2_ContractPrice_Context` and the compatibility mirror `EM2_Contract_Type`; no physical-control ownership is introduced here.

## Validation status

- Deployment structure: **PASS** (`enabled=true`, `broken=false`, `triggerable=true`).
- Manual start: **PASS**.
- FIXED branch topology: **PASS by structure**; PBTH is unreachable from the FALSE/FIXED branch.
- DYNAMIC branch topology: **PASS by structure**; exactly one PBTH `prices_json(next_hours)` call precedes normalization.
- Explicit FIXED -> DYNAMIC -> FIXED selector smoke: **PENDING**; the operational selector was not changed for testing.
- Long-duration low-load/throttling soak: **PENDING**.

The existing proposed <12h PBTH event refresh remains a separate DYNAMIC-only follow-up and must never execute for FIXED.

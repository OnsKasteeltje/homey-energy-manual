# Contract Price Adapter v0.10 — FIXED + DYNAMIC low-load preparation

_Status: prepared in GitHub only; not deployed to Homey._

## Objective

Close the contract-switching gap in v0.9 so that `EMS_ContractType` remains the single authoritative contract selector and both `FIXED` and `DYNAMIC` produce a fresh, semantically consistent `EM2_ContractPrice_Context` without broad Logic/device enumeration.

The intended switching contract is:

`website selector -> ems-settings-command.json -> EMS Settings Sync -> EMS_ContractType -> Contract Price Adapter -> EM2_ContractPrice_Context -> Core/Planner`

## Current gap in v0.9

The current v0.9 production runtime is intentionally DYNAMIC-only. When `EMS_ContractType != DYNAMIC`, it mirrors `EM2_Contract_Type='FIXED'` and exits. This can leave the last DYNAMIC `EM2_ContractPrice_Context` in place after a DYNAMIC -> FIXED switch.

That state is not acceptable because contract type and price context can temporarily disagree.

## v0.10 invariant

For every admitted execution, the adapter must publish a contract-consistent context before returning:

- `EMS_ContractType=FIXED` -> publish a fresh FIXED context.
- `EMS_ContractType=DYNAMIC` -> publish a fresh DYNAMIC context from PBTH.
- invalid selector -> fail closed to FIXED and publish a FIXED context.
- no physical device/actuator writes.
- no `Homey.logic.getVariables()`.
- no `Homey.devices.getDevices()`.

## Targeted variable contract

Existing v0.9 IDs retained:

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EM2_Contract_Type`: `211e5846-aada-4607-8d52-01b2ef578866`
- `TEMP_PBTH_JSON_BUFFER`: `29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b`
- `EM2_ContractPrice_Context`: `93e41221-6b4d-4f5f-83dc-997c9620f758`
- `EM2_ContractPrice_Source`: `3e5a182d-2479-479a-bb58-42a27f4a4e23`
- `EM2_ContractPrice_Quality`: `abedc6f4-cfee-4496-9b3c-418f1f3ad2bc`
- `EM2_ContractPrice_Horizon`: `587ea957-f9e9-44c7-b975-3bed53bd9ab8`
- `EM2_ContractPrice_UpdatedAt`: `77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb`

The FIXED path additionally needs targeted IDs for the existing configuration variables:

- `EM2_Fixed_Import_Normal`
- `EM2_Fixed_Import_Offpeak`
- `EM2_Fixed_Export`
- `EM2_Fixed_Offpeak_Active`
- optional `EM2_Contract_EndDate`

Their live Homey IDs must be resolved once during deployment preparation; they are deliberately not guessed here.

## Prepared runtime logic

```js
// Contract Price Adapter v0.10 — FIXED + DYNAMIC TARGETED LOW-LOAD
// PREPARED ONLY: resolve FIXED variable IDs before Homey deployment.

const IDS={
  canonical:'8d346495-f183-4072-86d0-c4bc9da94e2e',
  mirror:'211e5846-aada-4607-8d52-01b2ef578866',
  buffer:'29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',
  context:'93e41221-6b4d-4f5f-83dc-997c9620f758',
  source:'3e5a182d-2479-479a-bb58-42a27f4a4e23',
  quality:'abedc6f4-cfee-4496-9b3c-418f1f3ad2bc',
  horizon:'587ea957-f9e9-44c7-b975-3bed53bd9ab8',
  updatedAt:'77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb',

  // Resolve once from Homey before deployment; do not use broad enumeration at runtime.
  fixedNormal:'__RESOLVE_EM2_Fixed_Import_Normal__',
  fixedOffpeak:'__RESOLVE_EM2_Fixed_Import_Offpeak__',
  fixedExport:'__RESOLVE_EM2_Fixed_Export__',
  fixedOffpeakActive:'__RESOLVE_EM2_Fixed_Offpeak_Active__',
  contractEndDate:'__RESOLVE_EM2_Contract_EndDate__'
};

const STEP_MS=15*60000;
const ECON=0.02;
const read=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const bool=v=>v===true||String(v).toLowerCase()==='true';
const now=()=>new Date().toISOString();

async function publish(ctx){
  await write(IDS.mirror,ctx.contractType);
  await write(IDS.context,JSON.stringify(ctx));
  await write(IDS.source,ctx.source);
  await write(IDS.quality,ctx.quality);
  await write(IDS.horizon,ctx.horizon);
  await write(IDS.updatedAt,ctx.updatedAt);
}

async function buildFixed(contractType){
  const [normalV,offpeakV,exportV,offActiveV,endV]=await Promise.all([
    read(IDS.fixedNormal),read(IDS.fixedOffpeak),read(IDS.fixedExport),
    read(IDS.fixedOffpeakActive),read(IDS.contractEndDate)
  ]);
  const normal=num(normalV?.value),offpeak=num(offpeakV?.value),exp=num(exportV?.value),off=bool(offActiveV?.value);
  const valid=[normal,offpeak,exp].every(v=>v!==null&&v>=0);
  const imp=valid?(off?offpeak:normal):null;
  const quality=valid?'GOOD':'DEGRADED';
  const cheapNow=valid&&off&&(normal-offpeak)>=ECON;
  const expensiveNow=valid&&!off&&(normal-offpeak)>=ECON;
  const ts=now();
  return {
    schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.5',
    contractType,
    contractEndDate:String(endV?.value||''),
    source:'FIXED_CONFIG_TARGETED',
    quality,
    updatedAt:ts,
    importPriceNow:imp,
    exportPriceNow:valid?exp:null,
    selfUseGainNow:valid?imp-exp:null,
    negativeNow:false,
    cheapNow,
    expensiveNow,
    cheapNext4h:cheapNow,
    expensiveNext4h:expensiveNow,
    statistics:{
      minNext4h:valid?Math.min(normal,offpeak):null,
      maxNext4h:valid?Math.max(normal,offpeak):null,
      avgNext4h:imp,
      p25AvailableHorizon:valid?Math.min(normal,offpeak):null,
      p75AvailableHorizon:valid?Math.max(normal,offpeak):null,
      economicThreshold:ECON
    },
    horizon:'STATIC',
    horizonHours:168,
    slotMinutes:60,
    slots:168,
    guards:{
      canonicalContractSource:'EMS_ContractType',
      targetedLogicReads:true,
      broadLogicEnumeration:false,
      broadDeviceEnumeration:false,
      fixedDoesNotDependOnPBTH:true,
      noActuatorWrites:true
    }
  };
}

async function buildDynamic(){
  const buffer=await read(IDS.buffer);
  let arr=null;try{arr=JSON.parse(String(buffer?.value??'[]'));}catch{}
  const raw=Array.isArray(arr)?arr:[],prices=[];
  for(const v of raw){const n=Number(v);if(!Number.isFinite(n)||n<=-2||n>=5)break;prices.push(n);}
  const quality=prices.length>=4?'GOOD':'DEGRADED';
  const horizonHours=prices.length*STEP_MS/3600000;
  const horizon=horizonHours>=12?'FULL':horizonHours>=6?'INTRADAY':'DIAGNOSTIC';
  const ts=now();
  return {
    schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.5',
    contractType:'DYNAMIC',
    source:'PBTH_PRICES_JSON_TARGETED',
    quality,
    updatedAt:ts,
    importPriceNow:prices.length?prices[0]:null,
    exportPriceNow:null,
    selfUseGainNow:null,
    negativeNow:prices.length?prices[0]<0:false,
    horizon,
    horizonHours,
    slotMinutes:15,
    slots:prices.length,
    guards:{
      canonicalContractSource:'EMS_ContractType',
      targetedLogicReads:true,
      broadLogicEnumeration:false,
      broadDeviceEnumeration:false,
      pbthActionCardOnly:true,
      noActuatorWrites:true,
      dynamicOnly:true
    }
  };
}

let contract=String((await read(IDS.canonical))?.value||'FIXED').toUpperCase();
if(!['FIXED','DYNAMIC'].includes(contract)){
  contract='FIXED';
  await write(IDS.canonical,'FIXED');
}

if(contract==='FIXED'){
  await publish(await buildFixed('FIXED'));
  return true;
}

// DYNAMIC branch assumes the preceding PBTH prices_json(next_hours) action
// has refreshed TEMP_PBTH_JSON_BUFFER, as in v0.9.
await publish(await buildDynamic());
return true;
```

## Required flow branching

The Advanced Flow should branch before invoking PBTH:

1. Read `EMS_ContractType` with a targeted HomeyScript condition.
2. If FIXED: do **not** call PBTH; run FIXED targeted normalizer/publisher.
3. If DYNAMIC: call PBTH `prices_json(next_hours)` once, then run DYNAMIC targeted normalizer/publisher.
4. Both branches end in the same semantic `EM2_ContractPrice_Context` output contract.

This is important: a FIXED contract must not wake PBTH merely because the flow runs every 15 minutes.

## Switch acceptance tests

These can be executed later with minimal Homey calls:

### A. FIXED -> DYNAMIC

Expected after one admitted run:

- `EMS_ContractType = DYNAMIC`
- `EM2_Contract_Type = DYNAMIC`
- context `contractType = DYNAMIC`
- context `source = PBTH_PRICES_JSON_TARGETED`
- context `horizon` is `DIAGNOSTIC|INTRADAY|FULL`
- no device/actuator write

### B. DYNAMIC -> FIXED

Expected after one admitted run:

- `EMS_ContractType = FIXED`
- `EM2_Contract_Type = FIXED`
- context `contractType = FIXED`
- context `source = FIXED_CONFIG_TARGETED`
- context `horizon = STATIC`
- stale DYNAMIC context is no longer present
- PBTH action is not called on the FIXED branch
- no device/actuator write

### C. Invalid selector

Expected:

- canonical selector fails closed to `FIXED`
- a FIXED context is immediately published
- no DYNAMIC/PBTH branch is entered

### D. Invalid FIXED tariff configuration

Expected:

- context remains `contractType=FIXED`
- `quality=DEGRADED`
- price fields become `null` where appropriate
- no fallback to DYNAMIC and no PBTH call

## Interaction with proposed short-horizon refresh

The previously proposed v0.10 PBTH event refresh for `horizonHours < 12` remains valid **only inside the DYNAMIC branch**. To avoid version ambiguity, implementation should combine both changes into one release candidate, preferably named `Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD`.

The event refresh must never fire or call PBTH while `EMS_ContractType=FIXED`.

## Deployment prerequisites

Before Homey deployment:

1. Resolve the five FIXED configuration Logic variable IDs with one controlled read/discovery step.
2. Confirm current fixed tariff values are still the intended production configuration.
3. Build/update the Advanced Flow branching so PBTH is DYNAMIC-only.
4. Keep v0.9 available as rollback until the two-direction switch smoke test passes.
5. Run only the minimal A/B switch validation; avoid broad Homey enumeration.

## Release decision

Prepared: **YES**.

Homey changed: **NO**.

Safe to deploy immediately without resolving FIXED variable IDs: **NO**.

# EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD

_Status: prepared in GitHub only. Homey deliberately not touched._

## Objective

Replace v0.3's broad 5-minute `Homey.logic.getVariables()` scan with deterministic targeted Logic reads, keep the existing GitHub `ems_settings` command contract, and reduce steady-state polling cadence from 5 to 15 minutes while retaining manual triggerability.

## Compatibility with live Core v0.11f

Validated 2026-08-30 against live `EM v2 | 00 Core Tick | v0.11f (Planner Tesla Headroom)`.

The Settings Sync interface is unchanged by v0.11f:

- `EMS_ContractType` remains the canonical website/config contract selector consumed by the Contract Price Adapter;
- `EMS_HotWaterSource` remains the canonical BOILER/CV selector;
- `WW_Boilermodus` remains the boolean warm-water mode consumed by Core (`state.hotWater.mode`);
- FIXED/DYNAMIC contract changes must never alter `EMS_HotWaterSource` or `WW_Boilermodus` unless the website command explicitly changes `hotWaterSource`;
- Core v0.11f's Planner Tesla projected-grid headroom change does not alter this contract;
- no Core, Planner, Power Intent, WW Adapter/Gate/Actuator or EV ownership is moved into Settings Sync.

## Low-load requirements

v0.4 must satisfy all of the following:

- no `Homey.logic.getVariables()`;
- no `Homey.devices.getDevices()`;
- no variable creation during normal runtime;
- targeted reads/writes only by stable Logic ID;
- 15-minute scheduled cadence + manual start;
- same `ems_settings` GitHub command schema;
- same canonical outputs: `EMS_ContractType`, `EMS_HotWaterSource`, `WW_Boilermodus`;
- `requestId` idempotency retained;
- status writes only when state meaningfully changes or an error state changes;
- no physical device/actuator writes.

## Stable IDs resolved from GitHub/runtime registries

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EMS_HotWaterSource`: `63006c48-7b92-452c-bbf5-6c02893b875c`
- `WW_Boilermodus`: `f9d885a4-fca2-4aea-a5a9-a5c05da90835`
- `GH_Status_Token`: `235cfe0f-5760-48b9-9349-a33be47d04d1`

Only two IDs still need one controlled Homey resolve before deployment:

- `EMS_Settings_LastRequestId`: `__RESOLVE_EMS_Settings_LastRequestId__`
- `EMS_Settings_Sync_Status`: `__RESOLVE_EMS_Settings_Sync_Status__`

Do not deploy while either placeholder remains.

## Prepared targeted runtime

```js
// EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD
const VERSION='EM2_EMS_SETTINGS_SYNC_V0.4';
const API='https://api.github.com/repos/OnsKasteeltje/homey-energy-manual/contents/docs/data/ems-settings-command.json?ref=main';
const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/ems-settings-command.json';

const IDS={
  contract:'8d346495-f183-4072-86d0-c4bc9da94e2e',
  source:'63006c48-7b92-452c-bbf5-6c02893b875c',
  boilerMode:'f9d885a4-fca2-4aea-a5a9-a5c05da90835',
  lastId:'__RESOLVE_EMS_Settings_LastRequestId__',
  status:'__RESOLVE_EMS_Settings_Sync_Status__',
  token:'235cfe0f-5760-48b9-9349-a33be47d04d1'
};

const read=async id=>Homey.logic.getVariable({id});
const write=async(id,value)=>Homey.logic.updateVariable({id,variable:{value}});
const norm=v=>String(v??'').trim();
const upper=v=>norm(v).toUpperCase();

async function setIfChanged(id,next,current){
  if(current!==next){await write(id,next);return true;}
  return false;
}

async function readCommand(token){
  if(token){
    try{
      const r=await fetch(API,{headers:{
        Authorization:`Bearer ${token}`,
        Accept:'application/vnd.github.raw+json',
        'X-GitHub-Api-Version':'2022-11-28',
        'User-Agent':'Homey-EMS-Settings-v0.4',
        'Cache-Control':'no-cache'
      }});
      if(r.ok)return {cmd:await r.json(),source:'GITHUB_API'};
    }catch(_){ }
  }
  try{
    const r=await fetch(RAW+'?ts='+Date.now(),{headers:{'Cache-Control':'no-cache'}});
    if(r.ok)return {cmd:await r.json(),source:'RAW_FALLBACK'};
  }catch(_){ }
  return null;
}

const [contractV,sourceV,boilerV,lastIdV,statusV,tokenV]=await Promise.all([
  read(IDS.contract),read(IDS.source),read(IDS.boilerMode),read(IDS.lastId),read(IDS.status),read(IDS.token)
]);

const fetched=await readCommand(norm(tokenV?.value));
async function setStatus(status,extra={}){
  const next=JSON.stringify({version:VERSION,status,...extra});
  if(String(statusV?.value||'')!==next)await write(IDS.status,next);
}

if(!fetched){await setStatus('FETCH_FAILED');return true;}
const cmd=fetched.cmd;
if(cmd?.schema!==1||cmd?.kind!=='ems_settings'){
  await setStatus('BLOCKED_SCHEMA',{schema:cmd?.schema??null,kind:cmd?.kind??null});
  return true;
}

const contract=upper(cmd.contractType);
const source=upper(cmd.hotWaterSource);
const requestId=norm(cmd.requestId);
if(!['FIXED','DYNAMIC'].includes(contract)||!['BOILER','CV'].includes(source)||!requestId){
  await setStatus('BLOCKED_VALUES',{contract,source,requestId});
  return true;
}

const desiredBoiler=source==='BOILER';
const currentContract=upper(contractV?.value);
const currentSource=upper(sourceV?.value);
const currentBoiler=Boolean(boilerV?.value);
const currentLastId=norm(lastIdV?.value);

const alreadyApplied=currentLastId===requestId&&currentContract===contract&&currentSource===source&&currentBoiler===desiredBoiler;
if(alreadyApplied)return true;

await setIfChanged(IDS.contract,contract,currentContract);
await setIfChanged(IDS.source,source,currentSource);
await setIfChanged(IDS.boilerMode,desiredBoiler,currentBoiler);
await setIfChanged(IDS.lastId,requestId,currentLastId);
await setStatus('SYNC_OK',{
  requestId,
  contractType:contract,
  hotWaterSource:source,
  boilerMode:desiredBoiler,
  requestedAt:cmd.requestedAt||null,
  sourceOfCommand:cmd.source||null,
  fetchSource:fetched.source
});
return true;
```

## Flow topology

- Trigger: every 15 minutes.
- Manual start retained.
- One HomeyScript action only.
- Six targeted Logic reads per admitted run; zero broad Logic/device discovery.
- Common already-applied path performs zero writes.
- No physical device writes.

## Acceptance test — DYNAMIC -> FIXED with WW isolation

1. Resolve only the two remaining Settings Sync Logic IDs in one controlled read-only step.
2. Assert zero placeholders remain; generate exact in-place Homey flow payload in GitHub before touching Homey again.
3. Deploy over flow `9193b3ae-1e3d-4b52-aa95-60aff099e68a`, initially disabled.
4. Capture pre-test values for `EMS_HotWaterSource` and `WW_Boilermodus` using targeted reads only.
5. Enable v0.4 and apply one controlled website DYNAMIC -> FIXED command while leaving `hotWaterSource=BOILER` unchanged.
6. Confirm `EMS_ContractType=FIXED` and requestId applied.
7. Confirm `EMS_HotWaterSource` and `WW_Boilermodus` are byte/boolean identical to their pre-test values: contract switching must cause no WW-mode transition in Core v0.11f.
8. Confirm Contract Price Adapter publishes `EM2_Contract_Type=FIXED`, `source=FIXED_CONFIG_TARGETED`, `horizon=STATIC`, with no PBTH call.
9. No `list_flows`, no broad Logic scan and no improvised probe fan-out during this acceptance run.
10. Leave v0.4 enabled only after no unexpected 429/throttling behavior is observed.

## Separate load-map item

Live Core v0.11f still contains one 5-minute `Homey.logic.getVariables()` broad read. That is a separate optimization item and must not be mixed into this Settings Sync change. v0.4 removes the second recurring broad scan that v0.3 would otherwise add.

## Release decision

Prepared outside Homey: **YES**.

Homey changed during this preparation: **NO**.

Remaining Homey discovery before exact payload: **2 targeted ID resolves only**.

Safe to deploy before those two IDs are resolved: **NO**.

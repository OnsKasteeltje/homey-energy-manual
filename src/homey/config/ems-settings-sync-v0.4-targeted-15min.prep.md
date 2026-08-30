# EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD

_Status: prepared in GitHub only. Homey deliberately not touched._

## Objective

Replace v0.3's broad 5-minute `Homey.logic.getVariables()` scan with deterministic targeted Logic reads, keep the existing GitHub command contract, and reduce steady-state polling cadence from 5 to 15 minutes while retaining manual triggerability for immediate application when explicitly requested.

## Why v0.4

The v0.3 baseline is functionally correct but not truly low-load: every admitted run starts with `Homey.logic.getVariables()` before its idempotency check. That means the no-op path still incurs a broad Logic enumeration every five minutes.

v0.4 must therefore satisfy all of the following:

- no `Homey.logic.getVariables()`;
- no `Homey.devices.getDevices()`;
- no variable creation during normal runtime;
- targeted reads only by stable Logic ID;
- 15-minute scheduled cadence + manual start;
- same `ems_settings` GitHub command schema;
- same canonical outputs: `EMS_ContractType`, `EMS_HotWaterSource`, `WW_Boilermodus`;
- same `requestId` idempotency semantics;
- status writes only when state meaningfully changes or an error state changes;
- no physical device/actuator writes.

## Known stable IDs

Already resolved and safe to hard-code:

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EMS_HotWaterSource`: `63006c48-7b92-452c-bbf5-6c02893b875c`

Still to resolve later with one controlled read-only Homey discovery step, after the current rest/throttling window:

- `WW_Boilermodus`: `__RESOLVE_WW_Boilermodus__`
- `EMS_Settings_LastRequestId`: `__RESOLVE_EMS_Settings_LastRequestId__`
- `EMS_Settings_Sync_Status`: `__RESOLVE_EMS_Settings_Sync_Status__`
- optional `GH_Status_Token`: `__RESOLVE_GH_Status_Token__`

Do not deploy while any placeholder remains.

## Prepared targeted runtime

```js
// EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD
const VERSION='EM2_EMS_SETTINGS_SYNC_V0.4';
const API='https://api.github.com/repos/OnsKasteeltje/homey-energy-manual/contents/docs/data/ems-settings-command.json?ref=main';
const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/ems-settings-command.json';

const IDS={
  contract:'8d346495-f183-4072-86d0-c4bc9da94e2e',
  source:'63006c48-7b92-452c-bbf5-6c02893b875c',
  boilerMode:'__RESOLVE_WW_Boilermodus__',
  lastId:'__RESOLVE_EMS_Settings_LastRequestId__',
  status:'__RESOLVE_EMS_Settings_Sync_Status__',
  token:'__RESOLVE_GH_Status_Token__'
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

const token=norm(tokenV?.value);
const fetched=await readCommand(token);

async function setStatus(status,extra={}){
  const next=JSON.stringify({version:VERSION,status,...extra});
  if(String(statusV?.value||'')!==next)await write(IDS.status,next);
}

if(!fetched){
  await setStatus('FETCH_FAILED');
  return true;
}

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
- No broad Logic/device discovery.
- No writes on the common already-applied path.
- No physical device writes.

## Acceptance tests after Homey rest window

1. Resolve the four remaining required IDs (and token ID if used) in one read-only discovery pass.
2. Populate this payload; assert zero placeholders remain.
3. Deploy in-place over flow `9193b3ae-1e3d-4b52-aa95-60aff099e68a` but keep it disabled until validation start.
4. Enable only for one controlled DYNAMIC -> FIXED test from the website.
5. Confirm canonical contract/source/boilerMode and requestId all update correctly.
6. Confirm `Contract Price Adapter v0.10` subsequently publishes `contractType=FIXED`, `source=FIXED_CONFIG_TARGETED`, `horizon=STATIC`, with no PBTH call.
7. Disable temporary validation artifacts and remove them after PASS.
8. Leave v0.4 enabled only after the validation proves no unexpected 429/throttling behavior.

## Release decision

Prepared outside Homey: **YES**.

Homey changed during this preparation: **NO**.

Safe to deploy before resolving the remaining Logic IDs: **NO**.

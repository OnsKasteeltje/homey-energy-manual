// EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD
const VERSION='EM2_EMS_SETTINGS_SYNC_V0.4';
const API='https://api.github.com/repos/OnsKasteeltje/homey-energy-manual/contents/docs/data/ems-settings-command.json?ref=main';
const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/ems-settings-command.json';

const IDS={
  contract:'8d346495-f183-4072-86d0-c4bc9da94e2e',
  source:'63006c48-7b92-452c-bbf5-6c02893b875c',
  boilerMode:'f9d885a4-fca2-4aea-a5a9-a5c05da90835',
  lastId:'e5562ce6-8ca9-4fff-af68-43fa183f0d23',
  status:'9f643c3c-0db9-4a8e-8b34-d0d0c49de220',
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
  read(IDS.contract),
  read(IDS.source),
  read(IDS.boilerMode),
  read(IDS.lastId),
  read(IDS.status),
  read(IDS.token)
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

const alreadyApplied=
  currentLastId===requestId&&
  currentContract===contract&&
  currentSource===source&&
  currentBoiler===desiredBoiler;

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

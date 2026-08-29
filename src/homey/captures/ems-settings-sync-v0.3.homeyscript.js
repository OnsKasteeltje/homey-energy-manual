// Runtime capture 2026-08-30
// Flow ID: 9193b3ae-1e3d-4b52-aa95-60aff099e68a
// Homey runtime enabled=false, broken=false; every 5 min + manual start.
const VERSION='EM2_EMS_SETTINGS_SYNC_V0.3';
const API='https://api.github.com/repos/OnsKasteeltje/homey-energy-manual/contents/docs/data/ems-settings-command.json?ref=main';
const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/ems-settings-command.json';
const TOKEN_VAR='GH_Status_Token';
const N={contract:'EMS_ContractType',source:'EMS_HotWaterSource',boilerMode:'WW_Boilermodus',lastId:'EMS_Settings_LastRequestId',status:'EMS_Settings_Sync_Status'};
const vars=await Homey.logic.getVariables();const byName=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
async function ensure(name,type,value){let v=byName[name];if(!v){v=await Homey.logic.createVariable({variable:{name,type,value}});byName[name]=v;}return v;}
async function put(name,type,value){const v=await ensure(name,type,value);if(v.value!==value){await Homey.logic.updateVariable({id:v.id,variable:{value}});v.value=value;return true;}return false;}
await ensure(N.contract,'string','FIXED');await ensure(N.source,'string','BOILER');await ensure(N.boilerMode,'boolean',true);await ensure(N.lastId,'string','');await ensure(N.status,'string','{}');
async function setStatus(status,extra={}){const stable={version:VERSION,status,...extra};await put(N.status,'string',JSON.stringify(stable));}
async function readCommand(){const token=String(byName[TOKEN_VAR]?.value||'').trim();if(token){try{const r=await fetch(API,{headers:{Authorization:`Bearer ${token}`,Accept:'application/vnd.github.raw+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Homey-EMS-Settings-v0.3','Cache-Control':'no-cache'}});if(r.ok)return {cmd:await r.json(),source:'GITHUB_API'};}catch(_){}}try{const r=await fetch(RAW+'?ts='+Date.now(),{headers:{'Cache-Control':'no-cache'}});if(r.ok)return {cmd:await r.json(),source:'RAW_FALLBACK'};}catch(_){}return null;}
const read=await readCommand();if(!read){await setStatus('FETCH_FAILED');return true;}const cmd=read.cmd;
if(cmd?.schema!==1||cmd?.kind!=='ems_settings'){await setStatus('BLOCKED_SCHEMA',{schema:cmd?.schema??null,kind:cmd?.kind??null});return true;}
const contract=String(cmd.contractType||'').toUpperCase(),source=String(cmd.hotWaterSource||'').toUpperCase(),requestId=String(cmd.requestId||'').trim();
if(!['FIXED','DYNAMIC'].includes(contract)||!['BOILER','CV'].includes(source)||!requestId){await setStatus('BLOCKED_VALUES',{contract,source,requestId});return true;}
const desiredBoiler=source==='BOILER';
const alreadyApplied=String(byName[N.lastId]?.value||'')===requestId&&String(byName[N.contract]?.value||'').toUpperCase()===contract&&String(byName[N.source]?.value||'').toUpperCase()===source&&Boolean(byName[N.boilerMode]?.value)===desiredBoiler;
if(alreadyApplied)return true;
await put(N.contract,'string',contract);await put(N.source,'string',source);await put(N.boilerMode,'boolean',desiredBoiler);await put(N.lastId,'string',requestId);
await setStatus('SYNC_OK',{requestId,contractType:contract,hotWaterSource:source,boilerMode:desiredBoiler,requestedAt:cmd.requestedAt||null,sourceOfCommand:cmd.source||null,fetchSource:read.source});
return true;

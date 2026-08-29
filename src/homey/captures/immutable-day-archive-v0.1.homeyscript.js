// Runtime capture 2026-08-30
// Flow ID: 322bcfe6-1ec4-46d4-a840-d13009d9c9c9
// Homey runtime enabled=false, broken=false; every 60 min + manual start.
const OWNER='OnsKasteeltje',REPO='homey-energy-manual',BRANCH='main';
const SERIES='docs/data/energy-day-series-7d.json',INDEX='docs/data/history/day-index-v1.json';
const RAW=`https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/${SERIES}`;
const TOKEN_VAR='GH_Status_Token',STATUS_VAR='EM2_BC_Day_Archive_Status_v1',TZ='Europe/Amsterdam',KEEP_DAYS=400;
const vars=await Homey.logic.getVariables();let byName=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
async function ensure(name,type,value){let v=byName[name];if(!v){v=await Homey.logic.createVariable({variable:{name,type,value}});byName[name]=v;}return v;}
async function putLogic(name,value){let v=await ensure(name,'string','');if(v.value!==value){await Homey.logic.updateVariable({id:v.id,variable:{value}});v.value=value;}}
const token=String(byName[TOKEN_VAR]?.value||'').trim();if(!token)throw new Error('BC archive: GH_Status_Token ontbreekt');
const H={Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Homey-BC-Day-Archive-v0.1','Cache-Control':'no-cache'};
const api=p=>`https://api.github.com/repos/${OWNER}/${REPO}/contents/${p}`,b64=s=>Buffer.from(s,'utf8').toString('base64');
async function read(path){const r=await fetch(`${api(path)}?ref=${BRANCH}&ts=${Date.now()}`,{headers:H});if(r.status===404)return null;if(!r.ok)throw new Error(`BC archive read ${path}: HTTP ${r.status}`);const j=await r.json();return {sha:j.sha,value:JSON.parse(Buffer.from(j.content,'base64').toString('utf8'))};}
async function readSeries(){const r=await fetch(`${RAW}?ts=${Date.now()}`,{headers:{'Cache-Control':'no-cache'}});if(!r.ok)throw new Error(`BC archive raw series HTTP ${r.status}`);return await r.json();}
async function put(path,value,message,sha=null){const body={message,branch:BRANCH,content:b64(JSON.stringify(value,null,2)+'\n')};if(sha)body.sha=sha;const r=await fetch(api(path),{method:'PUT',headers:{...H,'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error(`BC archive write ${path}: HTTP ${r.status} ${(await r.text()).slice(0,180)}`);return await r.json();}
function localDate(ms=Date.now()){return new Intl.DateTimeFormat('en-CA',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));}
const today=localDate(),series=await readSeries();if(!series||!Array.isArray(series.days))throw new Error('BC archive: energy-day-series-7d ontbreekt/ongeldig');
let idx=await read(INDEX);let index=idx?.value||{schema:'EMS_BC_DAY_ARCHIVE_INDEX_V1',retentionDays:KEEP_DAYS,immutable:true,days:[]};if(!Array.isArray(index.days))index.days=[];
const indexed=new Set(index.days.map(x=>String(x.date)));let changed=false,archived=0;
for(const day of series.days){const date=String(day?.date_local||day?.date||'');if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||date>=today||indexed.has(date))continue;const path=`docs/data/history/days/${date}.json`;const existing=await read(path);if(!existing){const doc={schema:'EMS_BC_IMMUTABLE_DAY_V1',date_local:date,immutable:true,archivedAt:new Date().toISOString(),sourceSchema:series.schema_version||series.schema||null,source:series.source||null,sample_interval_minutes:day.sample_interval_minutes||5,null_semantics:day.null_semantics||'NULL_IS_UNKNOWN_NEVER_ZERO',measurement_control_independent:day.measurement_control_independent!==false,...day};await put(path,doc,`Archive immutable EMS day ${date}`);archived++;}index.days.push({date,path,sampleCount:Array.isArray(day.samples)?day.samples.length:null,archivedAt:new Date().toISOString()});indexed.add(date);changed=true;}
index.days=index.days.sort((a,b)=>String(a.date).localeCompare(String(b.date))).slice(-KEEP_DAYS);index.updatedAt=new Date().toISOString();if(changed||!idx)await put(INDEX,index,'Update immutable EMS day archive index',idx?.sha||null);await putLogic(STATUS_VAR,JSON.stringify({status:'OK',at:new Date().toISOString(),indexedDays:index.days.length,archivedThisRun:archived,sourceDays:series.days.length,readOnly:true}));return true;

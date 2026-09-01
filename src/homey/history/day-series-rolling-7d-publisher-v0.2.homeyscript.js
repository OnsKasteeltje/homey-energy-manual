// PREP ONLY — NOT DEPLOYED
// Candidate flow: EM v2 | 72 History | Rolling 7d Archive v0.2 LOW-LOAD
// Purpose: drain completed local-day handoffs into docs/data/energy-day-series-7d.json.
// Schedule candidate: every 60 min + manual start.
// No device reads/writes. One Logic collection read per run; GitHub read/write only when queue is non-empty.

const OWNER='OnsKasteeltje',REPO='homey-energy-manual',BRANCH='main';
const OUT='docs/data/energy-day-series-7d.json';
const QUEUE_NAME='EM2_Day_Rollover_Queue_v1';
const QUEUE_SCHEMA='EM2_DAY_ROLLOVER_QUEUE_V1';
const TOKEN_NAME='GH_Status_Token';
const TZ='Europe/Amsterdam';
const KEEP_COMPLETED_DAYS=6;

const parse=v=>{try{return JSON.parse(String(v??'null'));}catch{return null;}};
const localDate=()=>new Intl.DateTimeFormat('en-CA',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const vars=await Homey.logic.getVariables();
const byName=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
const qv=byName[QUEUE_NAME];
if(!qv)return true;
let queue=parse(qv.value);
if(!queue||queue.schema!==QUEUE_SCHEMA||!Array.isArray(queue.days))throw new Error('ROLLING7D_QUEUE_INVALID');
queue.days=queue.days.filter(d=>/^\d{4}-\d{2}-\d{2}$/.test(String(d?.date_local||'')));
if(queue.days.length===0)return true;

const token=String(byName[TOKEN_NAME]?.value||'').trim();
if(!token)throw new Error('GH_Status_Token ontbreekt');

const api=`https://api.github.com/repos/${OWNER}/${REPO}/contents/${OUT}`;
const headers={Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Homey-EM2-Rolling7d-v0.2','Cache-Control':'no-cache'};
const cur=await fetch(`${api}?ref=${BRANCH}&ts=${Date.now()}`,{headers});
if(!cur.ok&&cur.status!==404)throw new Error(`ROLLING7D_GET_${cur.status}`);
let sha=null,remote={schema_version:'1.1',source:'EM2_DAY_ROLLOVER_ARCHIVE_V0.2',retention_completed_days:KEEP_COMPLETED_DAYS,generated_at:null,days:[]};
if(cur.ok){
  const j=await cur.json();sha=j.sha;
  const decoded=parse(Buffer.from(j.content||'','base64').toString('utf8'));
  if(decoded&&Array.isArray(decoded.days))remote=decoded;
}

const today=localDate();
const merged=new Map();
for(const d of remote.days||[]){
  const date=String(d?.date_local||d?.date||'');
  if(/^\d{4}-\d{2}-\d{2}$/.test(date)&&date<today)merged.set(date,d);
}
for(const d of queue.days){
  const date=String(d.date_local);
  if(date>=today)continue;
  merged.set(date,d);
}
const days=[...merged.entries()].sort((a,b)=>a[0].localeCompare(b[0])).slice(-KEEP_COMPLETED_DAYS).map(([,d])=>d);
const writtenDates=new Set(days.map(d=>String(d.date_local||d.date||'')));
const before=JSON.stringify(remote.days||[]);
const after=JSON.stringify(days);

if(before!==after||!sha){
  const out={...remote,schema_version:remote.schema_version||'1.1',source:'EM2_DAY_ROLLOVER_ARCHIVE_V0.2',retention_completed_days:KEEP_COMPLETED_DAYS,generated_at:new Date().toISOString(),days};
  const body={message:`chore: archive full-resolution canonical telemetry ${queue.days.map(d=>d.date_local).join(', ')}`,branch:BRANCH,content:Buffer.from(JSON.stringify(out,null,2)+'\n').toString('base64'),...(sha?{sha}:{})};
  const wr=await fetch(api,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!wr.ok)throw new Error(`ROLLING7D_PUT_${wr.status}: ${(await wr.text()).slice(0,180)}`);
}

// Clear only days that are now represented in the rolling file. Re-read queue to avoid erasing a handoff added concurrently.
const qNow=await Homey.logic.getVariable({id:qv.id});
let latest=parse(qNow?.value);
if(!latest||latest.schema!==QUEUE_SCHEMA||!Array.isArray(latest.days))throw new Error('ROLLING7D_QUEUE_REREAD_INVALID');
const remaining=latest.days.filter(d=>!writtenDates.has(String(d?.date_local||'')));
if(remaining.length!==latest.days.length){
  latest.days=remaining;
  latest.updated_at=new Date().toISOString();
  latest.last_archive_at=new Date().toISOString();
  latest.last_archived_dates=[...writtenDates].sort();
  await Homey.logic.updateVariable({id:qv.id,variable:{value:JSON.stringify(latest)}});
}
return true;

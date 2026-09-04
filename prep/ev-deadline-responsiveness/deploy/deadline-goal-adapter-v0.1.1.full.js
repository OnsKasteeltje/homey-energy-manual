// EM v2 | 10 Input | EV Deadline Goal Adapter v0.1.1 CANDIDATE
// PREP ONLY / NOT DEPLOYED
// Reads website deadline command and publishes validated Logic goals only. NO device writes.
// v0.1.1: semantic/idempotent final commit marker + infeasible-at-max-A observability.
const API='https://api.github.com/repos/OnsKasteeltje/homey-energy-manual/contents/docs/data/tesla-deadline-command.json?ref=main';
const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/tesla-deadline-command.json';
const TOKEN='GH_Status_Token',W_PER_A=690,TZ='Europe/Amsterdam',LATE_TOLERANCE_MS=60000;
const vars=await Homey.logic.getVariables(),by=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
const set=async(name,type,value)=>{const v=by[name];if(v){if(v.value!==value){await Homey.logic.updateVariable({id:v.id,variable:{value}});v.value=value;}return;}const nv=await Homey.logic.createVariable({variable:{name,type,value}});by[name]=nv;};
const markerValue=obj=>JSON.stringify({schema:'EM2_EV_GOAL_INPUT_V0.1',...obj});
const setMarker=async obj=>set('EM2_EV_Goal_Input_Status','string',markerValue(obj));
function zonedParts(ms){const ps=new Intl.DateTimeFormat('en-GB',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).formatToParts(new Date(ms)),o={};for(const p of ps)if(p.type!=='literal')o[p.type]=Number(p.value);return o;}
function parseLocal(s){s=String(s||'').trim();if(!s)return NaN;if(/[zZ]|[+-]\d\d:?\d\d$/.test(s))return Date.parse(s);const m=s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);if(!m)return NaN;const target=Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+(m[6]||0));let guess=target;for(let i=0;i<3;i++){const p=zonedParts(guess),shown=Date.UTC(p.year,p.month-1,p.day,p.hour%24,p.minute,p.second);guess+=target-shown;}return guess;}
async function read(){const token=String(by[TOKEN]?.value||'').trim();if(token){try{const r=await fetch(API,{headers:{Authorization:`Bearer ${token}`,Accept:'application/vnd.github.raw+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Homey-EV-Goal-Adapter','Cache-Control':'no-cache'}});if(r.ok)return await r.json();}catch{}}try{const r=await fetch(RAW+'?ts='+Date.now(),{headers:{'Cache-Control':'no-cache'}});if(r.ok)return await r.json();}catch{}return null;}
const cmd=await read(),now=Date.now();
if(!cmd){await setMarker({status:'FETCH_FAILED'});return false;}
const active=cmd.active===true,goal=Number(cmd.goalKWh),maxA=Math.round(Number(cmd.maxA)),deadline=String(cmd.deadline||''),dlMs=parseLocal(deadline),requestId=String(cmd.requestId||'');
if(!active){
  await set('EV Deadline actief','boolean',false);
  await set('EV Deadline tijd','string','');
  await set('EV Doel kWh','number',0);
  await set('EV Resterend kWh','number',0);
  await set('EV Latest start','string','');
  await set('EV Deadline status','string','NO_DEADLINE');
  await setMarker({status:'IDLE',requestId});
  return true;
}
const valid=requestId&&Number.isFinite(goal)&&goal>0&&Number.isFinite(maxA)&&maxA>=6&&maxA<=16&&Number.isFinite(dlMs)&&dlMs>now;
if(!valid){
  await set('EV Deadline actief','boolean',false);
  await set('EV Deadline status','string','DEADLINE_INPUT_REJECTED');
  await setMarker({status:'REJECTED',requestId,deadline,goalKWh:Number.isFinite(goal)?goal:null,maxA:Number.isFinite(maxA)?maxA:null});
  return false;
}
const neededMs=(goal/(maxA*W_PER_A/1000))*3600000,latestMs=dlMs-neededMs;
const latenessMs=now-latestMs,infeasibleAtMaxA=latenessMs>LATE_TOLERANCE_MS;
const deadlineStatus=now<latestMs?'DEADLINE_WAIT':infeasibleAtMaxA?'DEADLINE_INFEASIBLE_AT_MAX_A':'DEADLINE_CATCH_UP';
await set('EV Deadline actief','boolean',true);
await set('EV Deadline tijd','string',new Date(dlMs).toISOString());
await set('EV Doel kWh','number',goal);
await set('EV Resterend kWh','number',goal);
await set('EV Max laadstroom A','number',maxA);
await set('EV Latest start','string',new Date(latestMs).toISOString());
await set('EV Deadline status','string',deadlineStatus);
await setMarker({status:'OK',requestId,deadlineAt:new Date(dlMs).toISOString(),latestStartAt:new Date(latestMs).toISOString(),goalKWh:goal,maxA,neededMin:Math.round(neededMs/60000),deadlineStatus,infeasibleAtMaxA,deviceWrites:false});
return true;
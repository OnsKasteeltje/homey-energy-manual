// Homey runtime baseline capture — 2026-08-28
// Flow: EM v2 | 15 State | Warm Water Observer v0.2
// Flow ID: 957a85b5-a4ff-4fe2-bc6b-2e56e60387ea
// Captured state: enabled=false, broken=false, triggerable=true

// EM v2 | 15 State | Warm Water Observer v0.2
// Derived state only. Leest EM2_State; geen Homey.devices, geen fysieke writes.
// Integreert elapsed time op eigen run-tijd zodat State-deadbands geen looptijd verliezen.
const vars=await Homey.logic.getVariables(); const byName=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
const parse=v=>{try{return JSON.parse(String(v??'null'));}catch{return null;}};
const set=async(name,type,value)=>{const v=byName[name]; return v?Homey.logic.updateVariable({id:v.id,variable:{value}}):Homey.logic.createVariable({variable:{name,type,value}});};
const s=parse(byName.EM2_State?.value); if(!s||s.schema!=='ENERGY_STATE_V2.0') throw new Error('EM2_State ongeldig');
const now=Date.now(),sampleMs=Date.parse(s.sampledAt||''); if(!Number.isFinite(sampleMs)||now-sampleMs>15*60*1000) throw new Error('EM2_State stale >15 min');
const prev=parse(byName.EM2_WW_State?.value),legacy=parse(byName.WW_STATE_V13?.value);
const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Amsterdam',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()); const p=t=>parts.find(x=>x.type===t)?.value;
const today=`${p('year')}-${p('month')}-${p('day')}`,minuteOfDay=Number(p('hour'))*60+Number(p('minute'));
const hw=s.hotWater||{},boilerOn=hw.boilerOn===true,powerW=Number(hw.boilerPowerW)||0;
let st=(prev&&prev.schema==='EM2_WW_STATE_V0.2'&&prev.date===today)?{...prev}:null;
if(!st){
 const legacyDate=legacy?.date??legacy?.day??null,legacyToday=legacyDate===today;
 const legacyGoalDate=legacy?.goalReachedDate??legacy?.opTemperatuurDate??null;
 const legacyGoal=legacyGoalDate===today||legacy?.opTemperatuur===true||legacy?.goalReached===true;
 const legacyMin=Number(legacy?.boilerOnMin??legacy?.onMinutes??legacy?.boilerMinutes??0)||0;
 st={schema:'EM2_WW_STATE_V0.2',date:today,startedAt:new Date().toISOString(),updatedAt:new Date().toISOString(),sourceRevision:Number(s.revision),lastStateSampleAt:s.sampledAt,boilerOnMinToday:legacyToday?legacyMin:0,heatingConfirmMin:0,lowAfterHeatingMin:0,heatingConfirmed:false,goalReached:legacyToday&&legacyGoal,goalReachedAt:(legacyToday&&legacyGoal)?new Date().toISOString():null,bootstrappedFromLegacy:legacyToday,quality:legacyToday?'PARTIAL_LEGACY_BOOTSTRAP':'PARTIAL_FROM_START_TIME'};
}
const prevRunMs=Date.parse(st.updatedAt||''); let deltaMin=Number.isFinite(prevRunMs)?Math.max(0,Math.min(10,(now-prevRunMs)/60000)):0;
if(deltaMin>0&&boilerOn) st.boilerOnMinToday=(Number(st.boilerOnMinToday)||0)+deltaMin;
if(boilerOn&&powerW>1500){st.heatingConfirmMin=(Number(st.heatingConfirmMin)||0)+deltaMin;if(st.heatingConfirmMin>=15)st.heatingConfirmed=true;} else if(!st.heatingConfirmed) st.heatingConfirmMin=0;
if(st.heatingConfirmed&&boilerOn&&powerW<100){st.lowAfterHeatingMin=(Number(st.lowAfterHeatingMin)||0)+deltaMin;if(st.lowAfterHeatingMin>=10&&!st.goalReached){st.goalReached=true;st.goalReachedAt=new Date().toISOString();}} else if(powerW>=100||!boilerOn) st.lowAfterHeatingMin=0;
const remaining=Math.max(0,240-(Number(st.boilerOnMinToday)||0)); const catchup=minuteOfDay<1140&&!st.goalReached&&remaining>0&&(1140-minuteOfDay)<=remaining+5;
st={...st,schema:'EM2_WW_STATE_V0.2',date:today,updatedAt:new Date().toISOString(),sourceRevision:Number(s.revision),lastStateSampleAt:s.sampledAt,boilerOn,boilerPowerW:powerW,boilerOnMinToday:Math.round((Number(st.boilerOnMinToday)||0)*10)/10,remainingFallbackMin:Math.round(remaining*10)/10,minuteOfDay,catchupRequired:catchup,stateAgeSec:Math.round((now-sampleMs)/1000),policy:{primaryGoal:'OP_TEMPERATUUR',heatConfirmW:1500,heatConfirmMinutes:15,lowThresholdW:100,lowConfirmMinutes:10,fallbackMinutes:240,deadline:'19:00'}};
await set('EM2_WW_State','string',JSON.stringify(st)); return true;

// EM v2 | 81 Observability | EV Device Health v0.3 OBSERVABILITY-ONLY
// One targeted Easee device read + existing EM2_State read. No physical device writes.
const VERSION='EM2_EV_DEVICE_HEALTH_V0.3';
const CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const STATE_VAR_ID='8e1efbb0-7999-494c-9429-7d274afacd79';
const HEALTH_VAR_ID='db467a16-7d23-4033-af96-42a69b932a2b';
const STATE_FRESH_MS=7*60*1000, TELEMETRY_STALE_MS=5*60*1000;
const REQUIRED_MISMATCH_COUNT=2, MIN_GRID_IMPORT_W=4000, MIN_PHASE_A=5, MAX_PHASE_SPREAD_A=1;
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const ageMs=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const stateVar=await Homey.logic.getVariable({id:STATE_VAR_ID});
const healthVar=await Homey.logic.getVariable({id:HEALTH_VAR_ID});
const state=parse(stateVar?.value),prev=parse(healthVar?.value)||{};
let charger=null,deviceReadError=null;
try{charger=await Homey.devices.getDevice({id:CHARGER_ID});}catch(e){deviceReadError=String(e?.message||e);}
const caps=charger?.capabilitiesObj||{};
const cv=k=>caps?.[k]?.value;
const ct=k=>caps?.[k]?.lastUpdated||null;
const liveKeys=['measure_power','measure_current.offered','measure_current.p1','measure_current.p2','measure_current.p3','measure_voltage','meter_power','charger_status','evcharger_charging_state','target_charger_current'];
const liveTs=liveKeys.map(ct).map(x=>Date.parse(String(x||''))).filter(Number.isFinite);
const newestTelemetryMs=liveTs.length?Math.max(...liveTs):null;
const telemetryAgeMs=newestTelemetryMs===null?Infinity:Date.now()-newestTelemetryMs;
const deviceAvailable=charger?charger.available!==false:false;
const unavailableMessage=charger?.unavailableMessage??charger?.unavailableReason??null;
const stateAge=ageMs(state?.sampledAt),stateValid=!!state&&stateAge>=0&&stateAge<=STATE_FRESH_MS;
const grid=state?.grid||{},gridW=num(grid.powerW),l1A=num(grid.l1A),l2A=num(grid.l2A),l3A=num(grid.l3A);
const phaseSpread=stateValid&&l1A!==null&&l2A!==null&&l3A!==null?Math.max(l1A,l2A,l3A)-Math.min(l1A,l2A,l3A):null;
const evLike3Phase=stateValid&&gridW!==null&&phaseSpread!==null&&gridW>=MIN_GRID_IMPORT_W&&l1A>=MIN_PHASE_A&&l2A>=MIN_PHASE_A&&l3A>=MIN_PHASE_A&&phaseSpread<=MAX_PHASE_SPREAD_A;
const chargeState=String(cv('evcharger_charging_state')??state?.tesla?.chargeState??'unknown').trim().toLowerCase();
const measureW=num(cv('measure_power')),requestedA=num(cv('target_charger_current')),offeredA=num(cv('measure_current.offered'));
const chargerClaimsInactive=['plugged_out','disconnected','unplugged','idle'].includes(chargeState);
const chargerMeasuresIdle=(measureW===null||measureW<=100)&&(num(cv('measure_current.p1'))===null||Math.abs(num(cv('measure_current.p1')))<1)&&(num(cv('measure_current.p2'))===null||Math.abs(num(cv('measure_current.p2')))<1)&&(num(cv('measure_current.p3'))===null||Math.abs(num(cv('measure_current.p3')))<1);
const contradiction=evLike3Phase&&(chargerClaimsInactive||chargerMeasuresIdle);
let mismatchCount=Number.isInteger(prev?.persistence?.mismatchCount)?prev.persistence.mismatchCount:0;
if(contradiction)mismatchCount=Math.min(REQUIRED_MISMATCH_COUNT,mismatchCount+1);else mismatchCount=0;
let healthStatus='OK',reason='FRESH_TELEMETRY';
if(deviceReadError||!charger){healthStatus='UNAVAILABLE';reason='EASEE_DEVICE_READ_FAILED';}
else if(!deviceAvailable){healthStatus='UNAVAILABLE';reason='EASEE_DEVICE_UNAVAILABLE';}
else if(!Number.isFinite(telemetryAgeMs)||telemetryAgeMs<0||telemetryAgeMs>TELEMETRY_STALE_MS){healthStatus='STALE';reason='EASEE_TELEMETRY_STALE';}
else if(mismatchCount>=REQUIRED_MISMATCH_COUNT){healthStatus='MISMATCH';reason='P1_EV_LOAD_BUT_EASEE_INACTIVE';}
const evStatus=chargeState.toUpperCase();
const controlAvailability='OBSERVABILITY_ONLY';
const out={schema:VERSION,sampledAt:new Date().toISOString(),status:healthStatus,reason,evStatus,controlAvailability,controlSafe:null,warning:healthStatus==='OK'?null:'Easee observability is degraded; control authority remains with fresh P1/Power Intent/Gate.',sourceStateSampledAt:state?.sampledAt??null,sourceStateRevision:num(state?.revision),easee:{deviceAvailable,unavailableMessage,deviceReadError,chargeState,requestedA,offeredA,measureW,newestTelemetryAt:newestTelemetryMs===null?null:new Date(newestTelemetryMs).toISOString(),telemetryAgeSec:Number.isFinite(telemetryAgeMs)?Math.max(0,Math.round(telemetryAgeMs/1000)):null,staleAfterSec:TELEMETRY_STALE_MS/1000},p1:{gridW,l1A,l2A,l3A,phaseSpreadA:phaseSpread,evLike3Phase},persistence:{mismatchCount,requiredCount:REQUIRED_MISMATCH_COUNT},physicalWritePerformed:false};
const semantic=x=>JSON.stringify({status:x?.status,reason:x?.reason,evStatus:x?.evStatus,controlAvailability:x?.controlAvailability,easee:x?.easee,p1:x?.p1,persistence:x?.persistence});
const changed=semantic(prev)!==semantic(out);
if(changed)await Homey.logic.updateVariable({id:HEALTH_VAR_ID,variable:{value:JSON.stringify(out)}});
return true;

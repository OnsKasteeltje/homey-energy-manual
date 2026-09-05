// EM v2 | 60 Actuator | EV Power v0.2.4 MIN7 TARGETED-READ LIVE OWNERSHIP + EASEE SESSION CONTROL
// Gate-driven. Accept only 0A or 7..16A. Manual Start still normalizes LIVE=false.
// Advanced Flow session-control contract after this script succeeds:
//   1) LIVE must still be true.
//   2) target_charger_current must be > 6A.
//   3) plugged_in_paused -> Easee resumeCharging.
//   4) if Resume returns but charger remains paused after 10s -> evcharger_charging_start fallback.
//   5) plugged_in -> evcharger_charging_start.
//   6) plugged_in_charging -> no session command.
// Desired 0A remains dynamic-current zero; no explicit Stop/Pause is added.
const VERSION='EM2_EV_ACTUATOR_V0.2';
const CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119';
const FRESH_MS=120000;
const IDS={live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978',status:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',adapter:'f2118322-d59d-4aa8-b478-234effc3983c',gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',state:'8e1efbb0-7999-494c-9429-7d274afacd79'};
const [liveVar,statusVar,intentVar,adapterVar,gateVar,stateVar]=await Promise.all([Homey.logic.getVariable({id:IDS.live}),Homey.logic.getVariable({id:IDS.status}),Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.adapter}),Homey.logic.getVariable({id:IDS.gate}),Homey.logic.getVariable({id:IDS.state})]);
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const report=async(status,extra={})=>{const value=JSON.stringify({schema:VERSION,status,at:new Date().toISOString(),...extra});if(statusVar.value!==value){await Homey.logic.updateVariable({id:IDS.status,variable:{value}});statusVar.value=value;}};
const intent=parse(intentVar?.value),adapter=parse(adapterVar?.value),gate=parse(gateVar?.value),state=parse(stateVar?.value);
const r=num(intent?.sourceRevision),ar=num(adapter?.sourceRevision),sr=num(state?.revision),targetW=num(intent?.targets?.ev?.target_W),requestedA=num(adapter?.command?.requested_A);
const gateR=num(gate?.sourceRevision),gateIntentR=num(gate?.intentRevision),gateStateR=num(gate?.stateRevision),gateCoreR=num(gate?.coreRevision);
if(liveVar.value!==true){await report('SHADOW_NO_WRITE',{targetW,requestedA,revision:r,gateRevision:gateR,gateStatus:String(gate?.finalStatus||'UNKNOWN'),live:false,physicalWritePerformed:false});return true;}
let charger=null;
const getCharger=async()=>{if(charger)return charger;const devices=await Homey.devices.getDevices();charger=devices[CHARGER_ID];if(!charger)throw new Error('CHARGER_MISSING');return charger;};
const writeA=async a=>{const c=await getCharger();const current=num(c.capabilitiesObj?.target_charger_current?.value);if(current===a)return {write:false,previousA:current};await c.setCapabilityValue('target_charger_current',a);return {write:true,previousA:current};};
const failClosedLive=async(reason,extra={})=>{try{const w=await writeA(0);await report('LIVE_FAIL_CLOSED',{reason,targetA:0,physicalWritePerformed:w.write,previousA:w.previousA,live:true,...extra});return true;}catch(e){await report('LIVE_FAIL_CLOSED_WRITE_ERROR',{reason,error:String(e?.message||e),live:true,...extra});throw e;}};
try{
 const intentAge=age(intent?.generatedAt),adapterAge=age(adapter?.generatedAt),stateAge=age(state?.sampledAt),gateAge=age(gate?.updatedAt);
 const schemaOK=intent?.schema==='EM2_POWER_INTENT_V0.2'&&adapter?.schema==='EM2_EV_POWER_ADAPTER_V0.1'&&gate?.schema==='EM2_EV_ADAPTER_GATE_V0.2';
 const revOK=r!==null&&ar===r&&sr===r&&num(adapter?.stateRevision)===r;
 const gateRevOK=r!==null&&gateR===r&&gateIntentR===r&&gateStateR===r&&gateCoreR===r;
 const fresh=intentAge>=0&&intentAge<=FRESH_MS&&adapterAge>=0&&adapterAge<=FRESH_MS&&stateAge>=0&&stateAge<=FRESH_MS&&gateAge>=0&&gateAge<=FRESH_MS;
 const adapterSafe=adapter?.valid===true&&adapter?.deviceWrites===false&&adapter?.readOnly===true&&adapter?.controlMode==='SHADOW'&&adapter?.command?.capability==='setDynamicChargerCurrent'&&adapter?.command?.physicalWrite===false&&adapter?.safety?.failClosed===true&&adapter?.safety?.mappingRevision==='FLOOR_3P230_MIN7_FAIL_CLOSED'&&adapter?.safety?.neverIncreaseUpstreamPower===true;
 const numericOK=targetW!==null&&Number.isInteger(targetW)&&targetW>=0&&requestedA!==null&&Number.isInteger(requestedA)&&requestedA>=0&&requestedA<=16&&((requestedA===0)||(requestedA>=7));
 const powerOK=numericOK&&num(adapter?.electrical?.executable_W)===requestedA*690&&(targetW===0||requestedA===0||requestedA*690<=targetW||requestedA===num(adapter?.electrical?.max_A));
 if(!schemaOK)return await failClosedLive('SCHEMA_MISMATCH',{r,ar,sr,gateR});
 if(!revOK)return await failClosedLive('REVISION_MISMATCH',{r,ar,sr,gateR});
 if(!gateRevOK)return await failClosedLive('VALIDATION_GATE_REVISION_MISMATCH',{r,ar,sr,gateR,gateIntentR,gateStateR,gateCoreR});
 if(!fresh)return await failClosedLive('STALE_INPUT',{intentAgeSec:Math.round(intentAge/1000),adapterAgeSec:Math.round(adapterAge/1000),stateAgeSec:Math.round(stateAge/1000),gateAgeSec:Math.round(gateAge/1000),r});
 if(!adapterSafe||!numericOK||!powerOK)return await failClosedLive('ADAPTER_CONTRACT_INVALID',{targetW,requestedA,r});
 if(gate?.mapping!=='FLOOR_3P230_MIN7_FAIL_CLOSED')return await failClosedLive('VALIDATION_GATE_MAPPING_MISMATCH',{targetW,requestedA,r,gateR,gateMapping:String(gate?.mapping||'UNKNOWN')});
 if(gate?.finalStatus!=='PASS')return await failClosedLive('VALIDATION_GATE_NOT_PASS',{targetW,requestedA,r,gateR,gateStatus:String(gate?.finalStatus||'UNKNOWN')});
 const w=await writeA(requestedA);await report(w.write?(requestedA===0?'WRITE_ZERO_NORMALIZE':'WRITE_OK'):'NOOP_ALREADY_TARGET',{targetW,targetA:requestedA,previousA:w.previousA,revision:r,gateRevision:gateR,gateStatus:'PASS',live:true,physicalWritePerformed:w.write,ownership:requestedA===0?'NORMALIZE_AUTOSTART_TO_ZERO':'APPLY_POWER_INTENT',sessionControl:requestedA>=7?'FLOW_STATE_AWARE_START_RESUME':'NONE'});return true;
}catch(e){try{return await failClosedLive('RUNTIME_EXCEPTION',{error:String(e?.message||e),r,gateR});}catch(_){throw e;}}

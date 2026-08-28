# EM v2 | 60 Control | Warm Water Actuator v0.8 HYBRID

- Homey flow ID: `40d45aeb-174e-4a83-9a42-71ae46065cb4`
- Runtime state at capture: `enabled=false`, `broken=false`, `triggerable=true`
- Trigger: manual start only
- Capture date: 2026-08-28
- Status: exact runtime baseline captured; no runtime promotion performed

## Runtime HomeyScript

```js
// EM v2 | 60 Control | Warm Water Actuator v0.8 HYBRID CANDIDATE
// Disabled by default. Separate kill-switch defaults FALSE. No periodic trigger yet.
// v0.8: canonieke WW_Boilermodus guard; CV-selectie kan nooit BOILER_ON schrijven.
const VERSION='EM2_WW_ACTUATOR_V0.8';
const BOILER_ID='8238b270-21a2-4284-aa78-6b9b58d254ab';
const KILL='EM2_WW_Hybrid_Enabled',MODE='WW_Boilermodus';
const STATUS='EM2_WW_Actuator_Status';
const MAX_AGE_MS=10*60*1000;
const vars=await Homey.logic.getVariables();
const byName=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
const parse=v=>{try{return JSON.parse(String(v??'null'));}catch{return null;}};
const ensure=async(name,type,value)=>{let v=byName[name];if(!v){v=await Homey.logic.createVariable({variable:{name,type,value}});byName[name]=v;}return v;};
const put=async(name,type,value)=>{const v=await ensure(name,type,value);if(v.value!==value){await Homey.logic.updateVariable({id:v.id,variable:{value}});v.value=value;}};
const report=async(status,extra={})=>put(STATUS,'string',JSON.stringify({version:VERSION,status,at:new Date().toISOString(),...extra}));
const kill=await ensure(KILL,'boolean',false);const mode=await ensure(MODE,'boolean',true);
const state=parse(byName.EM2_State?.value),ww=parse(byName.EM2_WW_State?.value),ctl=parse(byName.EM2_Control_WW?.value);
if(!state||state.schema!=='ENERGY_STATE_V2.0'){await report('BLOCKED_STATE_SCHEMA',{schema:state?.schema??null});return true;}
if(!ww||ww.schema!=='EM2_WW_STATE_V0.8'){await report('BLOCKED_WW_SCHEMA',{schema:ww?.schema??null});return true;}
if(!ctl||ctl.schema!=='EM2_CONTROL_WW_V0.11'){await report('BLOCKED_CONTROL_SCHEMA',{schema:ctl?.schema??null});return true;}
const sr=Number(state.revision),wr=Number(ww.sourceRevision),cr=Number(ctl.sourceRevision);
if(!Number.isFinite(sr)||sr!==wr||sr!==cr){await report('BLOCKED_REVISION_MISMATCH',{stateRevision:sr,wwRevision:wr,controlRevision:cr});return true;}
const sampled=Date.parse(state.sampledAt||''),controlAt=Date.parse(ctl.generatedAt||'');
const now=Date.now(),stateAge=Number.isFinite(sampled)?now-sampled:Infinity,controlAge=Number.isFinite(controlAt)?now-controlAt:Infinity;
if(stateAge>MAX_AGE_MS||controlAge>MAX_AGE_MS){await report('BLOCKED_STALE',{stateAgeSec:Math.round(stateAge/1000),controlAgeSec:Math.round(controlAge/1000),revision:sr});return true;}
if(ctl?.guards?.stateFresh!==true||ctl?.guards?.revisionMatch!==true||ctl?.guards?.wwStateFresh!==true){await report('BLOCKED_CORE_GUARDS',{guards:ctl?.guards??null,revision:sr});return true;}
const action=String(ctl.action||'HOLD'),priority=String(ctl.priority||'MAY');
if(!['BOILER_ON','BOILER_OFF','HOLD'].includes(action)){await report('BLOCKED_ACTION',{action,priority,revision:sr});return true;}
if(action!=='HOLD'&&!['MUST','SHOULD'].includes(priority)){await report('BLOCKED_PRIORITY',{action,priority,revision:sr});return true;}
if(mode.value!==true&&action==='BOILER_ON'){await report('BLOCKED_SOURCE_CV',{action,priority,revision:sr,boilerMode:false,physicalWritePerformed:false});return true;}
if(kill.value!==true){await report('BLOCKED_KILL_SWITCH',{action,priority,revision:sr,boilerMode:mode.value===true,physicalWritePerformed:false});return true;}
if(action==='HOLD'){await report('HOLD',{priority,revision:sr,boilerMode:mode.value===true,physicalWritePerformed:false});return true;}
const devices=await Homey.devices.getDevices(),boiler=devices[BOILER_ID];
if(!boiler){await report('BLOCKED_BOILER_MISSING',{revision:sr});return true;}
const current=boiler.capabilitiesObj?.onoff?.value;
if(typeof current!=='boolean'){await report('BLOCKED_ONOFF_UNAVAILABLE',{revision:sr});return true;}
const target=action==='BOILER_ON';
if(current===target){await report('NOOP_ALREADY_TARGET',{action,target,current,priority,revision:sr,boilerMode:mode.value===true,physicalWritePerformed:false});return true;}
await boiler.setCapabilityValue('onoff',target);
await report('WRITE_OK',{action,target,previous:current,priority,revision:sr,boilerMode:mode.value===true,physicalWritePerformed:true});
return true;
```

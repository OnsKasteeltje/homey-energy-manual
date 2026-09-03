// EM v2 | 82 Observability | EV Telemetry Mismatch Guard v0.1 SHADOW
// HOMEY PREPARED — DISABLED / NOT RUN.
// Logic-only runtime. Reads the existing EM2_State document; performs no device reads and no physical writes.

const VERSION='EM2_EV_TELEMETRY_HEALTH_V0.1';
const STATE_VAR_ID='8e1efbb0-7999-494c-9429-7d274afacd79';
const HEALTH_VAR_ID='db467a16-7d23-4033-af96-42a69b932a2b';

const REQUIRED_COUNT=2;
const MIN_GRID_IMPORT_W=4000;
const MIN_PHASE_A=5;
const MAX_PHASE_SPREAD_A=2;
const STATE_FRESH_MS=7*60*1000; // allows one 5-minute Core interval plus margin

const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const ageMs=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};

const [stateVar,healthVar]=await Promise.all([
  Homey.logic.getVariable({id:STATE_VAR_ID}),
  Homey.logic.getVariable({id:HEALTH_VAR_ID})
]);

const state=parse(stateVar?.value);
const prev=parse(healthVar?.value)||{};
const grid=state?.grid||{};
const tesla=state?.tesla||{};

const gridW=num(grid.powerW);
const l1A=num(grid.l1A),l2A=num(grid.l2A),l3A=num(grid.l3A);
const teslaPowerW=num(tesla.powerW);
const teslaL1A=num(tesla.l1A),teslaL2A=num(tesla.l2A),teslaL3A=num(tesla.l3A);
const requestedA=num(tesla.requestedA);
const chargeState=String(tesla.chargeState??'unknown').trim().toLowerCase();
const meterKWh=num(tesla.meterKWh);
const stateAge=ageMs(state?.sampledAt);

const stateValid=state&&gridW!==null&&l1A!==null&&l2A!==null&&l3A!==null&&stateAge>=0&&stateAge<=STATE_FRESH_MS;
const phaseSpread=stateValid?Math.max(l1A,l2A,l3A)-Math.min(l1A,l2A,l3A):null;
const evLike3Phase=stateValid&&gridW>=MIN_GRID_IMPORT_W&&l1A>=MIN_PHASE_A&&l2A>=MIN_PHASE_A&&l3A>=MIN_PHASE_A&&phaseSpread<=MAX_PHASE_SPREAD_A;

// Contradiction is intentionally conservative: physical EV-like load plus charger-side evidence claiming no charge.
// target/requestedA == 0 is supporting evidence only and never proves physical stop.
const chargerClaimsInactive=chargeState==='plugged_out'||chargeState==='disconnected'||chargeState==='unplugged'||chargeState==='idle';
const chargerMeasuresIdle=(teslaPowerW!==null&&teslaPowerW<=100)&&
  (teslaL1A===null||Math.abs(teslaL1A)<1)&&
  (teslaL2A===null||Math.abs(teslaL2A)<1)&&
  (teslaL3A===null||Math.abs(teslaL3A)<1);
const contradiction=evLike3Phase&&(chargerClaimsInactive||chargerMeasuresIdle);

let mismatchCount=Number.isInteger(prev?.persistence?.mismatchCount)?prev.persistence.mismatchCount:0;
let consistentCount=Number.isInteger(prev?.persistence?.consistentCount)?prev.persistence.consistentCount:0;
let status='UNKNOWN',reason='INPUT_INVALID';

if(!stateValid){
  mismatchCount=0;consistentCount=0;
}else if(contradiction){
  mismatchCount=Math.min(REQUIRED_COUNT,mismatchCount+1);consistentCount=0;
  if(mismatchCount>=REQUIRED_COUNT){status='MISMATCH';reason='P1_EV_LOAD_BUT_EASEE_INACTIVE';}
  else {status='UNKNOWN';reason='P1_EV_LOAD_BUT_EASEE_INACTIVE_PENDING_CONFIRMATION';}
}else{
  mismatchCount=0;
  consistentCount=Math.min(REQUIRED_COUNT,consistentCount+1);
  const wasMismatch=prev?.status==='MISMATCH';
  if(wasMismatch&&consistentCount<REQUIRED_COUNT){status='UNKNOWN';reason='RECOVERY_PENDING_CONFIRMATION';}
  else {status='OK';reason=evLike3Phase?'EV_LOAD_TELEMETRY_NOT_CONTRADICTED':'NO_EV_LIKE_3PHASE_LOAD';}
}

const out={
  schema:VERSION,
  sampledAt:new Date().toISOString(),
  sourceStateSampledAt:state?.sampledAt??null,
  sourceStateRevision:num(state?.revision),
  status,
  reason,
  controlSafe:status==='OK',
  observabilityOnly:true,
  controlImpact:'NONE',
  p1:{gridW,l1A,l2A,l3A,phaseSpreadA:phaseSpread,evLike3Phase},
  easee:{chargeState,requestedA,measureW:teslaPowerW,l1A:teslaL1A,l2A:teslaL2A,l3A:teslaL3A,meterKWh,claimsInactive:chargerClaimsInactive,measuresIdle:chargerMeasuresIdle},
  persistence:{mismatchCount,consistentCount,requiredCount:REQUIRED_COUNT},
  thresholds:{minGridImportW:MIN_GRID_IMPORT_W,minPhaseA:MIN_PHASE_A,maxPhaseSpreadA:MAX_PHASE_SPREAD_A,stateFreshSec:STATE_FRESH_MS/1000},
  physicalWritePerformed:false
};

// Idempotency ignores timestamps and source revision; write only when semantic health changes.
const semantic=x=>JSON.stringify({status:x?.status,reason:x?.reason,controlSafe:x?.controlSafe,p1:x?.p1,easee:x?.easee,persistence:x?.persistence,thresholds:x?.thresholds});
if(semantic(prev)!==semantic(out)){
  await Homey.logic.updateVariable({id:HEALTH_VAR_ID,variable:{value:JSON.stringify(out)}});
}
return status!=='MISMATCH';

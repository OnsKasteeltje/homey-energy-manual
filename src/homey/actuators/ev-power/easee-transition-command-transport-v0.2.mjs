// Easee phase/transition safety transport v0.2
// Pure HTTP command adapter. No credential storage, no token refresh, no policy.
// Intended to be called only by the sole EV actuator.
//
// Official endpoints used:
// - POST /api/chargers/{serial}/commands/set_phase_mode
// - POST /api/sites/{siteId}/circuits/{circuitId}/dynamicCurrent
//
// The circuit cap is always symmetric A/A/A and therefore does not choose
// a physical phase. It is a temporary safety ceiling around resume, because
// Easee resume_charging resets the dynamic charger-current limit.

export const EASEE_COMMAND_SCHEMA='EM2_EASEE_TRANSITION_COMMAND_V0.2';

const tokenOk=v=>String(v||'').trim().length>0;

function baseResult({kind,transitionId,requestedAt,now,ok,httpStatus,reason,details={}}){
  return {
    schema:EASEE_COMMAND_SCHEMA,
    kind,
    transitionId:transitionId??null,
    requestedAt,
    completedAt:now().toISOString(),
    ok,
    httpStatus,
    reason,
    ...details,
    secretMaterialPersisted:false,
  };
}

async function post({fetchFn,url,body,accessToken,kind,transitionId,now}){
  const requestedAt=now().toISOString();
  try{
    const response=await fetchFn(url,{
      method:'POST',
      headers:{
        'Authorization':`Bearer ${String(accessToken).trim()}`,
        'Content-Type':'application/json',
        'Accept':'application/json, application/octet-stream'
      },
      body:JSON.stringify(body)
    });
    const ok=response?.ok===true;
    return baseResult({
      kind,transitionId,requestedAt,now,ok,
      httpStatus:Number(response?.status)||null,
      reason:ok?'ACCEPTED':`HTTP_${Number(response?.status)||'UNKNOWN'}`,
      details:{request:body}
    });
  }catch(err){
    return baseResult({
      kind,transitionId,requestedAt,now,ok:false,httpStatus:null,
      reason:`NETWORK_ERROR:${String(err?.message||err)}`,
      details:{request:body}
    });
  }
}

export function validatePhaseCommandInput({serialNumber,phaseMode,accessToken}){
  if(!String(serialNumber||'').trim())throw new Error('EASEE_SERIAL_MISSING');
  if(![1,3].includes(Number(phaseMode)))throw new Error('EASEE_PHASE_MODE_INVALID');
  if(!tokenOk(accessToken))throw new Error('EASEE_ACCESS_TOKEN_MISSING');
}

export async function sendEaseePhaseMode({
  fetchFn=fetch,
  serialNumber,
  phaseMode,
  accessToken,
  transitionId,
  now=()=>new Date(),
}){
  validatePhaseCommandInput({serialNumber,phaseMode,accessToken});
  return post({
    fetchFn,
    url:`https://api.easee.com/api/chargers/${encodeURIComponent(String(serialNumber).trim())}/commands/set_phase_mode`,
    body:{phaseMode:Number(phaseMode)},
    accessToken,
    kind:'SET_PHASE_MODE',
    transitionId,
    now,
  });
}

export function validateCircuitCapInput({siteId,circuitId,amps,minutes,accessToken}){
  if(!String(siteId||'').trim())throw new Error('EASEE_SITE_ID_MISSING');
  if(!String(circuitId||'').trim())throw new Error('EASEE_CIRCUIT_ID_MISSING');
  if(!Number.isInteger(Number(amps))||Number(amps)<6||Number(amps)>16)throw new Error('EASEE_CIRCUIT_CAP_AMPS_INVALID');
  if(!Number.isInteger(Number(minutes))||Number(minutes)<1||Number(minutes)>5)throw new Error('EASEE_CIRCUIT_CAP_TTL_INVALID');
  if(!tokenOk(accessToken))throw new Error('EASEE_ACCESS_TOKEN_MISSING');
}

export async function sendEaseeTransitionCircuitCap({
  fetchFn=fetch,
  siteId,
  circuitId,
  amps,
  minutes=1,
  accessToken,
  transitionId,
  now=()=>new Date(),
}){
  validateCircuitCapInput({siteId,circuitId,amps,minutes,accessToken});
  const a=Number(amps),ttl=Number(minutes);
  return post({
    fetchFn,
    url:`https://api.easee.com/api/sites/${encodeURIComponent(String(siteId).trim())}/circuits/${encodeURIComponent(String(circuitId).trim())}/dynamicCurrent`,
    body:{phase1:a,phase2:a,phase3:a,timeToLive:ttl},
    accessToken,
    kind:'SET_TRANSITION_CIRCUIT_CAP',
    transitionId,
    now,
  });
}

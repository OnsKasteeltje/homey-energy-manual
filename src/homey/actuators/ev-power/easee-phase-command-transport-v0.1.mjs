// Easee phase command transport v0.1
// Pure HTTP command adapter. No credential storage, no token refresh, no policy.
// Intended to be called only by the sole EV actuator after the transition
// state machine requests SET_PHASE_MODE.
//
// Official endpoint:
// POST https://api.easee.com/api/chargers/{serialNumber}/commands/set_phase_mode
// Body: { phaseMode: 1|3 }

export const EASEE_PHASE_COMMAND_SCHEMA='EM2_EASEE_PHASE_COMMAND_V0.1';

export function validatePhaseCommandInput({serialNumber,phaseMode,accessToken}){
  if(!String(serialNumber||'').trim())throw new Error('EASEE_SERIAL_MISSING');
  if(![1,3].includes(Number(phaseMode)))throw new Error('EASEE_PHASE_MODE_INVALID');
  if(!String(accessToken||'').trim())throw new Error('EASEE_ACCESS_TOKEN_MISSING');
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
  const url=`https://api.easee.com/api/chargers/${encodeURIComponent(String(serialNumber).trim())}/commands/set_phase_mode`;
  const requestedAt=now().toISOString();
  let response;
  try{
    response=await fetchFn(url,{
      method:'POST',
      headers:{
        'Authorization':`Bearer ${String(accessToken).trim()}`,
        'Content-Type':'application/json',
        'Accept':'application/json, application/octet-stream'
      },
      body:JSON.stringify({phaseMode:Number(phaseMode)})
    });
  }catch(err){
    return {
      schema:EASEE_PHASE_COMMAND_SCHEMA,
      transitionId:transitionId??null,
      requestedAt,
      completedAt:now().toISOString(),
      ok:false,
      httpStatus:null,
      reason:`NETWORK_ERROR:${String(err?.message||err)}`,
      phaseMode:Number(phaseMode),
      secretMaterialPersisted:false,
    };
  }

  const ok=response?.ok===true;
  return {
    schema:EASEE_PHASE_COMMAND_SCHEMA,
    transitionId:transitionId??null,
    requestedAt,
    completedAt:now().toISOString(),
    ok,
    httpStatus:Number(response?.status)||null,
    reason:ok?'ACCEPTED':`HTTP_${Number(response?.status)||'UNKNOWN'}`,
    phaseMode:Number(phaseMode),
    secretMaterialPersisted:false,
  };
}

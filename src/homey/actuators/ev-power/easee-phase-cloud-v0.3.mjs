// Easee phase cloud transport v0.3
// Pure HTTP helper for the only operation not exposed by the Homey Easee app:
// locked phase-mode control.
//
// No policy, no device current control, no circuit-current control.
// Initial authentication is handled by commissioning bootstrap.
// Runtime uses rotating access/refresh tokens supplied by the caller.

export const EASEE_PHASE_CLOUD_SCHEMA='EM2_EASEE_PHASE_CLOUD_V0.3';

const nonEmpty=v=>String(v||'').trim().length>0;

function result({kind,ok,status,reason,transitionId,now,extra={}}){
  return {
    schema:EASEE_PHASE_CLOUD_SCHEMA,
    kind,
    ok,
    httpStatus:status,
    reason,
    transitionId:transitionId??null,
    completedAt:now().toISOString(),
    ...extra,
    secretMaterialPersisted:false,
  };
}

async function postJson({fetchFn,url,body,accessToken,kind,transitionId,now}){
  const headers={
    'Content-Type':'application/json',
    'Accept':'application/json'
  };
  if(nonEmpty(accessToken))headers.Authorization=`Bearer ${String(accessToken).trim()}`;
  try{
    const response=await fetchFn(url,{
      method:'POST',
      headers,
      body:JSON.stringify(body)
    });
    let payload=null;
    try{payload=await response.json();}catch{}
    return {response,payload,result:result({
      kind,
      ok:response?.ok===true,
      status:Number(response?.status)||null,
      reason:response?.ok===true?'ACCEPTED':`HTTP_${Number(response?.status)||'UNKNOWN'}`,
      transitionId,now
    })};
  }catch(err){
    return {response:null,payload:null,result:result({
      kind,ok:false,status:null,
      reason:`NETWORK_ERROR:${String(err?.message||err)}`,
      transitionId,now
    })};
  }
}

export async function refreshEaseeTokenPair({
  fetchFn=fetch,
  accessToken,
  refreshToken,
  now=()=>new Date(),
}){
  if(!nonEmpty(accessToken))throw new Error('EASEE_ACCESS_TOKEN_MISSING');
  if(!nonEmpty(refreshToken))throw new Error('EASEE_REFRESH_TOKEN_MISSING');

  const {payload,result:base}=await postJson({
    fetchFn,
    url:'https://api.easee.com/api/accounts/refresh_token',
    body:{accessToken:String(accessToken).trim(),refreshToken:String(refreshToken).trim()},
    accessToken,
    kind:'REFRESH_TOKEN',
    transitionId:null,
    now,
  });
  if(!base.ok)return {...base,tokens:null};

  const nextAccess=payload?.accessToken;
  const nextRefresh=payload?.refreshToken;
  const expiresIn=Number(payload?.expiresIn);
  if(!nonEmpty(nextAccess)||!nonEmpty(nextRefresh)||!Number.isFinite(expiresIn)||expiresIn<=0){
    return {...base,ok:false,reason:'REFRESH_RESPONSE_INVALID',tokens:null};
  }
  return {
    ...base,
    tokens:{
      accessToken:nextAccess,
      refreshToken:nextRefresh,
      expiresIn
    }
  };
}

export async function sendEaseePhaseMode({
  fetchFn=fetch,
  serialNumber,
  phaseMode,
  accessToken,
  transitionId,
  now=()=>new Date(),
}){
  if(!nonEmpty(serialNumber))throw new Error('EASEE_SERIAL_MISSING');
  if(![1,3].includes(Number(phaseMode)))throw new Error('EASEE_PHASE_MODE_INVALID');
  if(!nonEmpty(accessToken))throw new Error('EASEE_ACCESS_TOKEN_MISSING');

  const {result:base}=await postJson({
    fetchFn,
    url:`https://api.easee.com/api/chargers/${encodeURIComponent(String(serialNumber).trim())}/commands/set_phase_mode`,
    body:{phaseMode:Number(phaseMode)},
    accessToken,
    kind:'SET_PHASE_MODE',
    transitionId,
    now,
  });
  return {...base,phaseMode:Number(phaseMode)};
}

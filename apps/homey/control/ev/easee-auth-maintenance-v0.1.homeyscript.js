// Easee authentication keepalive v0.1 — auth-only card in the existing EV writer Advanced Flow.
// Invoke every 15 minutes via a second cron trigger/action path. NEVER wire this
// code to a physical EV action card and NEVER start the EV actuator to test tokens.
// Canonical token bundle remains the same private Homey Logic variable.
const VERSION='EMS_EASEE_AUTH_MAINTENANCE_V0.1';
const BUNDLE_ID='__EM2_EASEE_BUNDLE_ID__';
const STATUS_ID='ea1f8a44-2f6c-490e-9b86-bae761886cf9';
const SCHEMA='EM2_EASEE_TOKEN_BUNDLE_V1';
const EARLY_REFRESH_MS=20*60*1000;
const ALERT_RETRY_MS=15*60*1000;
const nowISO=()=>new Date().toISOString();
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const validRevision=v=>Number.isSafeInteger(v)&&v>=0;
const future=(iso,marginMs=EARLY_REFRESH_MS)=>{
  const t=Date.parse(String(iso||''));
  return Number.isFinite(t)&&t>Date.now()+marginMs;
};
const readBundle=async()=>{
  if(!/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(BUNDLE_ID))
    throw new Error('EASEE_BUNDLE_NOT_CONFIGURED');
  const v=await Homey.logic.getVariable({id:BUNDLE_ID});
  const b=parse(v?.value);
  if(b?.schema!==SCHEMA||!b.accessToken||!b.refreshToken||
     !Number.isFinite(Date.parse(String(b.expiresAt||'')))||
     !validRevision(b.revision))
    throw new Error('EASEE_BUNDLE_INVALID');
  return b;
};
const readStatus=async()=>{
  const v=await Homey.logic.getVariable({id:STATUS_ID});
  return parse(v?.value)||{};
};
const writeStatus=async extra=>{
  // Preserve actuator target, hardware observations and physical status.
  const current=await readStatus();
  await Homey.logic.updateVariable({
    id:STATUS_ID,variable:{value:JSON.stringify({...current,...extra})}
  });
};
const notify=async(code,prior)=>{
  const prev=prior?.authAlert;
  const attempt=Date.parse(String(prev?.attemptedAt||''));
  if(prev?.active===true&&prev.code===code&&
    (prev.delivered===true||(Number.isFinite(attempt)&&Date.now()-attempt<ALERT_RETRY_MS)))
    return {...prev,deduped:true,lastObservedAt:nowISO()};
  const attemptedAt=nowISO();
  const msg='EMS Tesla: Easee-authenticatie mislukt ('+code+
    '). Automatisch laden kan geblokkeerd zijn. Controleer Easee tokens op de Pi.';
  let delivered=false,channel='NONE',pushError=null,timelineError=null;
  try{
    const users=await Homey.users.getUsers();
    const owner=Object.values(users||{}).find(u=>String(u?.role||'').toLowerCase()==='owner');
    if(!owner?.id||!owner?.athomId)throw new Error('HOMEY_OWNER_NOT_FOUND');
    await Homey.flow.runFlowCardAction({
      uri:'homey:manager:mobile',id:'homey:manager:mobile:push_text',
      args:{user:{id:owner.id,athomId:owner.athomId},text:msg}
    });
    delivered=true;channel='HOMEY_OWNER_PUSH';
  }catch(e){pushError=String(e?.message||e).slice(0,160);}
  if(!delivered){
    try{
      await Homey.flow.runFlowCardAction({
        uri:'homey:manager:notifications',
        id:'homey:manager:notifications:create_notification',
        args:{text:msg}
      });
      delivered=true;channel='HOMEY_TIMELINE_FALLBACK';
    }catch(e){timelineError=String(e?.message||e).slice(0,160);}
  }
  return {schema:'EM2_EV_AUTH_ALERT_V0.1',active:true,code,
          delivered,channel,attemptedAt,sentAt:delivered?nowISO():null,
          pushError,timelineError,deduped:false,
          remediation:'RUN_EASEE_TOKEN_BOOTSTRAP',secretMaterialIncluded:false};
};
const refresh=async()=>{
  const before=await readBundle();
  if(future(before.expiresAt))return {result:'VALID_NO_REFRESH',revision:before.revision};
  // Re-read immediately before using Easee's single-use refresh token.
  const current=await readBundle();
  if(current.revision>before.revision&&future(current.expiresAt))
    return {result:'NEWER_BUNDLE_REUSED',revision:current.revision};
  if(future(current.expiresAt))
    return {result:'VALID_NO_REFRESH',revision:current.revision};
  let response;
  try{
    response=await fetch('https://api.easee.com/api/accounts/refresh_token',{
      method:'POST',
      headers:{'Accept':'application/json','Content-Type':'application/json'},
      body:JSON.stringify({accessToken:current.accessToken,refreshToken:current.refreshToken})
    });
  }catch(_){throw new Error('EASEE_REFRESH_NETWORK_ERROR');}
  if(!response.ok){
    if(response.status===401){
      const newer=await readBundle();
      if(newer.revision>current.revision&&future(newer.expiresAt))
        return {result:'NEWER_BUNDLE_REUSED',revision:newer.revision};
    }
    throw new Error('EASEE_REFRESH_HTTP_'+response.status);
  }
  let payload;
  try{payload=await response.json();}catch(_){throw new Error('EASEE_REFRESH_INVALID');}
  const access=String(payload?.accessToken||'').trim();
  const token=String(payload?.refreshToken||'').trim();
  const ttl=Number(payload?.expiresIn);
  if(!access||!token||!Number.isFinite(ttl)||ttl<=0)
    throw new Error('EASEE_REFRESH_INVALID');
  const next={schema:SCHEMA,accessToken:access,refreshToken:token,
    expiresAt:new Date(Date.now()+Math.max(60,ttl-60)*1000).toISOString(),
    revision:current.revision+1};
  try{
    await Homey.logic.updateVariable({
      id:BUNDLE_ID,variable:{value:JSON.stringify(next)}
    });
  }catch(_){throw new Error('EASEE_BUNDLE_WRITE_FAILED');}
  const observed=await readBundle();
  if(observed.revision!==next.revision||
     observed.accessToken!==access||observed.refreshToken!==token)
    throw new Error('EASEE_BUNDLE_WRITE_CONFLICT');
  return {result:'REFRESHED',revision:observed.revision};
};
try{
  const result=await refresh();
  if(result.result==='REFRESHED'){
    const status=await readStatus();
    const previous=status.authAlert;
    await writeStatus({
      authMaintenance:{schema:VERSION,at:nowISO(),result:result.result,revision:result.revision},
      ...(previous?.active===true ? {authAlert:{...previous,active:false,
        resolvedAt:nowISO(),resolution:'EASEE_REFRESH_HTTP_SUCCESS'}}:{})
    });
  }
  return true;
}catch(err){
  const code=String(err?.message||err).slice(0,100);
  // No credential/token material appears in the status or notification.
  try{
    const previous=await readStatus();
    const authAlert=await notify(code,previous);
    await writeStatus({authAlert,
      authMaintenance:{schema:VERSION,at:nowISO(),result:'FAILED',reason:code}});
  }catch(_){}
  return false;
}

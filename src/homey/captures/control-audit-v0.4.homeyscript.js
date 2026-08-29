// Runtime capture 2026-08-30
// Flow ID: df295b26-9a47-497a-87c7-ccfd32323db1
// Homey runtime enabled=false, broken=false; EM2_Control_WW changed + 2 s settle.
const VAR='EM2_Control_Audit_History', MAX=120, PUB_MIN=30;
const OWNER='OnsKasteeltje', REPO='homey-energy-manual', PATH='docs/data/control-audit.json';
const now=new Date(), nowIso=now.toISOString(), nowMs=now.getTime();
const vars=await Homey.logic.getVariables();
const by=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
const parse=s=>{try{return JSON.parse(String(s??''));}catch{return null;}};
const ctl=parse(by.EM2_Control_WW?.value), st=parse(by.EM2_State?.value), ww=parse(by.EM2_WW_State?.value);
if(!ctl||!st||!ww)return false;
const r=Number(ctl.sourceRevision), sr=Number(st.revision), wr=Number(ww.sourceRevision);
if(!Number.isFinite(r)||r!==sr||r!==wr)return false;
const action=String(ctl.action??''), priority=String(ctl.priority??''), reason=String(ctl.reason??''), opportunity=String(ctl.opportunity??'');
const key=`${action}|${priority}|${reason}|${opportunity}`;
let h=parse(by[VAR]?.value);
if(!h||h.schema!=='EM2_CONTROL_AUDIT_V0.4')h={schema:'EM2_CONTROL_AUDIT_V0.4',updatedAt:null,lastKey:null,lastPublishAttemptAt:null,lastPublishedAt:null,lastPublishStatus:null,rows:[]};
let changed=false;
if(h.lastKey!==key){h.rows.push({at:nowIso,sourceRevision:r,action,priority,reason,opportunity,boilerMode:st?.ww?.boilerMode??null,wwState:ww?.state??null});if(h.rows.length>MAX)h.rows=h.rows.slice(-MAX);h.lastKey=key;h.updatedAt=nowIso;changed=true;}
const tokenVar=by['GitHub Personal Access Token'];
const lastAttemptMs=Date.parse(h.lastPublishAttemptAt||'');
const publishDue=changed&&tokenVar?.value&&(!Number.isFinite(lastAttemptMs)||nowMs-lastAttemptMs>=PUB_MIN*60000);
if(publishDue){h.lastPublishAttemptAt=nowIso;h.lastPublishStatus='ATTEMPTING';}
const hv=by[VAR], persist=async()=>{const value=JSON.stringify(h);if(hv){if(hv.value!==value){await Homey.logic.updateVariable({id:hv.id,variable:{value}});hv.value=value;}}else{const nv=await Homey.logic.createVariable({variable:{name:VAR,type:'string',value}});by[VAR]=nv;}};
if(changed||publishDue)await persist();
if(!publishDue)return true;
const token=String(tokenVar.value), headers={'Authorization':`Bearer ${token}`,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
const url=`https://api.github.com/repos/${OWNER}/${REPO}/contents/${PATH}`;
let sha=null, ok=false, err='';
try{const g=await fetch(url,{headers});if(g.ok){const j=await g.json();sha=j.sha??null;} else if(g.status!==404){throw new Error(`GET_${g.status}`);}const contentObj={schema:'EM2_CONTROL_AUDIT_PUBLIC_V0.4',generatedAt:nowIso,rows:h.rows};const body={message:`data: update control audit r${r}`,content:btoa(unescape(encodeURIComponent(JSON.stringify(contentObj,null,2))))};if(sha)body.sha=sha;const p=await fetch(url,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(body)});if(!p.ok)throw new Error(`PUT_${p.status}`);ok=true;}catch(e){err=String(e?.message||e).slice(0,120);}
h.lastPublishStatus=ok?'PASS':`FAIL_${err||'UNKNOWN'}`;if(ok)h.lastPublishedAt=new Date().toISOString();await persist();return true;

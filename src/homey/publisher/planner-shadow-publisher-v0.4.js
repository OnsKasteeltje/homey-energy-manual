// EM v2 | 46 Publish | Planner Shadow v0.4 event-driven LOW-LOAD
// Trigger only on EM2_Energy_Planner_Snapshot. Targeted Logic reads; no broad getVariables(). No device writes.
const OWNER='OnsKasteeltje',REPO='homey-energy-manual',BRANCH='main',OUT='docs/data/energy-planner-shadow.json';
const SNAPSHOT_ID='b9f1232c-ac01-45fa-9453-ef95d998b138';
const TOKEN_ID='235cfe0f-5760-48b9-9349-a33be47d04d1';
const REGRESSION_ID='443dfd4c-b4bf-42f5-b49a-3edf59ad69c3';
const CACHE_ID='c00f70fc-7617-46d0-9674-0950b94b600c';
const parse=v=>{try{return JSON.parse(String(v??''));}catch{return null;}};
const [sv,tv,rv,cv]=await Promise.all([
  Homey.logic.getVariable({id:SNAPSHOT_ID}),
  Homey.logic.getVariable({id:TOKEN_ID}),
  Homey.logic.getVariable({id:REGRESSION_ID}),
  Homey.logic.getVariable({id:CACHE_ID})
]);
const snapshot=parse(sv?.value),token=String(tv?.value||'').trim(),regression=parse(rv?.value),cache=parse(cv?.value)||{};
if(!snapshot||snapshot.schema!=='EM2_ENERGY_PLANNER_SNAPSHOT_V0.1'||!snapshot.plan||!token)throw new Error('Planner Shadow publish: missing/invalid snapshot or token');
const plan=snapshot.plan;
const planKey=`${snapshot.generatedAt||plan.generatedAt||'NA'}|${snapshot.sourceRevision??plan?.inputs?.sourceRevision??'NA'}`;
if(cache.lastPlanKey===planKey)return true;
const payload={schema:'EM2_PLANNER_SHADOW_PUBLISH_V0.4',publishedAt:new Date().toISOString(),observabilityOnly:true,controlImpact:'NONE',sourceRevision:snapshot.sourceRevision??plan?.inputs?.sourceRevision??null,generatedAt:snapshot.generatedAt??plan.generatedAt??null,plan,status:snapshot.status??null,regression};
const headers={'Authorization':`Bearer ${token}`,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Homey-EM2-Planner-Publisher-v0.4','Content-Type':'application/json'};
const url=`https://api.github.com/repos/${OWNER}/${REPO}/contents/${OUT}`;
const content=Buffer.from(JSON.stringify(payload,null,2)+'\n').toString('base64');
async function getSha(){const r=await fetch(`${url}?ref=${BRANCH}`,{headers});if(r.status===404)return null;if(!r.ok)throw new Error(`Planner Shadow SHA GET ${r.status}`);return (await r.json()).sha||null;}
async function put(sha){const body={message:'chore: publish rolling Planner Shadow snapshot',content,branch:BRANCH,...(sha?{sha}:{})};return fetch(url,{method:'PUT',headers,body:JSON.stringify(body)});}
let sha=typeof cache.sha==='string'&&cache.sha?cache.sha:null;if(!sha)sha=await getSha();
let r=await put(sha);if(!r.ok&&(r.status===409||r.status===422)){sha=await getSha();r=await put(sha);}if(!r.ok)throw new Error(`Planner Shadow PUT ${r.status}: ${(await r.text()).slice(0,160)}`);
const result=await r.json(),nextSha=result?.content?.sha||sha||null;
const next={schema:'EM2_PLANNER_SHADOW_PUBLISH_CACHE_V0.2',sha:nextSha,lastPlanKey:planKey,lastPublishedAt:payload.publishedAt,status:'OK',sourceRevision:payload.sourceRevision,generatedAt:payload.generatedAt};
const out=JSON.stringify(next);if(cv.value!==out)await Homey.logic.updateVariable({id:CACHE_ID,variable:{value:out}});
return true;
